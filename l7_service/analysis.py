import time,hashlib
import numpy as np
import pandas as pd
from scipy import stats
from threadpoolctl import threadpool_limits
from l7_analysis.config import AnalysisConfig,OLS_METHODS,InputError
from l7_analysis.engine import run_analysis,metrics
from l7_analysis.models import predict_artifact
from l7_analysis.inference import fit_inference,predict_with_intervals,coefficient_intervals,interval_summary
from l7_analysis.diagnostics import diagnose
from .contracts import Problem,Options,fingerprint,REQUEST_METHODS,METHOD_SECONDS,json_bytes,MAX_JSON_BYTES,finite_json
from .ingest import prepare

def build_forms(artifact,training):
    forms=[];defaults={}
    for field in artifact['preprocessor']['fields']:
        item=dict(field);name=field['field'];series=training[name]
        if item['kind']=='numeric':
            present=pd.to_numeric(series).dropna();unique=sorted(float(v) for v in present.unique())
            item.update(min=float(present.min()) if len(present) else None,max=float(present.max()) if len(present) else None,
                        allowed_values=unique if len(unique)<=12 else None)
            value=series.iloc[0];defaults[name]=None if pd.isna(value) else float(value)
        else:
            value=series.iloc[0];defaults[name]=None if pd.isna(value) else str(value)
        forms.append(item)
    return forms,defaults

