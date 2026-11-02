"""Independent development-model and exported-site integrity checks."""
from pathlib import Path
import argparse,json,hashlib,os,sys
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from scipy import stats
from sklearn.linear_model import LinearRegression
from l7_analysis.data import SCENARIOS,load_development
from l7_analysis.preprocessing import FrameEncoder
from l7_analysis.selection import folds_for
from threadpoolctl import threadpool_limits
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main(root):
    checks=[];unique=0;ols_count=0
    def check(name,passed,method):
        checks.append({'name':name,'passed':bool(passed),'expected':True,'actual':bool(passed),'method':method});assert passed,name
    manifest=read(root/'artifacts/analysis/website/export-manifest.json')
    check('protected model and heldout files unchanged',all(sha(root/p)==h for p,h in manifest['protected_sha256'].items()),'188 SHA-256 references from before Stage 5')
    check('exports match manifest',all(sha(root/p)==h for p,h in manifest['export_sha256'].items()),'every public JSON byte fingerprint')
    check('export source fingerprints unchanged',all(sha(root/p)==h for p,h in manifest['source_sha256'].items()),'export scripts and all numerical core modules')
    raw=read(root/'artifacts/reference/datasets-manifest.json')
    check('raw and processed source values unchanged',all(sha(root/f['path'])==f['sha256'] for ds in raw['datasets'] for f in ds['raw_files']) and all(sha(root/f['path'])==f['sha256'] for f in raw['processed_files']),'Stage 1 source manifest')
    with threadpool_limits(limits=1):
        for s in SCENARIOS:
            frame,ids,cfg,source=load_development(root,s);case=read(root/'web/data'/f'{s}.json')
            original=read(root/'artifacts/analysis/models'/s/'result.json');cv={e['id']:e for e in original['cv_results']}
            frozen=read(root/'artifacts/analysis/evaluation'/s/'evaluation.json');by_frozen={m['candidate_id']:m for m in frozen['models']}
            y=frame[cfg.target].to_numpy(dtype=float);yr=np.log(y) if cfg.target_transform=='log' else y
            eqs=set();winners=0
            check(s+' candidate coverage',len(case['candidates'])==sum(e['status']=='completed' for e in original['cv_results']),'all predeclared, completed Stage 3 candidates')
            for card in case['candidates']:
                d=read(root/'web'/card['detail']);a=d['artifact'];name=s+'/'+card['id']
                check(name+' CV and model binding',card['cv']==cv[card['id']]['cv'] and a['candidate_id']==card['id'] and a['dataset_id']==s and len(a['selected_keys'])==card['selected_count'],'source Stage 3 CV, actual model ID and field count')
                if card['frozen_winner']:
                    expected=by_frozen[card['id']];winners+=1
                    check(name+' frozen details preserved',d['frozen']==expected and a==read(root/expected['model_path']),'exact object comparison to original model and evaluation')
                else:check(name+' no additional test scoring',d['frozen'] is None and 'heldout_plot' not in d and card['test'] is None,'nonwinner has development/CV only')
                spec=d['inference']
                if not spec:continue
                ols_count+=1
                if spec['model_equation_sha256'] in eqs:continue
                eqs.add(spec['model_equation_sha256']);unique+=1
                encoder=FrameEncoder.from_spec(a['preprocessor']);Z,_=encoder.transform(frame,a['selected_keys']);X=np.column_stack([np.ones(len(frame)),Z]);q=X.shape[1]
                beta=np.linalg.lstsq(X,yr,rcond=None)[0];inverse=np.linalg.inv(X.T@X);res=yr-X@beta;sigma2=res@res/(len(y)-q)
                classical=inverse*sigma2;h=np.einsum('ij,jk,ik->i',X,inverse,X);hc3=inverse@((X.T*(res/(1-h))**2)@X)@inverse
                check(name+' independent coefficients and covariance',np.allclose(beta,np.r_[a['model']['intercept'],a['model']['coefficients']],rtol=1e-7,atol=1e-7) and np.allclose(classical,spec['covariance_classical'],rtol=1e-7,atol=1e-8) and np.allclose(hc3,spec['covariance_hc3'],rtol=1e-7,atol=1e-8),'full development numpy least-squares, inverse and explicit HC3 sandwich')
                pred=X@beta
                if cfg.target_transform=='log':pred=np.exp(pred)
                dm=d['development_metrics'];den=np.square(y-y.mean()).sum();errors=y-pred
                check(name+' development fit metrics',np.isclose(np.mean(abs(errors)),dm['mae']) and np.isclose(np.mean(errors**2),dm['mse']) and np.isclose(1-np.square(errors).sum()/den,dm['r2']),'independent full-development residual aggregation')
                sample=np.linspace(0,len(frame)-1,min(300,len(frame)),dtype=int);V=X[sample];location=V@beta;t=stats.t.ppf(.975,len(y)-q)
                half=t*np.sqrt(np.maximum(0,np.einsum('ij,jk,ik->i',V,classical,V))+sigma2)
                lower,upper=location-half,location+half
                if cfg.target_transform=='log':lower,upper=np.exp(lower),np.exp(upper)
                display=d['development_plot']['rows']
                check(name+' development display PI',np.allclose(lower,display['observation_pi_lower'],rtol=1e-7,atol=1e-7) and np.allclose(upper,display['observation_pi_upper'],rtol=1e-7,atol=1e-7) and len(display['actual'])<=300,'independent Student-t PI on exact displayed development rows')
            check(s+' nine frozen winners and unchanged representative',winners==9 and case['representative_id']==frozen['frozen_representative_id'],'all methods retain their original evaluation')
            # Independently replay one learning-curve fold plus all train/validation separation.
            Xraw=frame[original['input_fields']]
            for fraction in [.1,.25,.5,.75,1.]:
                for fi,(tr,va) in enumerate(folds_for(Xraw,3,73)):
                    subset=np.random.default_rng(730+fi).permutation(tr)[:max(30,int(len(tr)*fraction))]
                    assert not set(subset)&set(va)
                    if fraction!=.1 or fi!=0:continue
                    enc=FrameEncoder(cfg.categorical);zt=enc.fit_transform(Xraw.iloc[subset]);zv,_=enc.transform(Xraw.iloc[va])
                    estimator=LinearRegression().fit(zt,yr[subset]);pr=estimator.predict(zv)
                    if cfg.target_transform=='log':pr=np.exp(pr)
                    expected=case['learning_curve'][0]['records'][0]
                    check(s+' learning curve independent validation fold',len(subset)==expected['training_rows'] and np.isclose(np.mean((y[va]-pr)**2),expected['validation']['mse'],rtol=1e-8),'sklearn direct OLS, independently reconstructed subset and preprocessing, no test')
            check(s+' all learning subsets isolated',True,'reconstructed every 3-fold subset at five sample fractions and asserted no overlap')
    check('488 candidates and 424 OLS interval displays',sum(manifest['counts'].values())==488 and ols_count==424,'actual exported model counts')
    result={'status':'passed','checks':len(checks),'ols_candidates':ols_count,'unique_ols_equations':unique,'check_results':checks,
            'scope':'Independent development-only coefficient/covariance/PI, exact CV/frozen bindings and source integrity.',
            'limits':['No new holdout scoring, no public API or Vercel execution.','Statistical assumptions and future interval coverage are not established by software agreement.']}
    (root/'artifacts/validation/stage5-data.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['status','checks','ols_candidates','unique_ols_equations']}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();main(a.root.resolve())
