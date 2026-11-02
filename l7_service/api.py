import asyncio,hashlib,json,threading
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI,Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from pydantic import ValidationError
from .contracts import Problem,Options,REQUEST_METHODS,MAX_REQUEST_BYTES,MAX_CSV_BYTES,MAX_JSON_BYTES,json_bytes
from .ingest import parse_csv,describe
from .remote import fetch_csv
from .analysis import run_method

ANALYSIS_LOCK=threading.Lock()

def reply(value,status=200):
    content=json_bytes(value)
    if len(content)>MAX_JSON_BYTES:raise Problem('result_too_large','JSON回應超過3,000,000 bytes。',413)
    return Response(content,status_code=status,media_type='application/json',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
def error(problem):return reply({'status':'failed','error':{'code':problem.code,'message':problem.message}},problem.status)

class BodyLimit:
    def __init__(self,app):self.app=app
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or not scope.get('path','').startswith('/api/') or scope.get('method')!='POST':return await self.app(scope,receive,send)
        headers=dict(scope.get('headers',[]));length=headers.get(b'content-length')
        if length:
            try:size=int(length)
            except ValueError:return await error(Problem('request_length','Content-Length不合法。',400))(scope,receive,send)
            if size<0 or size>MAX_REQUEST_BYTES:return await error(Problem('request_too_large','請求超過3,570,000 bytes。',413))(scope,receive,send)
        origin=headers.get(b'origin')
        if origin:
            try:origin_host=urlsplit(origin.decode()).netloc.lower()
            except (ValueError,UnicodeError):origin_host=''
            if not origin_host or origin_host!=headers.get(b'host',b'').decode().lower():return await error(Problem('cross_origin','請從此網站頁面送出分析請求。',403))(scope,receive,send)
        chunks=[];total=0
        while True:
            message=await receive()
            if message['type']=='http.disconnect':return
            chunk=message.get('body',b'');total+=len(chunk)
            if total>MAX_REQUEST_BYTES:return await error(Problem('request_too_large','請求內容超過大小限制。',413))(scope,receive,send)
            chunks.append(chunk)
            if not message.get('more_body',False):break
        body=b''.join(chunks);sent=False
        async def replay():
            nonlocal sent
            if not sent:sent=True;return {'type':'http.request','body':body,'more_body':False}
            return await receive()
        return await self.app(scope,replay,send)

async def multipart(request):
    if not request.headers.get('content-type','').lower().startswith('multipart/form-data'):raise Problem('multipart_required','請以CSV檔案表單傳送資料。',415)
    try:
        async with request.form(max_files=1,max_fields=2,max_part_size=MAX_CSV_BYTES) as form:
            if not set(form.keys())<={'file','options','sha256'} or any(len(form.getlist(k))!=1 for k in form):raise Problem('invalid_form','表單欄位重複或不合法。')
            file=form.get('file')
            if not isinstance(file,UploadFile):raise Problem('file_missing','請選擇CSV檔案。')
            data=await file.read(MAX_CSV_BYTES+1)
            if len(data)>MAX_CSV_BYTES:raise Problem('csv_too_large','CSV超過3,500,000 bytes。',413)
            raw_options=form.get('options','{}');expected_sha=form.get('sha256')
            if not isinstance(raw_options,str) or len(raw_options.encode())>50000:raise Problem('options_size','分析設定不合法或過大。')
            if expected_sha is not None and (not isinstance(expected_sha,str) or len(expected_sha)!=64):raise Problem('source_fingerprint','資料指紋格式不合法。')
            return data,raw_options,expected_sha
    except Problem:raise
    except HTTPException as e:raise Problem('invalid_form','上傳表單超過欄位限制或格式不完整。',400) from e

def create_app(web_root=None):
    app=FastAPI(title='Lesson 7 Custom Dataset API',docs_url=None,redoc_url=None,openapi_url=None,telemetry={'tracing':False})
    app.add_middleware(BodyLimit)
    @app.exception_handler(Problem)
    async def problem_handler(request,exc):return error(exc)
    @app.exception_handler(HTTPException)
    async def http_handler(request,exc):return error(Problem('http_error','找不到指定資源或請求格式不合法。',exc.status_code))

    @app.get('/api/health')
    async def health():return reply({'status':'ok','pipeline':'custom-v1','methods':list(REQUEST_METHODS),'persist_uploads':False,'json_limit':MAX_JSON_BYTES,'csv_limit':MAX_CSV_BYTES})

    @app.post('/api/data/preview')
    async def preview(request:Request):
        data,_,_=await multipart(request)
        def inspect():
            frame,source=parse_csv(data);return describe(frame,source)
        return reply(await asyncio.to_thread(inspect))

    @app.post('/api/data/url')
    async def remote(request:Request):
        if not request.headers.get('content-type','').lower().startswith('application/json'):raise Problem('json_required','網址設定需為JSON。',415)
        body=await request.body()
        if len(body)>4096:raise Problem('url_size','網址設定過長。',413)
        try:value=json.loads(body)
        except (ValueError,UnicodeError) as e:raise Problem('invalid_json','網址設定不是合法JSON。',400) from e
        if not isinstance(value,dict) or set(value)!={'url'}:raise Problem('url_fields','網址設定只接受url欄位。')
        data,transport=await asyncio.to_thread(fetch_csv,value['url'])
        # Validate actual CSV before returning it to the browser. No remote body is stored.
        await asyncio.to_thread(parse_csv,data)
        return Response(data,media_type='text/csv',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
            'X-Dataset-SHA256':hashlib.sha256(data).hexdigest(),'X-Source-Host':transport['host'],'X-Redirect-Count':str(transport['redirects'])})

    @app.post('/api/analyze/{method}')
    async def analyze(method:str,request:Request):
        if method not in REQUEST_METHODS:raise Problem('unknown_method','找不到指定分析方法。',404)
        data,raw_options,expected_sha=await multipart(request)
        try:options=Options.model_validate_json(raw_options)
        except ValidationError as e:raise Problem('invalid_options','Target／排除／類別／群組或轉換設定格式不正確。') from e
        if not ANALYSIS_LOCK.acquire(blocking=False):raise Problem('instance_busy','此執行個體正在分析；前一工作可能仍在收尾，請稍後重試。',409)
        cancelled=threading.Event()
        def work():
            try:
                frame,source=parse_csv(data)
                if expected_sha and expected_sha!=source['sha256']:raise Problem('source_changed','CSV與預覽時的指紋不同，請重新預覽。',409)
                return run_method(frame,source,options,method,cancel=cancelled.is_set)
            finally:ANALYSIS_LOCK.release()
        task=asyncio.create_task(asyncio.to_thread(work))
        try:
            while not task.done():
                if await request.is_disconnected():cancelled.set()
                await asyncio.sleep(.1)
            return reply(await task)
        except asyncio.CancelledError:
            cancelled.set()
            # Thread owns the lock until its cooperative checkpoint/finally completes.
            task.add_done_callback(lambda t:t.exception() if not t.cancelled() else None)
            raise

    if web_root is not None:app.mount('/',StaticFiles(directory=str(web_root),html=True),name='web')
    return app
