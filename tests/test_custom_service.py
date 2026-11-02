import io,json,time,unittest,threading
from unittest.mock import patch,Mock
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from l7_service.contracts import Options,Problem,MAX_CSV_BYTES,fingerprint
from l7_service.ingest import parse_csv,describe,prepare
from l7_service.remote import validate_url,public_ip,fetch_csv,PinnedHTTPSConnection
from l7_service.analysis import run_method
from l7_service.api import create_app,ANALYSIS_LOCK

def data(rows=80):
    x=np.arange(rows,dtype=float)
    return pd.DataFrame({'x':x,'z':np.sin(x),'state':['A','B','C','A']*(rows//4),
                         'y':2*x+np.sin(x)*3+(x%7)*.13}).to_csv(index=False).encode()
def parsed():return parse_csv(data())

class IngestTests(unittest.TestCase):
    def test_csv_real_types_and_profile(self):
        f,s=parsed();p=describe(f,s);self.assertEqual(s['rows'],80);self.assertEqual(p['columns'][2]['kind'],'categorical');self.assertEqual(len(p['preview']),5)
    def test_semicolon_and_literal_NA(self):
        b=('a;b;y\n'+''.join(f'{i};NA;{i+1}\n' for i in range(50))).encode();f,s=parse_csv(b)
        self.assertEqual(s['delimiter'],';');self.assertEqual(f.b.isna().sum(),0)
    def test_duplicate_headers(self):
        with self.assertRaisesRegex(Problem,'重複欄名'):parse_csv(b'a,a\n1,2\n'*50)
    def test_inconsistent_row(self):
        with self.assertRaises(Problem):parse_csv(b'a,b\n1,2,3\n'+b'1,2\n'*50)
    def test_row_bounds(self):
        for n in [49,10001]:
            with self.subTest(n=n),self.assertRaises(Problem):parse_csv(('x,y\n'+''.join(f'{i},{i+1}\n' for i in range(n))).encode())
    def test_size_and_encoding(self):
        for b in [b'a'*(MAX_CSV_BYTES+1),b'\xff\xfe',b'<html>not a csv</html>']:
            with self.subTest(length=len(b)),self.assertRaises(Problem):parse_csv(b)
    def test_source_column_budget(self):
        with self.assertRaises(Problem):parse_csv((','.join('c'+str(i) for i in range(101))+'\n').encode())
    def test_long_text_preview_bounded_and_active_category_rejected(self):
        f,s=parsed();f['state']=['x'*10000]*80;p=describe(f,s)
        self.assertLess(len(p['preview'][0]['state']),200)
        with self.assertRaises(Problem):prepare(f,s,Options(target='y'))
    def test_invalid_targets(self):
        f,s=parsed()
        for kind in ['missing','infinite','constant','text']:
            g=f.copy()
            if kind=='missing':g.loc[0,'y']=np.nan
            if kind=='infinite':g.loc[0,'y']=np.inf
            if kind=='constant':g['y']=1
            if kind=='text':g['y']='text'
            with self.subTest(kind=kind),self.assertRaises(Problem):prepare(g,s,Options(target='y'))
    def test_invalid_log(self):
        f,s=parsed();f.loc[0,'y']=0
        with self.assertRaises(Problem):prepare(f,s,Options(target='y',target_transform='log'))
    def test_category_and_input_budgets(self):
        f,s=parsed();f['unique_text']=['label'+str(i) for i in range(len(f))]
        with self.assertRaises(Problem):prepare(f,s,Options(target='y'))
        g=pd.DataFrame({f'x{i}':np.arange(80)+i for i in range(40)});g['y']=np.arange(80)
        with self.assertRaises(Problem):prepare(g,s,Options(target='y'))
    def test_encoded_budget(self):
        f,s=parsed()
        for i in range(4):f['category'+str(i)]=['c'+str(x%20) for x in range(80)]
        with self.assertRaises(Problem):prepare(f,s,Options(target='y'))
    def test_source_and_option_fingerprints(self):
        _,s=parsed();a=fingerprint(Options(target='y'),s['sha256']);b=fingerprint(Options(target='y',exclude=['z']),s['sha256'])
        self.assertNotEqual(a,b)
    def test_duplicate_x_isolated(self):
        f=pd.DataFrame({'x':np.repeat(np.arange(40),2),'y':np.arange(80)});_,s=parsed()
        train,test,_,_,_,split,_=prepare(f,s,Options(target='y'))
        self.assertTrue(split['grouped']);self.assertFalse(set(train.x)&set(test.x))
    def test_group_and_duplicate_union(self):
        f=pd.DataFrame({'x':np.arange(80),'subject':np.repeat(np.arange(10),8),'y':np.arange(80)*2})
        f.loc[8,'x']=f.loc[0,'x'];_,s=parsed();train,test,ti,vi,_,split,_=prepare(f,s,Options(target='y',group='subject'))
        self.assertFalse(set(f.subject.iloc[ti])&set(f.subject.iloc[vi]));self.assertFalse(set(train.x)&set(test.x));self.assertEqual(split['effective_groups'],9)
    def test_missing_or_insufficient_groups(self):
        f,s=parsed();f['group']=1
        with self.assertRaises(Problem):prepare(f,s,Options(target='y',group='group'))
        f.loc[0,'group']=np.nan
        with self.assertRaises(Problem):prepare(f,s,Options(target='y',group='group'))
    def test_holdout_deterministic(self):
        f,s=parsed();a=prepare(f,s,Options(target='y'));b=prepare(f,s,Options(target='y'))
        self.assertTrue(np.array_equal(a[2],b[2]));self.assertFalse(set(a[2])&set(a[3]));self.assertEqual(a[5]['test_rows'],16)

class Response:
    def __init__(self,status=200,headers=None,body=b'csv'):
        self.status=status;self.headers=headers or {};self.body=io.BytesIO(body)
    def getheader(self,key):return self.headers.get(key)
    def read1(self,size):return self.body.read(size)
class Connection:
    def __init__(self,response):self.response=response;self.calls=[];self.closed=False
    def request(self,*args,**kwargs):self.calls.append((args,kwargs))
    def getresponse(self):return self.response
    def close(self):self.closed=True

class RemoteTests(unittest.TestCase):
    def test_absolute_deadline_interrupts_stalled_headers(self):
        event=threading.Event()
        class Socket:
            def shutdown(self,how):event.set()
            def close(self):pass
        class Stalled(Connection):
            def __init__(self):super().__init__(Response());self.sock=Socket()
            def getresponse(self):event.wait(1);raise OSError('closed deadline socket')
        start=time.monotonic()
        with self.assertRaises(Problem) as captured:fetch_csv('https://example.org/x',resolver=lambda *_:['8.8.8.8'],connection_factory=lambda *_:Stalled(),seconds=.03)
        self.assertEqual(captured.exception.code,'url_timeout');self.assertLess(time.monotonic()-start,.5)
    def test_private_and_malformed_urls(self):
        for u in ['http://example.org/x','https://127.0.0.1/x','https://[::1]/x','https://169.254.169.254/x','https://10.0.0.1/x','https://u:p@example.org/x','https://example.org:8443/x','https://example.org/x#fragment','https://localhost/x','https://example.org/a\nb']:
            with self.subTest(url=u),self.assertRaises(Problem):validate_url(u)
    def test_ip_policy(self):
        for ip in ['127.0.0.1','::ffff:127.0.0.1','0.0.0.0','224.0.0.1','100.64.0.1']:self.assertFalse(public_ip(ip))
        self.assertTrue(public_ip('8.8.8.8'))
    def test_dns_mixed_private_blocked_before_connect(self):
        factory=Mock()
        with self.assertRaises(Problem):fetch_csv('https://example.org/a',resolver=lambda *_:['8.8.8.8','127.0.0.1'],connection_factory=factory)
        factory.assert_not_called()
    def test_public_connection_is_pinned_once(self):
        resolver=Mock(return_value=['8.8.8.8']);conn=Connection(Response(body=b'abc'));factory=Mock(return_value=conn)
        body,_=fetch_csv('https://example.org/x?q=1',resolver=resolver,connection_factory=factory)
        self.assertEqual(body,b'abc');self.assertEqual(resolver.call_count,1);self.assertEqual(factory.call_args.args[:2],('example.org',['8.8.8.8']));self.assertTrue(conn.closed)
        headers=conn.calls[0][1]['headers'];self.assertNotIn('Cookie',headers);self.assertNotIn('Authorization',headers)
    def test_redirect_private_revalidated(self):
        conn=Connection(Response(302,{'Location':'https://127.0.0.1/secret'}));factory=Mock(return_value=conn)
        with self.assertRaises(Problem):fetch_csv('https://example.org/a',resolver=lambda *_:['8.8.8.8'],connection_factory=factory)
        self.assertEqual(factory.call_count,1);self.assertTrue(conn.closed)
    def test_redirect_public_and_limit(self):
        responses=[Connection(Response(302,{'Location':'https://other.example/b'})),Connection(Response(body=b'ok'))];resolver=Mock(return_value=['8.8.8.8'])
        body,m=fetch_csv('https://example.org/a',resolver=resolver,connection_factory=lambda *_:responses.pop(0))
        self.assertEqual(body,b'ok');self.assertEqual(m['redirects'],1);self.assertEqual(resolver.call_count,2)
        with self.assertRaises(Problem):fetch_csv('https://example.org/a',resolver=lambda *_:['8.8.8.8'],connection_factory=lambda *_:Connection(Response(302,{'Location':'/a'})))
    def test_remote_size_encoding_media_and_status(self):
        cases=[Response(200,{'Content-Length':str(MAX_CSV_BYTES+1)}),Response(200,body=b'x'*(MAX_CSV_BYTES+1)),Response(200,{'Content-Type':'text/html'}),Response(200,{'Content-Encoding':'gzip'}),Response(404)]
        for response in cases:
            with self.subTest(headers=response.headers,status=response.status),self.assertRaises(Problem):fetch_csv('https://example.org/a',resolver=lambda *_:['8.8.8.8'],connection_factory=lambda *_:Connection(response))
    def test_socket_peer_checked_and_original_host_tls(self):
        conn=PinnedHTTPSConnection('example.org',['8.8.8.8'],time.monotonic()+5);raw=Mock();raw.getpeername.return_value=('8.8.8.8',443);ctx=Mock();conn._context=ctx
        with patch('l7_service.remote.socket.socket',return_value=raw):conn.connect()
        raw.connect.assert_called_once_with(('8.8.8.8',443));ctx.wrap_socket.assert_called_once_with(raw,server_hostname='example.org')
        conn=PinnedHTTPSConnection('example.org',['8.8.8.8'],time.monotonic()+5);raw.getpeername.return_value=('127.0.0.1',443)
        with patch('l7_service.remote.socket.socket',return_value=raw),self.assertRaises(Problem):conn.connect()

class AnalysisTests(unittest.TestCase):
    def test_real_method_core_and_intervals(self):
        f,s=parsed();r=run_method(f,s,Options(target='y'),'kbest')
        self.assertEqual(r['status'],'completed');self.assertEqual(len(r['models']),1);m=r['models'][0]
        self.assertEqual(m['artifact']['fit_rows'],64);self.assertEqual(m['test_metrics']['n'],16);self.assertIsNotNone(m['inference']);self.assertEqual(len(r['folds']),5)
    def test_zero_budget_and_cancellation_not_success(self):
        f,s=parsed();o=Options(target='y')
        self.assertEqual(run_method(f,s,o,'kbest',budget_seconds=0)['status'],'partial_timeout')
        self.assertEqual(run_method(f,s,o,'kbest',cancel=lambda:True)['status'],'cancelled')
    def test_rank_deficiency_and_zero_variance_no_fake_intervals(self):
        for exact in [True,False]:
            f=pd.DataFrame({'x':np.arange(80),'double_x':np.arange(80)*2,'y':np.arange(80)*3+(0 if exact else np.sin(np.arange(80)))})
            _,s=parsed();r=run_method(f,s,Options(target='y'),'baseline');m=next(x for x in r['models'] if x['method']=='ols')
            self.assertIsNone(m['inference']);self.assertTrue(m['inference_status'].startswith('unavailable'))
    def test_test_only_category_not_in_fitted_encoder(self):
        f,s=parsed();_,test,_,test_ids,_,_,_=prepare(f,s,Options(target='y'));f.loc[int(test_ids[0]),'state']='UNSEEN'
        r=run_method(f,s,Options(target='y'),'baseline');m=next(x for x in r['models'] if x['method']=='ols')
        field=next(x for x in m['artifact']['preprocessor']['fields'] if x['field']=='state')
        self.assertNotIn('UNSEEN',field['categories']);self.assertEqual(m['test_transform_notes']['unknown_categories']['state'],1)
    def test_result_budget_error_explicit(self):
        f,s=parsed()
        with patch('l7_service.analysis.MAX_JSON_BYTES',100),self.assertRaises(Problem):run_method(f,s,Options(target='y'),'kbest')

class ApiTests(unittest.TestCase):
    def setUp(self):self.client=TestClient(create_app())
    def post(self,path,options=None,headers=None):
        return self.client.post(path,files={'file':('data.csv',data(),'text/csv')},data={'options':json.dumps(options or {'target':'y'})},headers=headers)
    def test_real_preview_and_analysis(self):
        p=self.post('/api/data/preview');self.assertEqual(p.status_code,200);self.assertEqual(p.json()['source']['rows'],80)
        a=self.post('/api/analyze/kbest');self.assertEqual(a.status_code,200);self.assertEqual(a.json()['status'],'completed');self.assertEqual(a.headers['cache-control'],'no-store')
    def test_busy_request(self):
        ANALYSIS_LOCK.acquire()
        try:self.assertEqual(self.post('/api/analyze/kbest').status_code,409)
        finally:ANALYSIS_LOCK.release()
    def test_origin_and_content_length(self):
        self.assertEqual(self.post('/api/data/preview',headers={'Origin':'https://other.example'}).status_code,403)
        r=self.client.post('/api/data/preview',content=b'x',headers={'content-length':'9999999'});self.assertEqual(r.status_code,413)
    def test_chunked_actual_body_limit(self):
        def chunks():
            for _ in range(60):yield b'x'*65536
        r=self.client.post('/api/data/preview',content=chunks(),headers={'Content-Type':'multipart/form-data; boundary=boundary'});self.assertEqual(r.status_code,413)
    def test_invalid_options_and_method(self):
        self.assertEqual(self.post('/api/analyze/unknown').status_code,404)
        self.assertEqual(self.post('/api/analyze/kbest',{'target':'y','budget_seconds':9999}).status_code,422)
    def test_source_hash_mismatch(self):
        r=self.client.post('/api/analyze/kbest',files={'file':('x.csv',data(),'text/csv')},data={'options':'{"target":"y"}','sha256':'0'*64})
        self.assertEqual(r.status_code,409);self.assertEqual(r.json()['error']['code'],'source_changed')
    def test_remote_path_is_raw_validated_csv(self):
        with patch('l7_service.api.fetch_csv',return_value=(data(),{'host':'example.org','redirects':0})):
            r=self.client.post('/api/data/url',json={'url':'https://example.org/x.csv'})
        self.assertEqual(r.status_code,200);self.assertEqual(r.content,data());self.assertIn('x-dataset-sha256',r.headers)
    def test_bad_remote_body_and_url(self):
        self.assertEqual(self.client.post('/api/data/url',json={'url':'http://127.0.0.1'}).status_code,422)
        with patch('l7_service.api.fetch_csv',return_value=(b'<html>no</html>',{'host':'example.org','redirects':0})):
            self.assertEqual(self.client.post('/api/data/url',json={'url':'https://example.org/x.csv'}).status_code,422)

if __name__=='__main__':unittest.main()
