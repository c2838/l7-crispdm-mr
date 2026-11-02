"""Evaluate exactly the Stage 3 frozen models. No test-driven model selection."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata as md
import json
import os
import resource
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from l7_analysis.config import OLS_METHODS
from l7_analysis.data import load_development,SCENARIOS
from l7_analysis.engine import metrics
from l7_analysis.models import predict_artifact
from l7_analysis.inference import fit_inference,predict_with_intervals,coefficient_intervals,interval_summary,equation_hash,design_for
from l7_analysis.diagnostics import diagnose

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def load_test(root,scenario):
    train,train_ids,cfg,source=load_development(root,scenario)
    info=SCENARIOS[scenario];split=pd.read_csv(root/source['split_path'])
    ids=split.loc[split.split=='final_test','source_row_index_0_based'].to_numpy()
    allowed=set(ids.tolist());assert not allowed&set(train_ids.tolist())
    test=pd.read_csv(root/source['input_path'],skiprows=lambda i:i>0 and i-1 not in allowed)
    assert len(test)==len(ids)==source['reserved_final_rows']
    source.update(final_test_rows_parsed_for_evaluation=len(test),test_source_rows_sha256=hashlib.sha256(ids.astype('<i8').tobytes()).hexdigest())
    return train,train_ids,test,ids,cfg,source

def sample_interval_rows(table,max_points=2000):
    n=len(table);order=np.argsort(table.prediction.to_numpy(),kind='stable')
    ranks=np.empty(n,dtype=int);ranks[order]=np.arange(n)
    if n<=max_points:chosen=np.arange(n)
    else:
        base=order[np.linspace(0,n-1,max_points-20,dtype=int)]
        extreme=np.argsort(np.abs(table.residual.to_numpy()))[-20:]
        chosen=np.union1d(base,extreme)
    chosen=chosen[np.argsort(ranks[chosen])]
    keep=['source_row_index_0_based','actual','prediction','residual','location_ci_lower','location_ci_upper',
          'observation_pi_lower','observation_pi_upper','location_ci_hc3_lower','location_ci_hc3_upper']
    keep=[k for k in keep if k in table]
    data=table.iloc[chosen][keep].to_dict('list');data['prediction_rank']=ranks[chosen].tolist()
    return {'rows':data,'display_rows':len(chosen),'total_test_rows':n,
       'display_rule':'All rows if <=2000; otherwise 1980 evenly spaced prediction ranks plus up to 20 largest absolute residuals. No rows removed from metrics.'}

def main(root):
    started=time.perf_counter();out=root/'artifacts/analysis/evaluation'
    if (out/'evaluation-manifest.json').exists():raise RuntimeError('Existing evaluation must be preserved before any rerun.')
    freeze_path=root/'artifacts/analysis/models/selection-freeze.json';freeze=json.loads(freeze_path.read_text())
    assert freeze['status']=='frozen_before_final_test_evaluation'
    assert all(sha(root/m['model_path'])==m['model_sha256'] for m in freeze['models'])
    assert all(sha(root/'artifacts/analysis/models'/s/'result.json')==h for s,h in freeze['scenario_result_sha256'].items())
    manifest={'status':'in_progress','authorized_stage':'User: 階段4 go',
       'evaluation_started_at':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds'),
       'freeze_sha256_before':sha(freeze_path),'selection_basis':'Frozen development CV choices; no change after reading test.',
       'model_count':len(freeze['models']),'sources':{},'models':[]}
    save(out/'evaluation-manifest.json',manifest)
    rows=[];coefficient_rows=[];case_summaries=[]
    with threadpool_limits(limits=1):
        for scenario in SCENARIOS:
            train,train_ids,test,test_ids,cfg,source=load_test(root,scenario)
            directory=out/scenario;directory.mkdir(parents=True,exist_ok=True)
            original=json.loads((root/'artifacts/analysis/models'/scenario/'result.json').read_text())
            representative=original['representative_candidate_id'];case_items=[];cache={}
            for frozen in [m for m in freeze['models'] if m['scenario']==scenario]:
                artifact=json.loads((root/frozen['model_path']).read_text());method=artifact['method'];cid=artifact['candidate_id']
                file_id=hashlib.sha256(cid.encode()).hexdigest()[:16]
                prediction,notes=predict_artifact(artifact,test);actual=test[cfg.target].to_numpy()
                score=metrics(actual,prediction)
                item={'scenario':scenario,'method':method,'candidate_id':cid,'representative_frozen':cid==representative,
                  'test_metrics':score,'selected_encoded_fields':len(artifact['selected_keys']),
                  'selected_raw_fields':len(artifact['selected_raw_fields']),'test_transform_notes':notes,
                  'test_adjusted_r2':None,'test_adjusted_r2_reason':'Adjusted R2 is reported on fitted development OLS, not relabeled held-out R2.',
                  'interval_status':'not_applicable_to_baseline_or_regularized_model','interval_summary':None,
                  'model_path':frozen['model_path'],'model_sha256':frozen['model_sha256']}
                table=pd.DataFrame({'source_row_index_0_based':test_ids,'actual':actual,'prediction':prediction,'residual':actual-prediction})
                if method in OLS_METHODS:
                    fingerprint=equation_hash(artifact)
                    if fingerprint not in cache:
                        bundle=fit_inference(artifact,train)
                        common={'status':bundle['status']}
                        if bundle['status']=='available':
                            interval,_=predict_with_intervals(artifact,bundle['spec'],test)
                            reference=bundle['fit'].get_prediction(design_for(artifact,test)[0]).summary_frame(alpha=.05)
                            # Compare on the regression scale before any exp backtransform.
                            assert np.allclose(interval.regression_location_ci_lower,reference.mean_ci_lower,rtol=1e-8,atol=1e-8)
                            assert np.allclose(interval.regression_observation_pi_upper,reference.obs_ci_upper,rtol=1e-8,atol=1e-8)
                            diagnostic,plot=diagnose(bundle,train_ids)
                            common.update(spec=bundle['spec'],interval=interval,diagnostics=diagnostic,plot=plot,
                                          coefficient_intervals=coefficient_intervals(bundle))
                        cache[fingerprint]=common
                    common=cache[fingerprint];item['interval_status']=common['status']
                    if common['status']=='available':
                        interval=common['interval']
                        for col in interval:
                            if col!='prediction':table[col]=interval[col].to_numpy()
                        summary=interval_summary(actual,interval);summary['nominal_level']=.95
                        summary['location_kind']=common['spec']['location_kind'];item['interval_summary']=summary
                        infer_id=fingerprint[:20]
                        for suffix,value in [('interval-spec',common['spec']),('diagnostics',common['diagnostics']),('diagnostic-plot-data',common['plot'])]:
                            path=directory/'inference'/f'{infer_id}-{suffix}.json'
                            if not path.exists():save(path,value)
                            item[suffix.replace('-','_')+'_path']=str(path.relative_to(root))
                        item['development_ols_adjusted_r2']=common['diagnostics']['development_ols_adjusted_r2']
                        item['development_adjusted_r2_scale']=common['diagnostics']['response_scale']
                        for row in common['coefficient_intervals']:coefficient_rows.append({'scenario':scenario,'method':method,'candidate_id':cid,**row})
                        train_point,_=predict_artifact(artifact,train)
                        edges=np.unique(np.quantile(train_point,[.25,.5,.75]));bin_index=np.searchsorted(edges,prediction,side='right')
                        groups=[]
                        for i in range(len(edges)+1):
                            mask=bin_index==i
                            groups.append({'bin':i,'rows':int(mask.sum()),'coverage':float(((actual[mask]>=interval.observation_pi_lower.to_numpy()[mask])&(actual[mask]<=interval.observation_pi_upper.to_numpy()[mask])).mean()) if mask.any() else None})
                        item['coverage_by_prediction_bin']={'edges_from_development_predictions':edges.tolist(),'groups':groups,'scope':'descriptive heldout coverage by training-defined predicted-value bins'}
                        if 'school' in test:
                            item['coverage_by_school']=[{'school':school,'rows':int((test.school==school).sum()),
                              'coverage':float(((actual[test.school==school]>=interval.observation_pi_lower.to_numpy()[test.school==school])&(actual[test.school==school]<=interval.observation_pi_upper.to_numpy()[test.school==school])).mean())}
                              for school in sorted(test.school.unique())]
                if scenario.startswith('student'):
                    item['prediction_outside_documented_0_20']=int(((prediction<0)|(prediction>20)).sum())
                    if item['interval_summary']:
                        item['pi_endpoint_outside_documented_0_20']=int(((table.observation_pi_lower<0)|(table.observation_pi_upper>20)).sum())
                predictions_path=directory/'predictions'/f'{file_id}.csv.gz';predictions_path.parent.mkdir(parents=True,exist_ok=True)
                table.to_csv(predictions_path,index=False,float_format='%.17g',compression='gzip')
                item['predictions_path']=str(predictions_path.relative_to(root));item['predictions_sha256']=sha(predictions_path)
                plot_path=directory/'plot-data'/f'{file_id}.json';save(plot_path,sample_interval_rows(table))
                item['interval_plot_data_path']=str(plot_path.relative_to(root))
                if cid==representative:
                    table.to_csv(directory/'representative-predictions.csv',index=False,float_format='%.17g')
                case_items.append(item);manifest['models'].append(item)
                rows.append({'scenario':scenario,'method':method,'candidate_id':cid,'representative_frozen':cid==representative,
                 'test_rows':len(test),**score,'selected_encoded_fields':item['selected_encoded_fields'],
                 'pi_coverage':item['interval_summary']['observation_pi_coverage'] if item['interval_summary'] else None,
                 'pi_mean_width':item['interval_summary']['observation_pi_mean_width'] if item['interval_summary'] else None})
                print(json.dumps({'scenario':scenario,'method':method,'test_rows':len(test),'interval_status':item['interval_status']}),flush=True)
            manifest['sources'][scenario]=source
            case={'scenario':scenario,'test_rows':len(test),'frozen_representative_id':representative,'models':case_items,
                  'representative':next(x for x in case_items if x['candidate_id']==representative),
                  'limits':['No retuning, replacement, clipping or test-row deletion.','Classical PI depends on conditional homoskedastic normal errors.','Selection uncertainty is not corrected.']}
            save(directory/'evaluation.json',case);case_summaries.append(case)
    pd.DataFrame(rows).to_csv(out/'test-comparison.csv',index=False)
    pd.DataFrame(coefficient_rows).to_csv(out/'coefficient-intervals.csv',index=False)
    assert sha(freeze_path)==manifest['freeze_sha256_before']
    assert all(sha(root/m['model_path'])==m['model_sha256'] for m in freeze['models'])
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    manifest.update(status='completed',freeze_sha256_after=sha(freeze_path),
       evaluation_finished_at=datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds'),
       execution={'wall_s':time.perf_counter()-started,'peak_rss_bytes':int(peak if sys.platform=='darwin' else peak*1024),
        'versions':{n:md.version(n) for n in ['numpy','pandas','scipy','statsmodels']}})
    save(out/'evaluation-manifest.json',manifest)
    save(out/'summary.json',{'status':'completed','scope':'fixed held-out evaluation of Stage 3 frozen models',
       'frozen_selection_unchanged':True,'scenarios':[{'scenario':c['scenario'],'test_rows':c['test_rows'],
       'representative':c['representative']} for c in case_summaries],'execution':manifest['execution']})
    print(json.dumps({'status':'completed','evaluated_models':len(rows),'elapsed_s':manifest['execution']['wall_s']}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();main(a.root.resolve())
