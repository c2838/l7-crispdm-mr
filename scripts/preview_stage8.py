"""Local-only CDN routing approximation around the deployment API entrypoint.
This proves the source export runs locally, not that Vercel routing/build succeeded.
"""
from pathlib import Path
import argparse,sys

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8769);parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);args=parser.parse_args()
    root=args.root.resolve();sys.path.insert(0,str(root))
    from vercel_app import app as api
    from starlette.staticfiles import StaticFiles
    import uvicorn
    static=StaticFiles(directory=str(root/'public'),html=True)
    async def combined(scope,receive,send):
        if scope['type']!='http' or scope.get('path','').startswith('/api/'):
            return await api(scope,receive,send)
        try:return await static(scope,receive,send)
        except Exception as exc:
            from starlette.exceptions import HTTPException
            if not isinstance(exc,HTTPException):raise
            return await api(scope,receive,send)
    print(f'Packaged source local preview: http://127.0.0.1:{args.port}/ (CDN route approximation only)',flush=True)
    uvicorn.run(combined,host='127.0.0.1',port=args.port,access_log=False,log_level='warning')

if __name__=='__main__':main()
