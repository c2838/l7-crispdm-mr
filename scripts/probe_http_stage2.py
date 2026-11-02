"""Local native/FastAPI feasibility probes, not the production API.

Starts localhost-only servers on OS-selected ports, sends real HTTP requests,
checks CSV upload/validation/download, then closes both servers.
"""
from pathlib import Path
import argparse
import csv
import io
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from typing import Annotated

MAX_FILE_BYTES=3_500_000

def csv_summary(content,target):
    if len(content)>MAX_FILE_BYTES:raise ValueError('file_too_large')
    text=content.decode('utf-8-sig');reader=csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or target not in reader.fieldnames:raise ValueError('target_missing')
    rows=list(reader)
    if not rows:raise ValueError('no_data_rows')
    return {'rows':len(rows),'columns':len(reader.fieldnames),'target':target,'prototype_only':True}

class NativeHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,status,value,download=False):
        body=json.dumps(value).encode();self.send_response(status)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)))
        if download:self.send_header('Content-Disposition','attachment; filename="probe.json"')
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        self.respond(200,{'prototype_only':True},self.path=='/download')
    def do_POST(self):
        length=int(self.headers.get('Content-Length','0'))
        if length>MAX_FILE_BYTES:return self.respond(413,{'detail':'file_too_large'})
        query=parse_qs(urlparse(self.path).query);target=query.get('target',[''])[0]
        if not target:return self.respond(422,{'detail':'target_required'})
        try:result=csv_summary(self.rfile.read(length),target)
        except (ValueError,UnicodeDecodeError) as e:return self.respond(400,{'detail':str(e)})
        return self.respond(200,result)

def main(root):
    import pandas as pd
    import httpx
    import uvicorn
    from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Response
    from pydantic import BaseModel, Field
    app=FastAPI()
    class Config(BaseModel):
        target:str=Field(min_length=1,max_length=120)
        max_features:int=Field(ge=1,le=64)
    @app.get('/health')
    def health():return {'prototype_only':True}
    @app.post('/upload')
    async def upload(file:Annotated[UploadFile,File()],target:Annotated[str,Form(min_length=1,max_length=120)]):
        try:
            content=await file.read(MAX_FILE_BYTES+1)
            if len(content)>MAX_FILE_BYTES:raise HTTPException(413,'file_too_large')
            try:return csv_summary(content,target)
            except (ValueError,UnicodeDecodeError) as e:raise HTTPException(400,str(e))
        finally:await file.close()
    @app.post('/parameters')
    def parameters(config:Config):return config.model_dump()
    @app.get('/download')
    def download():return Response(json.dumps({'prototype_only':True}),media_type='application/json',
                                  headers={'Content-Disposition':'attachment; filename="probe.json"'})
    split=pd.read_csv(root/'artifacts/analysis/data-audit/dataset-b-split.csv')
    allowed=set(split.loc[split.split=='development','source_row_index_0_based'])
    frame=pd.read_csv(root/'data/processed/student-model-input.csv',skiprows=lambda i:i>0 and i-1 not in allowed)
    content=frame.to_csv(index=False).encode();assert len(frame)==519
    checks=[]
    def record(name,actual,expected,method):
        passed=actual==expected;checks.append({'name':name,'method':method,'expected':expected,'actual':actual,'passed':passed})
        assert passed,(name,actual,expected)
    native=ThreadingHTTPServer(('127.0.0.1',0),NativeHandler)
    nt=threading.Thread(target=native.serve_forever,daemon=True);nt.start()
    sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen(16)
    port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False,workers=1))
    ft=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True);ft.start()
    try:
        for _ in range(200):
            if server.started:break
            time.sleep(.02)
        assert server.started,'FastAPI startup failed'
        with httpx.Client(timeout=20,trust_env=False) as client:
            nurl=f'http://127.0.0.1:{native.server_port}';furl=f'http://127.0.0.1:{port}'
            r=client.post(nurl+'/upload?target=G3',content=content)
            record('native real CSV request status',r.status_code,200,'localhost HTTP, actual development CSV bytes')
            record('native parsed rows',r.json()['rows'],519,'response parsed from real CSV upload')
            r=client.post(nurl+'/upload',content=content)
            record('native manual missing-target validation',r.status_code,422,'localhost HTTP invalid query')
            r=client.post(furl+'/upload',files={'file':('student.csv',content,'text/csv')},data={'target':'G3'})
            record('FastAPI multipart upload status',r.status_code,200,'localhost HTTP multipart with actual development CSV')
            record('FastAPI parsed rows',r.json()['rows'],519,'response parsed from real CSV upload')
            r=client.post(furl+'/upload',files={'file':('student.csv',content,'text/csv')})
            record('FastAPI missing form target',r.status_code,422,'real malformed multipart request')
            r=client.post(furl+'/upload',files={'file':('student.csv',content,'text/csv')},data={'target':'missing'})
            record('FastAPI nonexistent target',r.status_code,400,'real CSV with target absent from its header')
            r=client.post(furl+'/parameters',json={'target':'G3','max_features':65})
            record('FastAPI typed parameter upper bound',r.status_code,422,'real JSON request with max_features outside 1..64')
            r=client.post(furl+'/upload',files={'file':('oversize.csv',b'x'*(MAX_FILE_BYTES+1),'text/csv')},data={'target':'G3'})
            record('FastAPI oversize file',r.status_code,413,'real multipart fixture, 3500001 file bytes; not analytical data')
            for name,url in [('native',nurl),('FastAPI',furl)]:
                r=client.get(url+'/download')
                record(name+' download attachment','attachment' in r.headers.get('content-disposition',''),True,'localhost HTTP GET and response headers')
        outcome={'scope':'real localhost HTTP probes; no Vercel request or production API tested',
                 'csv_source':'student development rows only','checks':checks,'passed_checks':len(checks),
                 'native_scope':'raw CSV body, manual parameter validation and attachment response; multipart not implemented',
                 'fastapi_scope':'multipart upload, typed JSON/form parameters, errors and attachment response',
                 'no_model_analysis':True,'server_cleanup':'both stopped after probes'}
        out=root/'artifacts/feasibility/http-probes.json';out.write_text(json.dumps(outcome,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'passed_checks':len(checks),'scope':outcome['scope']}))
    finally:
        native.shutdown();native.server_close();server.should_exit=True;ft.join(timeout=10);sock.close();nt.join(timeout=5)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args();main(args.root.resolve())
