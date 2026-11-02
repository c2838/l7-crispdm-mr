"""Independent full-test metrics/interval checks with frozen-model integrity."""
from pathlib import Path
import argparse,json,hashlib,os,sys
from datetime import datetime
from zoneinfo import ZoneInfo
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from threadpoolctl import threadpool_limits
from l7_analysis.data import SCENARIOS,load_development
from l7_analysis.models import predict_artifact,response
from l7_analysis.inference import design_for,predict_with_intervals

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,v):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main(root):
    out=root/'artifacts/analysis/evaluation';manifest=json.loads((out/'evaluation-manifest.json').read_text())
    freeze_file=root/'artifacts/analysis/models/selection-freeze.json';freeze=json.loads(freeze_file.read_text())
    checks=[]
    def check(name,passed,method):
        checks.append({'name':name,'expected':True,'actual':bool(passed),'passed':bool(passed),'method':method})
        assert passed,name
    check('fixed-model evaluation completed',manifest['status']=='completed' and len(manifest['models'])==36,'actual evaluation manifest')
    check('selection freeze unchanged',sha(freeze_file)==manifest['freeze_sha256_before']==manifest['freeze_sha256_after'],'SHA-256 before and after first held-out evaluation')
    check('all 36 frozen model bytes unchanged',all(sha(root/m['model_path'])==m['model_sha256'] for m in freeze['models']),'compare every model against Stage 3 freeze')
    check('all four Stage 3 selection results unchanged',all(sha(root/'artifacts/analysis/models'/s/'result.json')==h for s,h in freeze['scenario_result_sha256'].items()),'compare selection-result hashes; no test-driven tuning')
    unit=json.loads((root/'artifacts/validation/stage4-unit.json').read_text())
    check('33 executed unit tests match current numerical source',unit['passed'] and unit['tests']==33 and all(sha(root/p)==h for p,h in unit['source_sha256'].items()),'actual unittest command and source fingerprints')
    validated_intervals=set();rep_sensitivity=0;site_cases=[]
    with threadpool_limits(limits=1):
        for scenario,info in SCENARIOS.items():
            train,train_ids,cfg,source=load_development(root,scenario)
            split=pd.read_csv(root/source['split_path']);test_ids=split.loc[split.split=='final_test','source_row_index_0_based'].to_numpy()
            allowed=set(test_ids.tolist());test=pd.read_csv(root/source['input_path'],skiprows=lambda i:i>0 and i-1 not in allowed)
            y=test[cfg.target].to_numpy();case=json.loads((out/scenario/'evaluation.json').read_text())
            check(scenario+' exact held-out row count and disjointness',len(y)==len(test_ids)==(48320 if info['letter']=='a' else 130) and not set(train_ids)&allowed,'fixed split CSV, no row removal')
            original=json.loads((root/'artifacts/analysis/models'/scenario/'result.json').read_text())
            check(scenario+' representative remains CV-frozen',case['frozen_representative_id']==original['representative_candidate_id'],'unchanged representative identity, irrespective of test ranking')
            cards=[]
            for item in case['models']:
                method=item['method'];name=scenario+'/'+method;artifact=json.loads((root/item['model_path']).read_text())
                table=pd.read_csv(root/item['predictions_path'],float_precision='round_trip')
                check(name+' full prediction table integrity',sha(root/item['predictions_path'])==item['predictions_sha256'] and np.array_equal(table.source_row_index_0_based,test_ids) and np.array_equal(table.actual,y),'gzip CSV checksum, every held-out source row and actual target')
                pred,_=predict_artifact(artifact,test)
                check(name+' frozen JSON replay',np.allclose(table.prediction,pred,rtol=1e-10,atol=1e-10),'full test batch, no model fitting')
                reference={'mae':float(mean_absolute_error(y,pred)),'mse':float(mean_squared_error(y,pred)),
                           'rmse':float(np.sqrt(mean_squared_error(y,pred))),'r2':float(r2_score(y,pred))}
                check(name+' independent sklearn metrics',all(np.isclose(reference[k],item['test_metrics'][k],rtol=1e-10,atol=1e-10) for k in reference),'independent MAE/MSE/RMSE/R2 on all held-out rows')
                plot=json.loads((root/item['interval_plot_data_path']).read_text())
                check(name+' display thinning does not remove scored rows',plot['total_test_rows']==len(y) and plot['display_rows']<=2000 and len(table)==len(y),'plot metadata versus complete prediction table')
                if item['interval_status']=='available':
                    summary=item['interval_summary'];covered=(y>=table.observation_pi_lower)&(y<=table.observation_pi_upper)
                    check(name+' full PI coverage and width',int(covered.sum())==summary['covered_count'] and np.isclose(covered.mean(),summary['observation_pi_coverage']) and np.isclose((table.observation_pi_upper-table.observation_pi_lower).mean(),summary['observation_pi_mean_width']),'all rows, no visual subsampling in metrics')
                    check(name+' no fake mean-CI coverage',summary['location_ci_coverage_against_individual_y'] is None,'individual outcomes are not the true conditional means')
                    spec=json.loads((root/item['interval_spec_path']).read_text())
                    if item['interval_spec_path'] not in validated_intervals:
                        X,_=design_for(artifact,train);V,_=design_for(artifact,test)
                        yr=response(train[cfg.target].to_numpy(dtype=float),artifact['target_transform'])
                        beta=np.linalg.lstsq(X,yr,rcond=None)[0];inverse=np.linalg.inv(X.T@X)
                        residual=yr-X@beta;df=len(yr)-X.shape[1];sigma2=float(residual@residual/df)
                        classic=inverse*sigma2;h=np.einsum('ij,jk,ik->i',X,inverse,X)
                        hc3=inverse@((X.T*(residual/(1-h))**2)@X)@inverse
                        check(name+' independent covariance and residual variance',np.allclose(classic,spec['covariance_classical'],rtol=1e-7,atol=1e-8) and np.allclose(hc3,spec['covariance_hc3'],rtol=1e-7,atol=1e-8) and np.isclose(sigma2,spec['mse_resid'],rtol=1e-9),'numpy least squares, inverse(XtX), explicit HC3 sandwich; no statsmodels covariance reuse')
                        location=V@beta;crit=stats.t.ppf(.975,df);vm=np.einsum('ij,jk,ik->i',V,classic,V);vr=np.einsum('ij,jk,ik->i',V,hc3,V)
                        hm=crit*np.sqrt(np.maximum(vm,0));hp=crit*np.sqrt(np.maximum(vm+sigma2,0));hr=crit*np.sqrt(np.maximum(vr,0))
                        curves={'location_ci_lower':location-hm,'location_ci_upper':location+hm,
                          'observation_pi_lower':location-hp,'observation_pi_upper':location+hp,
                          'location_ci_hc3_lower':location-hr,'location_ci_hc3_upper':location+hr}
                        if artifact['target_transform']=='log':curves={k:np.exp(v) for k,v in curves.items()}
                        check(name+' independent full-test CI/PI endpoints',all(np.allclose(table[k],v,rtol=1e-7,atol=1e-7) for k,v in curves.items()),'Student-t closed-form mean and observation variance; exp only for log models')
                        tiny=test.iloc[[0,len(test)//2,len(test)-1]];batch,_=predict_with_intervals(artifact,spec,tiny)
                        check(name+' single versus batch intervals',all(np.allclose(predict_with_intervals(artifact,spec,tiny.iloc[[i]])[0].to_numpy()[0],batch.to_numpy()[i],rtol=1e-9,atol=1e-9) for i in range(3)),'replay three individual rows against vectorized interval calculation')
                        validated_intervals.add(item['interval_spec_path'])
                    if item['representative_frozen']:
                        # A representative may share an equation/spec with an
                        # earlier method; still validate every representative.
                        X,_=design_for(artifact,train)
                        yr=response(train[cfg.target].to_numpy(dtype=float),artifact['target_transform'])
                        diag=json.loads((root/item['diagnostics_path']).read_text());i=diag['sensitivity']['deleted_training_position_for_sensitivity']
                        deleted=np.linalg.lstsq(np.delete(X,i,axis=0),np.delete(yr,i),rcond=None)[0]
                        check(name+' one-row influence sensitivity independently refit',np.allclose(deleted,diag['sensitivity']['coefficients_after_one_row_deletion'],rtol=1e-7,atol=1e-7) and not diag['sensitivity']['production_model_changed'],'one training-row deletion refit for diagnostic validation only; no held-out deletion')
                        rep_sensitivity+=1
                    if artifact['target_transform']=='log':check(name+' correct log location label','not arithmetic' in spec['location_kind'],'no smearing or arithmetic-mean claim')
                else:check(name+' regularized/baseline intervals not fabricated',item['interval_summary'] is None,'OLS classical PI not automatically assigned to different estimator families')
                cv=next(x['cv'] for x in original['cv_results'] if x['id']==item['candidate_id'])
                cards.append({'method':method,'candidate_id':item['candidate_id'],'frozen_representative':item['representative_frozen'],
                 'cv':cv,'test':item['test_metrics'],'selected_encoded_fields':item['selected_encoded_fields'],
                 'interval_status':item['interval_status'],'interval_summary':item['interval_summary'],
                 'model_path':item['model_path'],'predictions_path':item['predictions_path'],
                 'interval_spec_path':item.get('interval_spec_path'),'diagnostics_path':item.get('diagnostics_path'),
                 'diagnostic_plot_data_path':item.get('diagnostic_plot_data_path'),'interval_plot_data_path':item['interval_plot_data_path']})
            site_cases.append({'id':scenario,'primary':scenario in ['sgemm','student'],'development_rows':len(train),'test_rows':len(test),
                'raw_input_fields':original['raw_input_fields'],'encoded_fields':original['encoded_full_development_fields'],
                'target':cfg.target,'unit':'ms' if info['letter']=='a' else 'grade points','methods':cards,
                'frozen_representative_id':case['frozen_representative_id']})
    check('all 24 OLS model cards have calculated intervals',sum(m['interval_status']=='available' for m in manifest['models'])==24,'six OLS-family winners per four scenarios')
    check('all four representative influence sensitivities validated',rep_sensitivity==4,'one actual deletion refit for every frozen representative')
    raw=json.loads((root/'artifacts/reference/datasets-manifest.json').read_text())
    check('approved raw and prepared data unchanged',all(sha(root/f['path'])==f['sha256'] for ds in raw['datasets'] for f in ds['raw_files']) and all(sha(root/f['path'])==f['sha256'] for f in raw['processed_files']),'Stage 1 source SHA-256 manifest')
    plots=json.loads((out/'plots-manifest.json').read_text())
    check('13 actual PNG files present',plots['count']==13 and all((root/p).read_bytes()[:8]==b'\x89PNG\r\n\x1a\n' for p in plots['rendered']),'saved figures, separate visual review required')
    save(out/'site-summary.json',{'schema_version':'1.0','selection_frozen':True,'cases':site_cases,
      'scope':'preset website data references; not an implemented web UI or public API',
      'interval_caveats':['Post-selection conditioning; uncorrected selection uncertainty.','HC3 location CI does not repair observation PI.','Log location is geometric, not arithmetic conditional mean.']})
    report={'status':'passed_frozen_holdout_evaluation_with_assumption_limits','recorded_at':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds'),
      'checks':checks,'passed_checks':len(checks),'models_scored':36,'ols_models_with_intervals':24,
      'unique_covariance_specifications_verified':len(validated_intervals),'unit_tests':33,
      'scope':'full heldout metrics plus independent covariance/CI/PI and frozen-model integrity',
      'limitations':['Heteroskedasticity/non-normality/functional-form limitations are observed, not fixed by passing software checks.',
        '95% is nominal; heldout coverage is descriptive and does not validate all OLS assumptions.',
        'No test-driven selection, clipping, tuning or test-row removal performed.',
        'No website, public API, Vercel execution or deployment tested.']}
    save(root/'artifacts/validation/stage4.json',report)
    print(json.dumps({'status':report['status'],'checks':len(checks),'models':36,'interval_specs':len(validated_intervals)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();main(a.root.resolve())
