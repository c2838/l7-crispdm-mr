"""Development-only candidate details and static browser data; no test refitting."""
from pathlib import Path
import argparse,copy,hashlib,json,os,sys,time
from datetime import datetime
from zoneinfo import ZoneInfo
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from scipy import stats
from threadpoolctl import threadpool_limits
from l7_analysis.config import AnalysisConfig,Guard,OLS_METHODS
from l7_analysis.data import SCENARIOS,load_development
from l7_analysis.preprocessing import FrameEncoder
from l7_analysis.selection import kbest_path,rfe_path,sfs_path,folds_for
from l7_analysis.models import fit_linear,sparse_selector,predict_artifact
from l7_analysis.engine import metrics
from l7_analysis.inference import fit_inference,predict_with_intervals,coefficient_intervals,equation_hash
from l7_analysis.diagnostics import diagnose

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
def uid(text):return hashlib.sha256(text.encode()).hexdigest()[:16]

def main(root):
    started=time.perf_counter();out=root/'web/data'
    if (out/'catalog.json').exists():raise RuntimeError('Preserve existing Stage 5 export before rebuilding.')
    freeze_path=root/'artifacts/analysis/models/selection-freeze.json';freeze=read(freeze_path)
    protected={str(freeze_path.relative_to(root)):sha(freeze_path)}
    protected.update({m['model_path']:m['model_sha256'] for m in freeze['models']})
    protected.update({'artifacts/analysis/models/'+s+'/result.json':h for s,h in freeze['scenario_result_sha256'].items()})
    evaluation=root/'artifacts/analysis/evaluation'
    for p in evaluation.rglob('*'):
        if p.is_file():protected[str(p.relative_to(root))]=sha(p)
    assert all(sha(root/p)==h for p,h in protected.items())
    cases=[];fixtures=[];exports=[];counts={};details_count=0
    with threadpool_limits(limits=1):
        for scenario in SCENARIOS:
            print(json.dumps({'event':'scenario_started','scenario':scenario}),flush=True)
            frame,ids,cfg,source=load_development(root,scenario)
            original=read(root/'artifacts/analysis/models'/scenario/'result.json')
            case=read(evaluation/scenario/'evaluation.json')
            cfg=AnalysisConfig(**{k:tuple(v) if isinstance(v,list) else v for k,v in original['config'].items()})
            fields=original['input_fields'];X=frame[fields];y=frame[cfg.target].to_numpy(dtype=float)
            encoder=FrameEncoder(cfg.categorical);Z=encoder.fit_transform(X);guard=Guard()
            entries=[e for e in original['cv_results'] if e['status']=='completed']
            ks=original['k_grid']
            paths={'kbest':kbest_path(Z,y,cfg.target_transform,ks,guard),'rfe':rfe_path(Z,y,cfg.target_transform,ks,guard)}
            paths['sfs'],trace=sfs_path(X,y,encoder.keys,cfg.target_transform,ks,cfg,guard)
            forms=[];defaults={}
            for field in encoder.fields:
                f=field['field'];record=copy.deepcopy(field)
                if field['kind']=='numeric':
                    values=X[f].astype(float);options=sorted(values.unique().tolist())
                    record.update(min=float(values.min()),max=float(values.max()),allowed_values=options if len(options)<=12 else None)
                    defaults[f]=float(X.iloc[0][f])
                else:defaults[f]=str(X.iloc[0][f])
                forms.append(record)
            cards=[];equations={};frozen_by_id={m['candidate_id']:m for m in case['models']}
            for pos,entry in enumerate(entries):
                method=entry['method'];params=entry['parameters'];identifier=entry['id'];frozen=frozen_by_id.get(identifier)
                if frozen:artifact=read(root/frozen['model_path'])
                else:
                    extra={}
                    if method=='dummy':selected=[];fit={'coefficients':[],'intercept':float(y.mean()),'design_rank':1,'design_columns':1,'inference_status':'baseline_only'}
                    else:
                        if method in ['ols','ridge','lasso_reg']:selected=list(range(len(encoder.keys)))
                        elif method in paths:selected=paths[method][params['k']]
                        else:selected,extra=sparse_selector(Z,y,cfg.target_transform,params['alpha'],params.get('l1_ratio'))
                        fit=fit_linear(Z[:,selected],y,cfg.target_transform,method if method in ['ridge','lasso_reg'] else 'ols',params.get('alpha'))
                    artifact={'schema_version':'1.0','dataset_id':scenario,'candidate_id':identifier,'method':method,
                        'parameters':params,'target':cfg.target,'target_transform':cfg.target_transform,'raw_input_fields':fields,
                        'selected_keys':[encoder.keys[i] for i in selected],'selected_columns':[encoder.columns[i] for i in selected],
                        'selected_raw_fields':sorted(set(encoder.columns[i]['field'] for i in selected)),
                        'model':fit,'preprocessor':encoder.to_spec(),'fit_rows':len(frame),**extra,
                        'point_prediction_semantics':original['target_backtransform'],'source_frame_values_sha256':original['frame_values_sha256']}
                # Guard that reconstructing candidate paths did not silently change a frozen winner.
                if frozen and method in paths:
                    assert artifact['selected_keys']==[encoder.keys[i] for i in paths[method][params['k']]],identifier
                eq=equation_hash(artifact);q=len(artifact['selected_keys'])
                if eq not in equations or (method in OLS_METHODS and equations[eq]['inference'] is None):
                    pred,_=predict_artifact(artifact,frame)
                    sample=np.linspace(0,len(frame)-1,min(300,len(frame)),dtype=int)
                    observed=frame[cfg.target].to_numpy(dtype=float)
                    plot={'scope':'development display sample; not held-out evaluation','total_rows':len(frame),'display_rows':len(sample),
                          'rows':{'source_row_index_0_based':ids[sample].tolist(),'actual':observed[sample].tolist(),'prediction':pred[sample].tolist(),'residual':(observed-pred)[sample].tolist()}}
                    inf=None;coef=[];diagnostic=None;dplot=None;status='not_applicable_to_baseline_or_regularized_model'
                    if method in OLS_METHODS:
                        bundle=fit_inference(artifact,frame);status=bundle['status']
                        if status=='available':
                            inf=bundle['spec'];inf['critical_value_95']=float(stats.t.ppf(.975,inf['df_resid']))
                            coef=coefficient_intervals(bundle);diagnostic,dplot=diagnose(bundle,ids,max_points=300)
                    equations[eq]={'development_metrics':metrics(observed,pred),'development_plot':plot,'inference':inf,
                                   'coefficient_intervals':coef,'diagnostics':diagnostic,'diagnostic_plot':dplot,'inference_status':status}
                detail={'candidate_id':identifier,'artifact':artifact,**equations[eq],
                        'scope':'development-only fit; CV from Stage 3; frozen held-out metrics attached only to original winners',
                        'frozen':frozen,'cv':entry['cv']}
                # Regularized methods never inherit OLS inference even if equation hashes coincide.
                if method not in OLS_METHODS:
                    detail.update(inference=None,coefficient_intervals=[],diagnostics=None,diagnostic_plot=None,
                                  inference_status='not_applicable_to_baseline_or_regularized_model')
                if frozen:
                    detail['heldout_plot']=read(root/frozen['interval_plot_data_path'])
                    if frozen.get('diagnostics_path'):
                        detail['diagnostics']=read(root/frozen['diagnostics_path'])
                        detail['diagnostic_plot']=read(root/frozen['diagnostic_plot_data_path'])
                path=out/scenario/(uid(identifier)+'.json');save(path,detail);exports.append(path)
                card={'id':identifier,'method':method,'parameters':params,'cv':entry['cv'],
                      'mean_cv_selected_count':entry['mean_selected_count'],'selected_count':q,
                      'selected_labels':[v['label'] for v in artifact['selected_columns']],
                      'detail':str(path.relative_to(root/'web')),'frozen_winner':frozen is not None,
                      'representative':identifier==case['frozen_representative_id'],
                      'test':frozen['test_metrics'] if frozen else None}
                cards.append(card);details_count+=1
                default_frame=pd.DataFrame([defaults]);pred,_=predict_artifact(artifact,default_frame)
                expected={'prediction':float(pred[0])}
                if detail['inference']:
                    interval,_=predict_with_intervals(artifact,detail['inference'],default_frame)
                    expected.update({k:float(interval.iloc[0][k]) for k in ['location_ci_lower','location_ci_upper','observation_pi_lower','observation_pi_upper','location_ci_hc3_lower','location_ci_hc3_upper']})
                fixtures.append({'scenario':scenario,'candidate_id':identifier,'detail':str(path.relative_to(root/'web')),'input':defaults,'expected':expected})
                if card['representative']:
                    for kind in ['outside_range','unknown_category','missing_value']:
                        changed=dict(defaults)
                        if kind=='outside_range':
                            f=next(f for f in forms if f['kind']=='numeric');changed[f['field']]=f['max']+5
                        elif kind=='unknown_category':
                            cat=[f for f in forms if f['kind']=='categorical']
                            if not cat:continue
                            changed[cat[0]['field']]='__UNSEEN_CATEGORY__'
                        else:changed[forms[0]['field']]=None
                        row=pd.DataFrame([changed]);pr,_=predict_artifact(artifact,row);ex={'prediction':float(pr[0])}
                        if detail['inference']:
                            interval,_=predict_with_intervals(artifact,detail['inference'],row)
                            ex.update({k:float(interval.iloc[0][k]) for k in expected if k!='prediction'})
                        fixtures.append({'scenario':scenario,'candidate_id':identifier,'case':kind,'detail':str(path.relative_to(root/'web')),'input':changed,'expected':ex})
                if pos%20==0:print(json.dumps({'event':'candidates_exported','scenario':scenario,'done':pos+1,'total':len(entries)}),flush=True)
            # Learning curve: three development-only validation folds, all-feature OLS.
            learning=[]
            for fraction in [.1,.25,.5,.75,1.]:
                records=[]
                for fi,(tr,va) in enumerate(folds_for(X,3,73)):
                    order=np.random.default_rng(730+fi).permutation(tr);subset=order[:max(30,int(len(tr)*fraction))]
                    en=FrameEncoder(cfg.categorical);zt=en.fit_transform(X.iloc[subset]);zv,_=en.transform(X.iloc[va])
                    try:
                        fit=fit_linear(zt,y[subset],cfg.target_transform);from l7_analysis.models import predict_linear
                        records.append({'training_rows':len(subset),'training':metrics(y[subset],predict_linear(fit,zt,cfg.target_transform)),
                                        'validation':metrics(y[va],predict_linear(fit,zv,cfg.target_transform)),'rank_status':fit['inference_status']})
                    except (ValueError,RuntimeError) as e:records.append({'status':'unavailable','reason':str(e)})
                valid=[r for r in records if 'training' in r]
                learning.append({'fraction':fraction,'records':records,'mean_training_rows':float(np.mean([r['training_rows'] for r in valid])) if valid else None,
                                 'training_rmse':float(np.sqrt(np.mean([r['training']['mse'] for r in valid]))) if valid else None,
                                 'validation_rmse':float(np.sqrt(np.mean([r['validation']['mse'] for r in valid]))) if valid else None})
            summary={'id':scenario,'development_rows':len(frame),'test_rows':case['test_rows'],'raw_fields':len(fields),'encoded_fields':len(encoder.keys),
                     'target':cfg.target,'target_transform':cfg.target_transform,'unit':'ms' if scenario.startswith('sgemm') else 'grade points',
                     'forms':forms,'defaults':defaults,'winner_ids':original['method_winner_ids'],'representative_id':case['frozen_representative_id'],
                     'candidates':cards,'learning_curve':learning,'learning_scope':'All-feature OLS; 3-fold development validation; preprocessing fit independently per training subset; no test rows.',
                     'source':source,'sfs_full_development_trace':trace}
            save(out/(scenario+'.json'),summary);exports.append(out/(scenario+'.json'));counts[scenario]=len(cards)
            cases.append({'id':scenario,'path':'data/'+scenario+'.json','primary':scenario in ['sgemm','student']})
            print(json.dumps({'event':'scenario_completed','scenario':scenario,'candidates':len(cards)}),flush=True)
    assert all(sha(root/p)==h for p,h in protected.items()),'Protected results changed'
    catalog={'schema_version':'1.0','built_at':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds'),
             'cases':cases,'freeze_sha256':sha(freeze_path),'candidate_count':details_count,
             'scope':'Local preset website; custom dataset analysis and public deployment pending later stages.'}
    save(out/'catalog.json',catalog);exports.append(out/'catalog.json')
    save(root/'artifacts/validation/stage5-prediction-fixtures.json',fixtures)
    save(root/'artifacts/analysis/website/export-manifest.json',{'status':'completed','candidate_count':details_count,'counts':counts,
         'elapsed_s':time.perf_counter()-started,'protected_sha256':protected,
         'export_sha256':{str(p.relative_to(root)):sha(p) for p in exports},
         'source_sha256':{str(p.relative_to(root)):sha(p) for p in [Path(__file__).resolve(),*sorted((root/'l7_analysis').glob('*.py'))]},
         'new_final_test_rows_parsed':0,'additional_model_families':0,'purpose':'Existing candidate exploration and learning curve; not improving GPU R2.'})
    print(json.dumps({'status':'completed','candidates':details_count,'elapsed_s':time.perf_counter()-started}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();main(a.root.resolve())
