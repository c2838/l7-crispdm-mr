"""Public HTTPS CSV fetch: vetted DNS results pinned to the actual socket + TLS SNI."""
import concurrent.futures,http.client,ipaddress,re,socket,ssl,threading,time
from urllib.parse import urlsplit,urljoin,quote
from .contracts import Problem,MAX_CSV_BYTES,URL_SECONDS

_DNS_POOL=concurrent.futures.ThreadPoolExecutor(max_workers=2,thread_name_prefix='csv-dns')
_DNS_SLOTS=threading.BoundedSemaphore(2)

def public_ip(text):
    try:
        value=ipaddress.ip_address(text)
        if getattr(value,'ipv4_mapped',None):value=value.ipv4_mapped
        return value.is_global and not value.is_multicast and not value.is_unspecified
    except ValueError:return False

def validate_url(url):
    if not isinstance(url,str) or len(url)>2048 or not url or any(ord(c)<=32 or ord(c)==127 for c in url):raise Problem('invalid_url','請輸入無空白／控制字元、最多2048字元的公開HTTPS CSV網址。')
    try:p=urlsplit(url);port=p.port
    except ValueError as e:raise Problem('invalid_url','網址格式或port不合法。') from e
    if p.scheme.lower()!='https' or not p.hostname or p.username is not None or p.password is not None or p.fragment or port not in (None,443):
        raise Problem('invalid_url','只接受443埠的公開HTTPS網址，不接受帳密、fragment或其他協定。')
    try:host=p.hostname.rstrip('.').encode('idna').decode('ascii').lower()
    except UnicodeError as e:raise Problem('invalid_url','網域名稱無法解析。') from e
    if '%' in host or len(host)>253 or host=='localhost' or host.endswith(('.localhost','.local','.internal')):raise Problem('private_url','不能讀取本機或內部網路。')
    try:address=ipaddress.ip_address(host)
    except ValueError:address=None
    if address is not None:
        if not public_ip(host):raise Problem('private_url','不能讀取非公開IP位址。')
    else:
        if not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',part) for part in host.split('.')):raise Problem('invalid_url','網域名稱格式不合法。')
    target=quote(p.path or '/',safe="/%:@!$&'()*+,;=-._~")
    if p.query:target+='?'+quote(p.query,safe="/%?:@!$&'()*+,;=-._~")
    return host,target

def bounded_dns(host,timeout):
    if not _DNS_SLOTS.acquire(blocking=False):raise Problem('dns_busy','網址解析忙碌，請稍後重試。',503)
    future=_DNS_POOL.submit(socket.getaddrinfo,host,443,0,socket.SOCK_STREAM)
    future.add_done_callback(lambda _: _DNS_SLOTS.release())
    try:records=future.result(timeout=max(.001,timeout))
    except concurrent.futures.TimeoutError as e:raise Problem('url_timeout','公開網址解析超時。',504) from e
    except OSError as e:raise Problem('dns_failed','公開網址無法解析；請確認網址或改用檔案上傳。',422) from e
    addresses=list(dict.fromkeys(record[4][0] for record in records))
    return addresses

class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self,host,addresses,deadline):
        super().__init__(host,443,timeout=max(.01,deadline-time.monotonic()),context=ssl.create_default_context())
        self.addresses=addresses;self.deadline=deadline
    def connect(self):
        last=None
        for address in self.addresses:
            raw=None
            try:
                remaining=self.deadline-time.monotonic()
                if remaining<=0:raise TimeoutError()
                family=socket.AF_INET6 if ':' in address else socket.AF_INET
                raw=socket.socket(family,socket.SOCK_STREAM);raw.settimeout(min(3.,remaining))
                raw.connect((address,443))
                peer=raw.getpeername()[0]
                if ipaddress.ip_address(peer)!=ipaddress.ip_address(address) or not public_ip(peer):raise Problem('private_url','實際連線IP與已驗證的公開目標不一致。')
                raw.settimeout(max(.01,self.deadline-time.monotonic()))
                self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
                return
            except Problem:
                if raw:raw.close()
                raise
            except (OSError,ssl.SSLError) as e:
                last=e
                if raw:raw.close()
        raise OSError('Could not connect to vetted public target') from last

