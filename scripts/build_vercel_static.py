"""Copy only web/ assets into Vercel public/ and stamp a reproducible release.
No external writes, dependency installs, or analysis recomputation.
"""
from pathlib import Path
import hashlib,json,shutil,tomllib

ROOT=Path(__file__).resolve().parents[1]
STATIC=ROOT/'web'
PUBLIC=ROOT/'public'
EXTENSIONS={'.html','.css','.mjs','.svg','.json','.pdf','.md','.txt'}

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    project=tomllib.loads((ROOT/'pyproject.toml').read_text()).get('project',{})
    expected=[line.strip() for line in (ROOT/'requirements.txt').read_text().splitlines() if line.strip() and not line.lstrip().startswith('#')]
    if project.get('dependencies')!=expected:
        raise ValueError('pyproject.toml project.dependencies must exactly match requirements.txt; Vercel prioritizes pyproject.')
    if project.get('requires-python')!='~=3.12.0':
        raise ValueError('Deployment must use the validated Python 3.12.x runtime.')
    entries=[]
    for p in sorted(STATIC.rglob('*')):
        if p.is_symlink():raise ValueError('Static symlink is not allowed: '+str(p.relative_to(ROOT)))
        if not p.is_file():continue
        if p.suffix.lower() not in EXTENSIONS or any(x.startswith('.') for x in p.relative_to(STATIC).parts):
            raise ValueError('Unexpected static file: '+str(p.relative_to(ROOT)))
        entries.append({'path':p.relative_to(STATIC).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)})
    assert entries and (STATIC/'index.html').is_file()
    expected={x['path'] for x in entries}|{'release.json'}
    if PUBLIC.is_symlink():raise ValueError('public/ cannot be a symlink')
    if PUBLIC.exists():
        existing={p.relative_to(PUBLIC).as_posix() for p in PUBLIC.rglob('*') if p.is_file()}
        extra=existing-expected
        if extra:raise ValueError('Unexpected generated files; review before removing: '+str(sorted(extra)))
    code=[]
    for p in sorted([ROOT/'vercel_app.py',ROOT/'pyproject.toml',ROOT/'vercel.json',ROOT/'requirements.txt',ROOT/'.python-version',ROOT/'scripts/build_vercel_static.py',*ROOT.glob('l7_analysis/*.py'),*ROOT.glob('l7_service/*.py')]):
        code.append({'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p)})
    payload={'schema_version':'1.0','frozen_selection_sha256':'3a4fec9047f6e08b4eace272bd2f43d7fb4be1fb8356525549340561f15425f3','static_files':entries,'runtime_sources':code}
    payload['release_id']=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    PUBLIC.mkdir(exist_ok=True)
    for entry in entries:
        p=PUBLIC/entry['path'];p.parent.mkdir(parents=True,exist_ok=True)
        if not p.exists() or digest(p)!=entry['sha256']:shutil.copyfile(STATIC/entry['path'],p)
    (PUBLIC/'release.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'release_id':payload['release_id'],'files':len(entries),'static_bytes':sum(x['bytes'] for x in entries),'output':'public/'},ensure_ascii=False))

if __name__=='__main__':main()
