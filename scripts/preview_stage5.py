"""Loopback-only static preview with development cache disabled."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import argparse

class PreviewHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        super().end_headers()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8767);a=p.parse_args()
    directory=Path(__file__).resolve().parents[1]/'web'
    server=ThreadingHTTPServer(('127.0.0.1',a.port),partial(PreviewHandler,directory=str(directory)))
    print(f'Lesson 7 local preview: http://127.0.0.1:{a.port}/',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
