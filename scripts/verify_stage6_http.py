"""Real localhost HTTP + real public HTTPS source, then independent metric/interval replay."""
from pathlib import Path
import argparse,json,hashlib,sys,os,time
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import httpx,numpy as np,pandas as pd
from scipy import stats
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from sklearn.model_selection import GroupShuffleSplit
from l7_service.contracts import Options,json_bytes
from l7_service.ingest import parse_csv,prepare
from l7_service.analysis import run_method
from l7_analysis.models import predict_artifact
from l7_analysis.inference import predict_with_intervals,design_for
URL='https://archive.ics.uci.edu/ml/machine-learning-databases/parkinsons/telemonitoring/parkinsons_updrs.data'
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main(root,origin):
    fixture=root/'artifacts/validation/fixtures/stage6/parkinsons-updrs.csv';data=fixture.read_bytes();out=root/'artifacts/validation/stage6-http'
    options={'target':'total_UPDRS','exclude':['age','sex','test_time','motor_UPDRS'],'categorical':[],'group':'subject#','target_transform':'identity','seed':0}
    checks=[];results=[];fixtures=[];start=time.perf_counter()
    def check(name,passed,method):checks.append({'name':name,'passed':bool(passed),'method':method});assert passed,name
    with httpx.Client(base_url=origin,timeout=240,trust_env=False) as client:
        health=client.get('/api/health');check('actual HTTP health',health.status_code==200,'live localhost request')
        response=client.post('/api/data/url',json={'url':URL});check('actual public HTTPS through API',response.status_code==200,'API fetch uses actual public DNS, pinned IP and verified TLS')
        check('URL body equals uploaded fixture bytes',response.content==data and response.headers['x-dataset-sha256']==sha(data),'byte comparison and SHA-256')
        for route,body in [('upload',data),('url',response.content)]:
            p=client.post('/api/data/preview',files={'file':('public-validation.csv',body,'text/csv')})
            check(route+' actual preview',p.status_code==200 and p.json()['source']['rows']==5875 and p.json()['source']['sha256']==sha(data),'real multipart HTTP preview; no preset JSON')
        for method in ['baseline','kbest','rfe','sfs','lasso_select','elasticnet_select']:
            response=client.post('/api/analyze/'+method,files={'file':('public-validation.csv',data,'text/csv')},data={'options':json.dumps(options),'sha256':sha(data)})
            check(method+' actual HTTP success',response.status_code==200,'real shared-engine execution, not a mock')
            result=response.json();check(method+' complete status',result['status']=='completed','no timeout or partial result relabelled as complete')
            check(method+' response bounded',len(response.content)<=3_000_000,'actual serialized HTTP response bytes')
            save(out/(method+'.json'),result);results.append(result)
            print(json.dumps({'method':method,'status':result['status'],'models':len(result['models']),'elapsed_s':result['elapsed_s'],'bytes':len(response.content)}),flush=True)
    check('all six stateless requests bound to identical data/options/split',len({r['analysis_id'] for r in results})==1 and all(r['split']==results[0]['split'] for r in results),'independent HTTP requests carry same bytes/settings; no cross-instance memory dependency')
    frame,source=parse_csv(data);training,test,ti,vi,fields,split,warnings=prepare(frame,source,Options(**options))
    independent_train,independent_test=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=0).split(frame,groups=frame['subject#']))
    check('independent patient holdout split',np.array_equal(ti,independent_train) and np.array_equal(vi,independent_test) and not set(frame['subject#'].iloc[ti])&set(frame['subject#'].iloc[vi]),'sklearn direct GroupShuffleSplit with original patient IDs')
    all_models=[m for r in results for m in r['models']];check('nine actual models',len(all_models)==9,'four baselines plus five selection models')
    direct=run_method(frame,source,Options(**options),'kbest');actual=next(r for r in results if r['request_method']=='kbest')
    check('CLI shared core matches HTTP CV and chosen model',direct['models'][0]['artifact']==actual['models'][0]['artifact'] and direct['models'][0]['cv']==actual['models'][0]['cv'],'actual separate direct core execution with same bytes/settings')
    y=test[options['target']].to_numpy(dtype=float)
    for m in all_models:
        artifact=m['artifact'];pred,_=predict_artifact(artifact,test)
        metrics={'mae':mean_absolute_error(y,pred),'mse':mean_squared_error(y,pred),'rmse':np.sqrt(mean_squared_error(y,pred)),'r2':r2_score(y,pred)}
        check(m['method']+' independent full-test metrics',all(np.isclose(v,m['test_metrics'][k],rtol=1e-9,atol=1e-9) for k,v in metrics.items()),'sklearn metrics on every retained patient test record')
        expected={'prediction':float(predict_artifact(artifact,pd.DataFrame([m['defaults']]))[0][0])}
        if m['inference']:
            spec=m['inference'];X,_=design_for(artifact,training);V,_=design_for(artifact,test);beta=np.linalg.lstsq(X,training[options['target']],rcond=None)[0]
            pinv=np.linalg.pinv(X);residual=training[options['target']].to_numpy()-X@beta;df=len(X)-X.shape[1];variance=float(residual@residual/df);cov=pinv@pinv.T*variance
            check(m['method']+' independent coefficients and classical covariance',np.allclose(beta,spec['coefficients_with_intercept'],rtol=1e-6,atol=1e-7) and np.allclose(cov,spec['covariance_classical'],rtol=1e-6,atol=1e-7),'numpy least-squares and pseudoinverse covariance; stable for ill-conditioned voice measures')
            location=V@beta;half=stats.t.ppf(.975,df)*np.sqrt(np.maximum(0,np.einsum('ij,jk,ik->i',V,cov,V))+variance)
            coverage=float(np.mean((y>=location-half)&(y<=location+half)))
            check(m['method']+' full-test PI coverage',np.isclose(coverage,m['interval_summary']['observation_pi_coverage']),'independent Student-t observation PI, all test rows')
            single,_=predict_with_intervals(artifact,spec,pd.DataFrame([m['defaults']]))
            expected.update({k:float(single.iloc[0][k]) for k in ['location_ci_lower','location_ci_upper','observation_pi_lower','observation_pi_upper','location_ci_hc3_lower','location_ci_hc3_upper']})
        fixtures.append({'artifact':artifact,'inference':m['inference'],'forms':m['forms'],'input':m['defaults'],'expected':expected,'method':m['method']})
    save(root/'artifacts/validation/stage6-prediction-fixtures.json',fixtures)
    save(root/'artifacts/validation/stage6-http.json',{'status':'passed','checks':checks,'passed_checks':len(checks),'models':len(all_models),'split':split,'source_sha256':source['sha256'],'real_public_url':URL,'elapsed_s':time.perf_counter()-start,
       'scope':'Live localhost HTTP, actual external CSV, source equality, CLI equivalence and independent sklearn/numpy metrics/PI.',
       'limitations':['Not public Vercel execution.','Third data are validation material, not an added preset or a saved user upload.','Good software agreement is not proof of clinical suitability or OLS assumptions.']})
    print(json.dumps({'status':'passed','checks':len(checks),'models':len(all_models)}),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--origin',default='http://127.0.0.1:8768');a=p.parse_args();main(a.root.resolve(),a.origin)
