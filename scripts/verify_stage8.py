"""Actual local HTTP validation of packaged source; no cloud operations."""
from pathlib import Path
import json,hashlib,sys,time,zipfile,subprocess,os,re,tomllib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
import httpx,numpy as np
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from sklearn.model_selection import GroupShuffleSplit
from l7_analysis.models import predict_artifact
from l7_service.ingest import parse_csv

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(rel):return json.loads((ROOT/rel).read_text())
def save(rel,value):
    p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    checks=[]
    def check(name,passed,evidence=None):
        checks.append({'name':name,'passed':bool(passed),'evidence':evidence});assert passed,name
    package=load('artifacts/validation/stage8-package.json');source=ROOT/package['source_directory'];manifest=json.loads((source.parent/'manifest.json').read_text())
    check('all export files match explicit original SHA',all(sha(source/f['path'])==f['sha256'] for f in manifest['github_files']),len(manifest['github_files']))
    check('no single Git file exceeds100MB',all(f['bytes']<100_000_000 for f in manifest['github_files']),max(f['bytes'] for f in manifest['github_files']))
    forbidden=['docs/notebooklm/received/','reports/source/transcripts/','artifacts/history/','reports/tmp/','.env','data/raw/','data/processed/']
    check('publication manifest excludes local/private paths',all(not any(f['path'].startswith(x) for x in forbidden) for f in manifest['github_files']))
    config=load('vercel.json');schema=load('artifacts/validation/stage8-official-schema.json')
    check('all config keys are official schema keys',set(config)<=set(schema['properties']))
    check('framework enum supports fastapi',config['framework'] in schema['properties']['framework']['enum'])
    fs=schema['properties']['functions']['patternProperties']['^.{1,256}$']['properties']
    check('Function options are official schema keys',set(config['functions']['vercel_app.py'])<=set(fs))
    check('single app entrypoint and platform limit300',tomllib.loads((source/'pyproject.toml').read_text())['tool']['vercel']['entrypoint']=='vercel_app:app' and config['functions']['vercel_app.py']['maxDuration']==300)
    check('Fluid enabled and Python3.12 pinned',config['fluid'] is True and (source/'.python-version').read_text().strip()=='3.12')
    expected=[x.strip() for x in (source/'requirements.txt').read_text().splitlines() if x.strip() and not x.lstrip().startswith('#')]
    check('Vercel pyproject declares all36 exact runtime pins',tomllib.loads((source/'pyproject.toml').read_text())['project']['dependencies']==expected and len(expected)==36)
    check('original requirements lock unchanged',sha(ROOT/'requirements.txt')==sha(ROOT/'artifacts/history/stage8-before/requirements.txt') if (ROOT/'artifacts/history/stage8-before/requirements.txt').exists() else sha(ROOT/'requirements.txt')==sha(source/'requirements.txt'))
    release=json.loads((source/'public/release.json').read_text());expected_release=load('public/release.json')
    check('packaged build same release identity',release==expected_release,release['release_id'])
    # API must import without web/public at runtime, as both are Function-excluded.
    isolated=ROOT/'artifacts/deployment/api-import-check';isolated.mkdir(exist_ok=True)
    import shutil
    for name in ['vercel_app.py','l7_analysis','l7_service']:
        s=source/name;d=isolated/name
        if s.is_dir():shutil.copytree(s,d,dirs_exist_ok=True)
        else:shutil.copyfile(s,d)
    probe="import time,resource,json;t=time.perf_counter();import vercel_app;print(json.dumps({'import_s':time.perf_counter()-t,'maxrss_macos_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'routes':[r.path for r in vercel_app.app.routes]}))"
    env=os.environ.copy();env.pop('PYTHONPATH',None)
    p=subprocess.run([sys.executable,'-B','-c',probe],cwd=isolated,env=env,text=True,capture_output=True,timeout=45)
    check('isolated API imports without static/data/artifacts',p.returncode==0,p.stderr[-500:] if p.returncode else json.loads(p.stdout))
    startup=json.loads(p.stdout)
    check('API has no root static mount','/' not in startup['routes'])

    wheels=[]
    for f in sorted(Path('/private/tmp/l7-stage8-linux-wheels').glob('*.whl')):
        with zipfile.ZipFile(f) as z:expanded=sum(x.file_size for x in z.infolist())
        wheels.append({'name':f.name,'compressed_bytes':f.stat().st_size,'uncompressed_bytes':expanded,'sha256':sha(f)})
    total=sum(w['uncompressed_bytes'] for w in wheels)
    check('all36 pinned Linux wheels available',len(wheels)==36,len(wheels))
    check('wheel contents below500MB before Vercel overhead',total<500_000_000,total)
    save('artifacts/validation/stage8-linux-wheels.json',{'status':'downloaded_and_measured_not_cloud_build','python':'CPython3.12','target':'manylinux2014 and manylinux_2_28 x86_64','wheels':wheels,'compressed_bytes':sum(w['compressed_bytes'] for w in wheels),'uncompressed_bytes':total,'limitation':'Wheel ZIP contents measured on macOS, not executed on Linux; Vercel .pyc/runtime overhead and actual bundle remain to be measured after user deploys.'})
    http=[];start=time.perf_counter()
    with httpx.Client(base_url='http://127.0.0.1:8769',timeout=240,trust_env=False) as client:
        for f in release['static_files']:
            response=client.get('/'+f['path']);ok=response.status_code==200 and hashlib.sha256(response.content).hexdigest()==f['sha256']
            http.append({'path':f['path'],'status_code':response.status_code,'bytes':len(response.content),'matches_sha':ok});assert ok,f['path']
        check('all509 static assets delivered byte-exact',len(http)==509 and all(x['matches_sha'] for x in http),len(http))
        response=client.get('/release.json');check('release stamp served',response.status_code==200 and response.json()==release)
        check('home served by local CDN approximation',client.get('/').content==(source/'public/index.html').read_bytes())
        check('API health through packaged entrypoint',client.get('/api/health').json()['pipeline']=='custom-v1')
        for path in ['/downloads/Lecture6_conversation_snapshot.pdf','/docs/notebooklm/received/gpu-original.txt','/artifacts/analysis/models/selection-freeze.json']:
            check('private or retired URL404 '+path,client.get(path).status_code==404)
        data=(ROOT/'artifacts/validation/fixtures/stage6/parkinsons-updrs.csv').read_bytes();fingerprint=hashlib.sha256(data).hexdigest()
        url='https://archive.ics.uci.edu/ml/machine-learning-databases/parkinsons/telemonitoring/parkinsons_updrs.data'
        response=client.post('/api/data/url',json={'url':url})
        check('real HTTPS public CSV via packaged API',response.status_code==200 and response.content==data and response.headers['x-dataset-sha256']==fingerprint)
        for route,body in [('upload',data),('url',response.content)]:
            r=client.post('/api/data/preview',files={'file':('third-public.csv',body,'text/csv')})
            check(route+' preview5875 rows',r.status_code==200 and r.json()['source']['rows']==5875)
        opts={'target':'total_UPDRS','exclude':['age','sex','test_time','motor_UPDRS'],'categorical':[],'group':'subject#','target_transform':'identity','seed':0}
        results=[]
        for method in ['baseline','kbest','rfe','sfs','lasso_select','elasticnet_select']:
            r=client.post('/api/analyze/'+method,files={'file':('third-public.csv',data,'text/csv')},data={'options':json.dumps(opts),'sha256':fingerprint})
            check(method+' packaged actual HTTP completed',r.status_code==200 and r.json()['status']=='completed',{'http':r.status_code,'bytes':len(r.content)})
            result=r.json();results.append(result);check(method+' payload below3MB',len(r.content)<3_000_000)
            save('artifacts/validation/stage8-http/'+method+'.json',result)
            print(json.dumps({'method':method,'models':len(result['models']),'elapsed_s':result['elapsed_s']}),flush=True)
        check('stateless analysis IDs and split consistent',len({x['analysis_id'] for x in results})==1 and all(x['split']==results[0]['split'] for x in results))
        models=[m for x in results for m in x['models']];check('all9 actual models',len(models)==9)
        frame,_=parse_csv(data);tr,te=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=0).split(frame,groups=frame['subject#']))
        check('independent patient group split',len(tr)==4623 and len(te)==1252 and not set(frame.iloc[tr]['subject#'])&set(frame.iloc[te]['subject#']))
        y=frame.iloc[te][opts['target']].to_numpy(dtype=float)
        for model in models:
            pred,_=predict_artifact(model['artifact'],frame.iloc[te]);metrics={'mae':mean_absolute_error(y,pred),'mse':mean_squared_error(y,pred),'rmse':np.sqrt(mean_squared_error(y,pred)),'r2':r2_score(y,pred)}
            check(model['method']+' independent all-test metric replay',all(np.isclose(v,model['test_metrics'][k],rtol=1e-9,atol=1e-9) for k,v in metrics.items()))
        r=client.post('/api/data/url',json={'url':'https://127.0.0.1/private.csv'});check('private URL rejected',r.status_code==422 and r.json()['error']['code']=='private_url')
        r=client.post('/api/data/preview',files={'file':('x.csv',data,'text/csv')},headers={'Origin':'https://unrelated.example'});check('cross-origin upload rejected',r.status_code==403)
    for group in ['protected_sha256','export_sha256','source_sha256']:
        entries=load('artifacts/analysis/website/export-manifest.json')[group]
        check(group+' unchanged',all(sha(ROOT/p)==h for p,h in entries.items()),len(entries))
    save('artifacts/validation/stage8-local.json',{'status':'passed_local_packaged_source','checks':checks,'passed_checks':len(checks),'static_http_files':len(http),'static_http':http,'release_id':release['release_id'],'source_package_id':package['package_id'],'elapsed_http_s':time.perf_counter()-start,'local_api_import':startup,'limitations':['Actual localhost HTTP from exported source, with CDN routing approximated locally. Not Vercel build/runtime/latency proof.','Linux wheels downloaded and ZIP size measured, not Linux execution.','Chrome login and platform operations are user-owned; actual GitHub/Vercel account and region not yet verified.','Public upload/URL/browser/cold-start/concurrency and bonus evidence remain pending deployment.']})
    print(json.dumps({'checks':len(checks),'static_files':len(http),'models':len(models),'wheel_uncompressed_bytes':total,'release_id':release['release_id']}))

if __name__=='__main__':main()
