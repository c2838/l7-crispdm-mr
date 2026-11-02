"""Combined static website + real custom analysis API, loopback only."""
from pathlib import Path
import argparse,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if __name__=='__main__':
    import uvicorn
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8768);a=p.parse_args()
    print(f'Lesson 7 custom-analysis preview: http://127.0.0.1:{a.port}/',flush=True)
    uvicorn.run('app:app',host='127.0.0.1',port=a.port,access_log=False,log_level='warning')