def run_method(frame,source,options:Options,method,*,cancel=None,budget_seconds=METHOD_SECONDS):
    if method not in REQUEST_METHODS:raise Problem('unknown_method','找不到指定分析方法。')
    started=time.perf_counter();deadline=started+budget_seconds
    development,test,dev_ids,test_ids,fields,split,warnings=prepare(frame,source,options)
    analysis_id=fingerprint(options,source['sha256'])
    methods=('dummy','ols','ridge','lasso_reg') if method=='baseline' else (method,)
    cfg=AnalysisConfig(target=options.target,dataset_id='custom-'+analysis_id[:16],target_transform=options.target_transform,
        categorical=tuple(options.categorical),group_column='__l7_effective_group__' if split['grouped'] else None,
        methods=methods,budget_seconds=max(0.,deadline-time.perf_counter()))
    with threadpool_limits(limits=1):
        try:result=run_analysis(development,cfg,cancel=cancel)
        except (InputError,ValueError,np.linalg.LinAlgError) as e:raise Problem('analysis_input',str(e)) from e
        output={'schema_version':'1.0','analysis_id':analysis_id,'data_sha256':source['sha256'],'request_method':method,
            'options':options.model_dump(),'source':source,'split':split,'raw_input_fields':len(fields),
            'scope':'One stateless method request; common development/test split; selection uses development CV only.',
            'engine_status':result['status'],'status':result['status'],'warnings':warnings,
            'cv_policy':{'outer_folds':5,'inner_sfs_folds':3,'seed':17,'k_grid':result.get('k_grid',[]),
                         'alphas':list(cfg.alphas),'l1_ratios':list(cfg.l1_ratios),'ridge_alphas':list(cfg.ridge_alphas)},
            'cv_candidates':[{'id':e['id'],'method':e['method'],'parameters':e['parameters'],'status':e['status'],'cv':e.get('cv'),
                'mean_selected_count':e.get('mean_selected_count'),
                'completed_folds':sum(f['status']=='completed' for f in e['folds']),
                'fold_metrics':[{'fold':f['fold'],'status':f['status'],'metrics':f.get('metrics'),'training_rows':f.get('training_rows'),'validation_rows':f.get('validation_rows')} for f in e['folds']]} for e in result['cv_results']],
            'winner_ids':result.get('method_winner_ids',{}),'models':[],'selection_representative_id':result.get('representative_candidate_id'),
            'folds':result['folds'],'events':result['events'],
            'privacy':'CSV/results kept only in current request/browser; no history database or source-row logging.',
            'interval_caveats':['Conditional on fitted preprocessing/selected columns; uncorrected selection uncertainty.',
                                 'Classical observation PI assumes an error model; HC3 only affects coefficient/location CI.',
                                 'Grouped splitting does not by itself establish independent errors.']}
        expected=next((e for e in result['cv_results'] if e['id']==result.get('representative_candidate_id')),None)
        test_y=test[options.target].to_numpy(dtype=float)
        for cid,artifact in result['models'].items():
            if cancel and cancel():output['status']='cancelled';break
            prediction,notes=predict_artifact(artifact,test)
            item={'candidate_id':cid,'method':artifact['method'],'parameters':artifact['parameters'],'artifact':artifact,
                  'selected_count':len(artifact['selected_keys']),'test_metrics':metrics(test_y,prediction),
                  'cv':next(e['cv'] for e in result['cv_results'] if e['id']==cid),
                  'inference':None,'inference_status':'not_applicable_to_baseline_or_regularized_model',
                  'coefficient_intervals':[],'diagnostics':None,'diagnostic_plot':None,'interval_summary':None,
                  'forms':None,'defaults':None,'test_transform_notes':notes}
            plot={'source_row_index_0_based':test_ids.tolist(),'actual':test_y.tolist(),'prediction':prediction.tolist(),'residual':(test_y-prediction).tolist()}
            if artifact['method'] in OLS_METHODS:
                if time.perf_counter()>=deadline:
                    item['inference_status']='unavailable_budget';output['status']='partial_timeout'
                else:
                    bundle=fit_inference(artifact,development);item['inference_status']=bundle['status']
                    if bundle['status']=='available':
                        spec=bundle['spec'];spec['critical_value_95']=float(stats.t.ppf(.975,spec['df_resid']))
                        spec['observation_kind']='new observation of the user-selected target under a homoskedastic Gaussian regression error model'
                        interval,_=predict_with_intervals(artifact,spec,test)
                        item['inference']=spec;item['coefficient_intervals']=coefficient_intervals(bundle)
                        for col in ['location_ci_lower','location_ci_upper','observation_pi_lower','observation_pi_upper','location_ci_hc3_lower','location_ci_hc3_upper']:plot[col]=interval[col].tolist()
                        item['interval_summary']=interval_summary(test_y,interval)
                        diagnostic,dplot=diagnose(bundle,dev_ids,max_points=500)
                        diagnostic['independence']={'status':'not_established','reason':'Heldout/CV groups isolated where available; row-level OLS still assumes an error structure not established by splitting.',
                            'source_limit':'User dataset; no independent external population validated. Grouped data may require cluster-aware inference.'}
                        item['diagnostics']=diagnostic;item['diagnostic_plot']=dplot
            item['forms'],item['defaults']=build_forms(artifact,development)
            # All metrics above use all test rows. Thinning only affects payload/plot display.
            order=np.argsort(prediction,kind='stable');rank=np.empty(len(test),dtype=int);rank[order]=np.arange(1,len(test)+1)
            plot['prediction_rank']=rank.tolist();display=order[np.linspace(0,len(test)-1,min(1000,len(test)),dtype=int)]
            item['heldout_plot']={'total_test_rows':len(test),'display_rows':len(display),'display_rule':'even ranks sorted by prediction; full rows scored',
                'rows':{k:[v[int(i)] for i in display] for k,v in plot.items()}}
            output['models'].append(item)
        if output['status']=='completed' and len(output['models'])!=len(methods) and method!='baseline':
            output['status']='unavailable';output['warnings'].append('此方法沒有可用的非固定模型欄位／完整候選；未宣稱成功。')
        elif output['status']=='completed' and len(output['models'])!=len(methods):output['status']='partial_unavailable'
        output['completed_model_count']=len(output['models']);output['elapsed_s']=time.perf_counter()-started
        output['validation_note']='Non-finite diagnostic scalars, if any, are represented as null/unavailable, not zero or a passed assumption.'
        output=finite_json(output)
        if len(json_bytes(output))>MAX_JSON_BYTES:
            for item in output['models']:
                p=item['heldout_plot'];indices=np.linspace(0,p['display_rows']-1,min(250,p['display_rows']),dtype=int)
                p['rows']={k:[v[int(i)] for i in indices] for k,v in p['rows'].items()};p['display_rows']=len(indices)
            output['warnings'].append('回應顯示點縮至最多250；全test指標與覆蓋率未改動。')
        if len(json_bytes(output))>MAX_JSON_BYTES:raise Problem('result_too_large','結果超過3,000,000 bytes顯示預算，請減少類別欄位或模型複雜度；未裁切計分資料。',413)
        return output
