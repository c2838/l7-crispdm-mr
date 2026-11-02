"""Shared batch/one-method engine. Returned metrics are tuning CV, not test scores."""
from collections import defaultdict
from dataclasses import asdict
import hashlib
import json
import time
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
from .config import AnalysisConfig,InputError,Guard,BudgetExceeded,Cancelled,OLS_METHODS
from .preprocessing import FrameEncoder
from .models import fit_linear,predict_linear,sparse_selector,predict_artifact
from .selection import folds_for,kbest_path,rfe_path,sfs_path

def candidate_id(method,params):
    suffix=','.join(f'{k}={v}' for k,v in sorted(params.items()))
    return method+(':'+suffix if suffix else '')

def metrics(y,pred):
    error=y-pred;mse=float(np.mean(error**2));den=float(np.square(y-y.mean()).sum())
    return {'n':len(y),'mae':float(np.mean(np.abs(error))),'mse':mse,'rmse':float(np.sqrt(mse)),
            'r2':1-float(np.square(error).sum())/den if den>0 else None}

def run_analysis(frame,config:AnalysisConfig,progress=None,cancel=None):
    config.validate();guard=Guard(config.budget_seconds,cancel);started=time.perf_counter()
    events=[]
    def emit(kind,**detail):
        event={'sequence':len(events),'event':kind,'elapsed_s':time.perf_counter()-started,**detail};events.append(event)
        if progress:progress(event)
    if not frame.columns.is_unique or any(not isinstance(c,str) for c in frame):raise InputError('Unique string column names required.')
    if config.target not in frame:raise InputError('Target column not found.')
    if len(frame)<max(10,config.outer_folds*2):raise InputError('Insufficient rows.')
    try:y=pd.to_numeric(frame[config.target],errors='raise').to_numpy(dtype=float)
    except (ValueError,TypeError) as e:raise InputError('Target must be numeric.') from e
    if not np.isfinite(y).all():raise InputError('Target contains missing/infinite values; do not impute target.')
    if config.target_transform=='log' and (y<=0).any():raise InputError('Log target requires positive values.')
    excluded={config.target,*config.exclude}
    if config.group_column:excluded.add(config.group_column)
    features=[c for c in frame if c not in excluded]
    if not features:raise InputError('No input features selected.')
    if not set(config.categorical)<=set(features):raise InputError('Categorical override not in selected inputs.')
    X=frame[features].copy()
    duplicates=int(X.duplicated().sum())
    if config.group_column:
        if config.group_column not in frame or frame[config.group_column].isna().any():raise InputError('Invalid group column.')
        groups=pd.factorize(frame[config.group_column],sort=True)[0]
        group_reason='explicit group column excluded from predictors'
    elif duplicates:
        groups=pd.util.hash_pandas_object(X,index=False).to_numpy();group_reason='identical input vectors kept in the same CV fold'
    else:groups=None;group_reason='unique inputs; shuffled KFold within the supplied development population'
    source_hash=hashlib.sha256(pd.util.hash_pandas_object(frame,index=False).to_numpy().tobytes()).hexdigest()
    result={'schema_version':'1.0','dataset_id':config.dataset_id,'status':'running','config':asdict(config),
      'rows':len(X),'raw_input_fields':len(features),'input_fields':features,'frame_values_sha256':source_hash,
      'scope':'development-only tuning CV; no final-test values supplied to this engine',
      'cv_strategy':group_reason,'duplicate_input_rows':duplicates,'target_units':'source units',
      'target_backtransform':'exp(log prediction), geometric location; no arithmetic-mean smearing correction' if config.target_transform=='log' else 'identity',
      'cv_results':[],'models':{},'folds':[],'selection_traces':[],'events':events,
      'limits':['CV scores used to choose k/parameters/model are optimistic selection scores, not unbiased external performance.',
                'Coefficients and any later classical intervals are conditional on preprocessing and feature selection.',
                'Unknown categories use the training reference effect; unknown counts are reported.']}
    entries={};folds=[];ks=[];failure=None;assignments=np.full(len(X),-1,dtype=int)
    def add(method,params,fold,selected,encoder,Zt,Zv,yt,yv,notes=None,kind='ols'):
        guard.check();identifier=candidate_id(method,params)
        if identifier not in entries:entries[identifier]={'id':identifier,'method':method,'parameters':params,'folds':[]}
        record={'fold':fold,'training_rows':len(yt),'validation_rows':len(yv),'encoded_training_fields':len(encoder.keys),
                'selected_count':len(selected),'selected_keys':[encoder.keys[i] for i in selected],**(notes or {})}
        try:
            if method=='dummy':pred=np.full(len(yv),yt.mean());fit={'inference_status':'baseline_only'}
            else:
                fit=fit_linear(Zt[:,selected],yt,config.target_transform,kind,params.get('alpha'))
                pred=predict_linear(fit,Zv[:,selected],config.target_transform)
            record.update(status='completed',metrics=metrics(yv,pred),inference_status=fit['inference_status'])
        except (ValueError,RuntimeError,np.linalg.LinAlgError) as e:
            record.update(status='failed',reason=f'{type(e).__name__}: {e}')
        entries[identifier]['folds'].append(record)
    with threadpool_limits(limits=1):
        try:
            emit('started',rows=len(X),methods=list(config.methods))
            for fi,(tr,va) in enumerate(folds_for(X,config.outer_folds,config.seed,groups)):
                guard.check();enc=FrameEncoder(config.categorical);Zt=enc.fit_transform(X.iloc[tr]);Zv,notes=enc.transform(X.iloc[va])
                if Zt.shape[1]>config.max_encoded_features:raise InputError('Encoded feature budget exceeded in a CV training fold.')
                folds.append({'tr':tr,'va':va,'encoder':enc,'Zt':Zt,'Zv':Zv,'notes':notes})
                assignments[va]=fi
                result['folds'].append({'fold':fi,'training_rows':len(tr),'validation_rows':len(va),
                  'training_row_positions_sha256':hashlib.sha256(np.asarray(tr,dtype='<i8').tobytes()).hexdigest(),
                  'validation_row_positions_sha256':hashlib.sha256(np.asarray(va,dtype='<i8').tobytes()).hexdigest(),
                  'encoded_training_fields':len(enc.keys),'preprocessing_fit_rows':len(tr),'validation_notes':notes,
                  'training_only_preprocessor_sha256':hashlib.sha256(json.dumps(enc.to_spec(),sort_keys=True).encode()).hexdigest()})
            smallest=min(len(f['encoder'].keys) for f in folds)
            ks=list(config.k_values) if config.k_values is not None else list(range(1,smallest+1))
            if any(k>smallest for k in ks):raise InputError('Requested k exceeds available encoded fields in a training fold.')
            result['k_grid']=ks;result['encoded_fold_counts']=[len(f['encoder'].keys) for f in folds]
            for fi,f in enumerate(folds):
                tr,va,enc,Zt,Zv=(f[k] for k in ['tr','va','encoder','Zt','Zv']);yt,yv=y[tr],y[va]
                emit('fold_started',fold=fi)
                for method in config.methods:
                    guard.check();emit('method_started',fold=fi,method=method)
                    if method in ['dummy','ols']:
                        add(method,{},fi,[] if method=='dummy' else list(range(len(enc.keys))),enc,Zt,Zv,yt,yv)
                    elif method in ['kbest','rfe','sfs']:
                        if not enc.keys:
                            result['selection_traces'].append({'fold':fi,'method':method,'status':'unavailable_no_variable_inputs'});continue
                        if method=='kbest':paths=kbest_path(Zt,yt,config.target_transform,ks,guard)
                        elif method=='rfe':paths=rfe_path(Zt,yt,config.target_transform,ks,guard)
                        else:
                            paths,trace=sfs_path(X.iloc[tr],yt,enc.keys,config.target_transform,ks,config,guard,None if groups is None else groups[tr])
                            result['selection_traces'].append({'fold':fi,'method':'sfs',**trace})
                        for k,selected in paths.items():add(method,{'k':k},fi,selected,enc,Zt,Zv,yt,yv)
                    elif method in ['lasso_select','elasticnet_select']:
                        if not enc.keys:continue
                        ratios=[None] if method=='lasso_select' else config.l1_ratios
                        for alpha in config.alphas:
                            for ratio in ratios:
                                guard.check();params={'alpha':alpha}
                                if ratio is not None:params['l1_ratio']=ratio
                                try:selected,notes=sparse_selector(Zt,yt,config.target_transform,alpha,ratio)
                                except RuntimeError as e:
                                    ident=candidate_id(method,params);entry=entries.setdefault(ident,{'id':ident,'method':method,'parameters':params,'folds':[]})
                                    entry['folds'].append({'fold':fi,'status':'failed','reason':str(e)});continue
                                add(method,params,fi,selected,enc,Zt,Zv,yt,yv,notes)
                    else:
                        alphas=config.ridge_alphas if method=='ridge' else config.alphas
                        for alpha in alphas:add(method,{'alpha':alpha},fi,list(range(len(enc.keys))),enc,Zt,Zv,yt,yv,kind=method)
                    emit('method_completed',fold=fi,method=method)
                emit('fold_completed',fold=fi)
            emit('cv_completed')
        except (BudgetExceeded,Cancelled) as e:failure=e

        den=float(np.square(y-y.mean()).sum())
        for entry in entries.values():
            completed=[r for r in entry['folds'] if r['status']=='completed']
            entry['status']='completed' if len(completed)==config.outer_folds else 'incomplete_or_failed'
            if entry['status']=='completed':
                n=sum(r['metrics']['n'] for r in completed);sse=sum(r['metrics']['mse']*r['metrics']['n'] for r in completed)
                entry.update(cv={'mae':sum(r['metrics']['mae']*r['metrics']['n'] for r in completed)/n,
                   'mse':sse/n,'rmse':float(np.sqrt(sse/n)),'r2':1-sse/den if den>0 else None,
                   'fold_rmse_std':float(np.std([r['metrics']['rmse'] for r in completed],ddof=1))},
                   mean_selected_count=float(np.mean([r['selected_count'] for r in completed])))
            result['cv_results'].append(entry)
        def order(e):return (e['cv']['rmse'],e['mean_selected_count'],e['id'])
        eligible=[e for e in result['cv_results'] if e['status']=='completed']
        winners={method:min([e for e in eligible if e['method']==method],key=order) for method in config.methods if any(e['method']==method for e in eligible)}
        result['method_winner_ids']={k:v['id'] for k,v in winners.items()}
        primary=[e for e in eligible if e['method'] in OLS_METHODS]
        result['representative_candidate_id']=min(primary,key=order)['id'] if primary else None
        try:
            if failure is not None:raise failure
            enc=FrameEncoder(config.categorical);Z=enc.fit_transform(X)
            if len(enc.keys)>config.max_encoded_features:raise InputError('Full development encoding exceeds feature budget.')
            result['encoded_full_development_fields']=len(enc.keys)
            sfs_ks=sorted({e['parameters']['k'] for m,e in winners.items() if m=='sfs'})
            final_sfs,trace=sfs_path(X,y,enc.keys,config.target_transform,sfs_ks,config,guard,groups) if sfs_ks else ({},{})
            if trace:result['selection_traces'].append({'scope':'full development refit','method':'sfs',**trace})
            for method,entry in winners.items():
                guard.check();params=entry['parameters'];extra={}
                if method=='dummy':selected=[];fit={'coefficients':[],'intercept':float(y.mean()),'design_rank':1,'design_columns':1,'inference_status':'baseline_only'}
                else:
                    if method in ['ols','ridge','lasso_reg']:selected=list(range(len(enc.keys)))
                    elif method=='kbest':selected=kbest_path(Z,y,config.target_transform,[params['k']],guard)[params['k']]
                    elif method=='rfe':selected=rfe_path(Z,y,config.target_transform,[params['k']],guard)[params['k']]
                    elif method=='sfs':selected=final_sfs[params['k']]
                    else:selected,extra=sparse_selector(Z,y,config.target_transform,params['alpha'],params.get('l1_ratio'))
                    fit=fit_linear(Z[:,selected],y,config.target_transform,method if method in ['ridge','lasso_reg'] else 'ols',params.get('alpha'))
                artifact={'schema_version':'1.0','dataset_id':config.dataset_id,'candidate_id':entry['id'],'method':method,
                  'parameters':params,'target':config.target,'target_transform':config.target_transform,'raw_input_fields':features,
                  'selected_keys':[enc.keys[i] for i in selected],'selected_columns':[enc.columns[i] for i in selected],
                  'selected_raw_fields':sorted(set(enc.columns[i]['field'] for i in selected)),
                  'model':fit,'preprocessor':enc.to_spec(),'fit_rows':len(X),**extra,
                  'point_prediction_semantics':result['target_backtransform'],'source_frame_values_sha256':source_hash}
                pred,_=predict_artifact(artifact,X.iloc[:min(10,len(X))])
                assert np.isfinite(pred).all();result['models'][entry['id']]=artifact
                emit('refit_completed',method=method,candidate_id=entry['id'],selected_count=len(selected))
            result['status']='completed'
        except BudgetExceeded:result['status']='partial_timeout'
        except Cancelled:result['status']='cancelled'
    result['representative_model_available']=result['representative_candidate_id'] in result['models']
    result['cv_validation_fold_by_row']=assignments.tolist()
    result['elapsed_s']=time.perf_counter()-started
    result['completed_methods']=[m for m,cid in result.get('method_winner_ids',{}).items() if cid in result['models']]
    result['unavailable_methods']=[m for m in config.methods if m not in result['completed_methods']]
    emit('finished',status=result['status'],completed_methods=result['completed_methods'])
    return result
