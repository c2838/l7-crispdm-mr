"""Independent formal-data checks; never score the reserved final test."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import sys

os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler,OneHotEncoder
from sklearn.linear_model import LinearRegression
from l7_analysis import predict_artifact
from l7_analysis.config import OLS_METHODS
from l7_analysis.data import SCENARIOS,load_development
from l7_analysis.preprocessing import FrameEncoder

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write_json(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def verify(root):
    checks=[];frozen=[];summaries=[];coefs=[];stability=[]
    def check(name,passed,method):
        checks.append({'name':name,'expected':True,'actual':bool(passed),'passed':bool(passed),'method':method})
        assert passed,name
    for scenario in SCENARIOS:
        directory=root/'artifacts/analysis/models'/scenario
        result=json.loads((directory/'result.json').read_text());frame,ids,cfg,source=load_development(root,scenario)
        X=frame.drop(columns=[cfg.target,*cfg.exclude]);y=frame[cfg.target].to_numpy()
        check(scenario+' completed all planned methods',result['status']=='completed' and set(result['completed_methods'])==set(cfg.methods),'actual completed result and exported model map')
        check(scenario+' source manifest and final-test exclusion',result['source']==source and source['final_test_rows_parsed_for_modeling']==0,'source loader verifies hashes and skips final-test data records')
        check(scenario+' exact engine source version',all(sha(root/path)==digest for path,digest in result['execution']['engine_code_sha256'].items()),'SHA-256 each executed engine module versus current source')
        assignments=pd.read_csv(directory/'cv-fold-assignments.csv')
        check(scenario+' development row identities',np.array_equal(assignments.source_row_index_0_based.to_numpy(),ids),'saved source row index mapping equals fixed development set')
        check(scenario+' all rows validated once',len(assignments)==len(frame) and set(assignments.validation_fold)==set(range(5)) and assignments.development_position.is_unique,'assignment coverage and five-fold labels')
        complete=[c for c in result['cv_results'] if c['status']=='completed']
        check(scenario+' every grid candidate completed five folds',len(complete)==len(result['cv_results']) and all(len(c['folds'])==5 for c in complete),'no hidden failed candidates or partial fold averages')
        check(scenario+' entire requested k range executed',result['k_grid']==list(range(1,min(result['encoded_fold_counts'])+1)),'not a single-k prototype')
        check(scenario+' representative chosen only from OLS family CV',result['representative_candidate_id']==min((c for c in complete if c['method'] in OLS_METHODS),key=lambda c:(c['cv']['rmse'],c['mean_selected_count'],c['id']))['id'],'independently sort completed candidate CV RMSE and complexity')
        # Independent sklearn preprocessing and OLS baseline in the saved folds.
        predictions=np.empty(len(y),dtype=float)
        cat=list(X.select_dtypes(exclude='number'));num=[c for c in X if c not in cat]
        for fold in range(5):
            va=np.flatnonzero(assignments.validation_fold.to_numpy()==fold);tr=np.flatnonzero(assignments.validation_fold.to_numpy()!=fold)
            pre=ColumnTransformer([('num',SimpleImputer(strategy='median'),num),
                ('cat',make_pipeline(SimpleImputer(strategy='most_frequent'),OneHotEncoder(drop='first',handle_unknown='ignore',sparse_output=False)),cat)],sparse_threshold=0)
            estimator=make_pipeline(pre,StandardScaler(),LinearRegression())
            estimator.fit(X.iloc[tr],np.log(y[tr]) if cfg.target_transform=='log' else y[tr])
            pred=estimator.predict(X.iloc[va]);predictions[va]=np.exp(pred) if cfg.target_transform=='log' else pred
        baseline=next(c for c in complete if c['id']=='ols')
        rmse=float(np.sqrt(np.mean((y-predictions)**2)))
        check(scenario+' independent baseline CV agreement',abs(rmse-baseline['cv']['rmse'])<1e-7,'separate sklearn imputer/OneHotEncoder/StandardScaler/OLS in saved folds; RMSE absolute tolerance 1e-7')
        for candidate in complete:
            n=sum(f['metrics']['n'] for f in candidate['folds'])
            mse=sum(f['metrics']['n']*f['metrics']['mse'] for f in candidate['folds'])/n
            check(scenario+' pooled metrics '+candidate['id'],abs(np.sqrt(mse)-candidate['cv']['rmse'])<1e-10 and n==len(frame),'independent weighted fold MSE aggregation; all development rows covered')
        for method,cid in result['method_winner_ids'].items():
            artifact_path=directory/result['model_files'][cid];artifact=json.loads(artifact_path.read_text())
            best=next(c for c in complete if c['id']==cid)
            check(scenario+' exported model identity '+method,artifact['fit_rows']==len(frame) and artifact['candidate_id']==cid and len(artifact['selected_keys'])==len(artifact['model']['coefficients']),'actual JSON model dimensions and full development refit')
            pred,notes=predict_artifact(artifact,X)
            check(scenario+' finite full development replay '+method,np.isfinite(pred).all(),'replay exported JSON on all development records, no fitting or final-test scores')
            if method in OLS_METHODS:
                enc=FrameEncoder.from_spec(artifact['preprocessor']);Z=enc.transform(X,artifact['selected_keys'])[0]
                design=np.column_stack([np.ones(len(X)),Z])
                independent=np.linalg.lstsq(design,np.log(y) if cfg.target_transform=='log' else y,rcond=None)[0]
                expected=design@independent
                if cfg.target_transform=='log':expected=np.exp(expected)
                check(scenario+' independent selected OLS solve '+method,np.allclose(pred,expected,rtol=1e-7,atol=1e-7),'numpy least-squares solve of exported selected design; tolerance 1e-7')
            summaries.append({'scenario':scenario,'method':method,'candidate_id':cid,'cv_rmse':best['cv']['rmse'],
              'cv_mae':best['cv']['mae'],'cv_r2':best['cv']['r2'],'cv_fold_rmse_std':best['cv']['fold_rmse_std'],
              'selected_encoded_refit':len(artifact['selected_keys']),'selected_raw_refit':len(artifact['selected_raw_fields']),
              'representative':cid==result['representative_candidate_id']})
            lookup={c['key']:i for i,c in enumerate(artifact['preprocessor']['columns'])}
            coef=np.asarray(artifact['model']['coefficients']);positions=[lookup[k] for k in artifact['selected_keys']]
            scale=np.asarray(artifact['preprocessor']['scale'])[positions];center=np.asarray(artifact['preprocessor']['center'])[positions]
            raw_coef=coef/scale if len(coef) else coef
            raw_intercept=float(artifact['model']['intercept']-raw_coef@center)
            coefs.append({'scenario':scenario,'method':method,'candidate_id':cid,'encoded_key':'(intercept)',
              'raw_field':'','category':'','standardized_design_coefficient':artifact['model']['intercept'],
              'unscaled_encoded_coefficient':raw_intercept,'response_scale':'log(ms)' if cfg.target_transform=='log' else 'source target units'})
            for column,sc,rc in zip(artifact['selected_columns'],coef,raw_coef):
                coefs.append({'scenario':scenario,'method':method,'candidate_id':cid,'encoded_key':column['key'],
                    'raw_field':column['field'],'category':column['category'],'standardized_design_coefficient':float(sc),
                    'unscaled_encoded_coefficient':float(rc),'response_scale':'log(ms)' if cfg.target_transform=='log' else 'source target units'})
            if method in OLS_METHODS:
                all_keys=sorted(set(k for f in best['folds'] for k in f['selected_keys']))
                for key in all_keys:
                    count=sum(key in f['selected_keys'] for f in best['folds'])
                    stability.append({'scenario':scenario,'method':method,'candidate_id':cid,'encoded_key':key,
                                      'selected_folds':count,'folds':5,'frequency':count/5})
            frozen.append({'scenario':scenario,'method':method,'candidate_id':cid,
                           'model_path':str(artifact_path.relative_to(root)),'model_sha256':sha(artifact_path)})
    protected=json.loads((root/'artifacts/reference/datasets-manifest.json').read_text())
    check('raw and prepared source files unchanged',all(sha(root/r['path'])==r['sha256'] for ds in protected['datasets'] for r in ds['raw_files']) and all(sha(root/r['path'])==r['sha256'] for r in protected['processed_files']),'compare with approved Stage 1 SHA-256 manifest')
    out=root/'artifacts/analysis/models'
    pd.DataFrame(summaries).to_csv(out/'method-summary.csv',index=False)
    pd.DataFrame(coefs).to_csv(out/'coefficients.csv',index=False)
    pd.DataFrame(stability).to_csv(out/'selection-stability.csv',index=False)
    freeze={'status':'frozen_before_final_test_evaluation','selection_basis':'development CV only; do not change representatives after seeing final test',
      'models':frozen,'scenario_result_sha256':{s:sha(out/s/'result.json') for s in SCENARIOS},
      'primary_scenarios':['sgemm','student'],'supplementary_scenarios':['sgemm_log','student_background'],
      'primary_representatives':{s:json.loads((out/s/'result.json').read_text())['representative_candidate_id'] for s in ['sgemm','student']}}
    write_json(out/'selection-freeze.json',freeze)
    unit=json.loads((root/'artifacts/validation/stage3-unit.json').read_text())
    check('unit suite matches current engine',unit['passed'] and all(sha(root/p)==h for p,h in unit['engine_code_sha256'].items()),'actual unittest execution report and engine source hashes')
    report={'status':'passed_development_engine_final_test_unrevealed','checks':checks,'passed_checks':len(checks),
      'scope':'four real development scenarios; independent baseline CV and selected OLS solves; artifact replay and freeze',
      'candidate_configurations':sum(len(json.loads((out/s/'result.json').read_text())['cv_results']) for s in SCENARIOS),
      'exported_models':len(frozen),'unit_tests':{'tests':unit['tests'],'result':'passed','evidence':'artifacts/validation/stage3-unit.json; not rerun by integration verifier'},
      'limitations':['Tuning CV is not unbiased external performance.','No final-test scoring, interval coverage or full residual diagnostics yet.',
                    'Log backtransform is exp(log prediction), without arithmetic-mean smearing; mean-CI semantics need separate treatment.',
                    'No online API, Vercel execution, public deployment or third-dataset bonus proof.']}
    write_json(root/'artifacts/validation/stage3.json',report)
    print(json.dumps({'passed_checks':len(checks),'candidate_configurations':report['candidate_configurations'],'models':len(frozen),'status':report['status']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();verify(a.root.resolve())
