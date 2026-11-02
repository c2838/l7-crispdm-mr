"""Lock successful runtime dependencies and record local feasibility context."""
from pathlib import Path
import argparse
import importlib.metadata as md
import json
import platform
import subprocess
import sys
import time
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args();root=args.root.resolve()
runtime=['numpy','pandas','scipy','scikit-learn','matplotlib','statsmodels','fastapi','uvicorn','python-multipart']
seen=set()
def walk(name):
    key=canonicalize_name(name)
    if key in seen:return
    seen.add(key)
    for raw in md.requires(key) or []:
        req=Requirement(raw)
        if req.marker is None or req.marker.evaluate({'extra':''}):walk(req.name)
for name in runtime:walk(name)
runtime_lock='\n'.join(f'{name}=={md.version(name)}' for name in sorted(seen))+'\n'
(root/'requirements.txt').write_text(runtime_lock)
all_lock=subprocess.check_output([sys.executable,'-m','pip','--isolated','freeze','--disable-pip-version-check'],text=True)
(root/'requirements-dev.lock.txt').write_text(all_lock)
(root/'.python-version').write_text('3.12\n')
(root/'requirements.in').write_text('''# Runtime families; requirements.txt contains the tested exact transitive lock.
numpy>=2.2,<3
pandas>=2.2,<3
scipy>=1.15,<2
scikit-learn>=1.6,<2
matplotlib>=3.10,<4
statsmodels>=0.14.5,<0.15
fastapi>=0.116,<1
uvicorn>=0.35,<1
python-multipart>=0.0.20,<0.1
''')
site=Path(md.distribution('numpy').locate_file('')).resolve()
sizes={}
for name in sorted(seen):
    d=md.distribution(name);size=0
    for f in d.files or []:
        path=Path(d.locate_file(f))
        if path.is_file():size+=path.stat().st_size
    sizes[name]={'version':d.version,'installed_bytes_including_metadata':size}
result={'python':platform.python_version(),'executable':sys.executable,'base_prefix':sys.base_prefix,
        'prefix':sys.prefix,'independent_venv':sys.prefix!=sys.base_prefix,
        'platform':platform.platform(),'machine':platform.machine(),'processor':platform.processor(),
        'runtime_dependencies':sizes,'runtime_installed_bytes_local':sum(x['installed_bytes_including_metadata'] for x in sizes.values()),
        'dev_only_direct_packages':{'httpx':md.version('httpx'),'psutil':md.version('psutil')},
        'lock_scope':'Exact successful local Python 3.12 resolution. Linux wheels measured separately; not a Vercel deployment build.',
        'pip_check':'No broken requirements found; executed separately',
        'account_plan_basis':'User selected Hobby free-tier evaluation; actual account/project not inspected.'}
dest=root/'artifacts/feasibility/environment.json';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'independent_venv':result['independent_venv'],'runtime_packages':len(seen),
                  'local_runtime_mib':round(result['runtime_installed_bytes_local']/2**20,2)}))