def fetch_csv(url,*,resolver=bounded_dns,connection_factory=PinnedHTTPSConnection,seconds=URL_SECONDS):
    deadline=time.monotonic()+seconds;seen=set()
    for hop in range(4):
        if url in seen:raise Problem('redirect_loop','網址重新導向形成循環。')
        seen.add(url);host,target=validate_url(url)
        remaining=deadline-time.monotonic()
        if remaining<=0:raise Problem('url_timeout','公開CSV取得超過15秒。',504)
        addresses=resolver(host,remaining)
        if not addresses or any(not public_ip(ip) for ip in addresses):raise Problem('private_url','DNS含非公開位址，拒絕連線。')
        conn=connection_factory(host,addresses,deadline)
        expired=threading.Event()
        def abort_at_deadline():
            expired.set();sock=getattr(conn,'sock',None)
            if sock is not None:
                try:sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass
                try:sock.close()
                except OSError:pass
        timer=threading.Timer(max(.001,deadline-time.monotonic()),abort_at_deadline);timer.daemon=True;timer.start()
        try:
            conn.request('GET',target,headers={'Accept':'text/csv,text/plain,application/octet-stream;q=0.8','Accept-Encoding':'identity','User-Agent':'Lesson7-CustomCSV/1.0'})
            response=conn.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location or hop==3:raise Problem('redirect_limit','網址重新導向缺少目標或超過3次。')
                url=urljoin(url,location);continue
            if response.status!=200:raise Problem('remote_status',f'資料來源回應HTTP {response.status}；請確認是公開CSV。')
            encoding=(response.getheader('Content-Encoding') or 'identity').lower()
            if encoding not in ('identity',''):raise Problem('compressed_remote','來源回傳壓縮內容，請改用未壓縮的公開CSV或先下載後上傳。')
            content_type=(response.getheader('Content-Type') or '').split(';')[0].strip().lower()
            if content_type in ('text/html','application/xhtml+xml','application/pdf') or content_type.startswith(('image/','audio/','video/')):raise Problem('not_csv','網址回傳網頁或其他媒體，並非CSV資料檔。')
            length=response.getheader('Content-Length')
            if length:
                try:size=int(length)
                except ValueError as e:raise Problem('remote_length','來源的Content-Length不合法。') from e
                if size<0 or size>MAX_CSV_BYTES:raise Problem('csv_too_large','公開CSV超過3,500,000 bytes。',413)
            chunks=[];total=0
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise Problem('url_timeout','公開CSV取得超過15秒。',504)
                if getattr(conn,'sock',None):conn.sock.settimeout(remaining)
                # read1 avoids waiting to fill a whole chunk while a peer trickles bytes.
                chunk=response.read1(min(65536,MAX_CSV_BYTES+1-total))
                if not chunk:break
                total+=len(chunk)
                if total>MAX_CSV_BYTES:raise Problem('csv_too_large','公開CSV超過3,500,000 bytes。',413)
                chunks.append(chunk)
            return b''.join(chunks),{'host':host,'redirects':hop,'bytes':total,'verified_public_addresses':addresses,'transport':'Pinned public IP; TLS certificate + original-host SNI; no credentials/proxy/cookies'}
        except Problem:raise
        except (TimeoutError,socket.timeout) as e:raise Problem('url_timeout','公開CSV取得超時，請改用上傳。',504) from e
        except (OSError,http.client.HTTPException,ssl.SSLError) as e:
            if expired.is_set():raise Problem('url_timeout','公開CSV取得超過總時間預算，已關閉連線。',504) from e
            raise Problem('remote_unavailable','公開CSV連線或TLS驗證失敗；未略過憑證驗證，請確認網址或改用上傳。') from e
        finally:timer.cancel();conn.close()
    raise Problem('redirect_limit','重新導向次數過多。')
