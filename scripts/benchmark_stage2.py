"""Stage 2 feasibility only. Uses development rows, never the final test.

Each case runs in its own single-threaded process. No score is used to choose
the final model. Forward selection caches independently fitted CV-fold
preprocessors; candidates are encoded columns and report their original fields.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time

os.environ.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                  VECLIB_MAXIMUM_THREADS='1', MPLCONFIGDIR='/private/tmp/l7-stage2-matplotlib')


def run_case(root, dataset, method, output):
    started=time.perf_counter();cpu_started=time.process_time()
    import warnings
    import resource
    import numpy as np
    import pandas as pd
    import scipy
    import sklearn
    import statsmodels.api as sm
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    from sklearn.linear_model import LinearRegression, Lasso, ElasticNet
    from sklearn.feature_selection import SelectKBest, f_regression, RFE
    from sklearn.model_selection import KFold
    from sklearn.metrics import mean_squared_error
    from threadpoolctl import threadpool_limits, threadpool_info
    threadpool_limits(1)
    imports_s=time.perf_counter()-started
    letter='a' if dataset=='sgemm' else 'b'
    t=time.perf_counter()
    if dataset=='stress':
        # Resource-bound fixture only, never a homework dataset or bonus proof.
        rng=np.random.default_rng(68)
        frame=pd.DataFrame(rng.normal(size=(10000,31)),columns=[f'n{i}' for i in range(31)])
        for i in range(8):frame[f'c{i}']=rng.choice(['a','b','c','d','e']+(['f'] if i==0 else []),len(frame))
        frame['fixture_target']=frame.n0*2-frame.n1+rng.normal(size=len(frame))
        target='fixture_target'
    else:
        split_path=root/f'artifacts/analysis/data-audit/dataset-{letter}-split.csv'
        split=pd.read_csv(split_path)
        indices=set(split.loc[split.split=='development','source_row_index_0_based'].tolist())
        source=root/('data/processed/sgemm-model-input.csv' if letter=='a' else 'data/processed/student-model-input.csv')
        # Skip final-test data records while reading. Header row remains.
        frame=pd.read_csv(source,skiprows=lambda i:i>0 and i-1 not in indices)
        expected=193280 if letter=='a' else 519
        assert len(frame)==len(indices)==expected
        target='runtime_mean_ms' if letter=='a' else 'G3'
    X=frame.drop(columns=[target]);y=frame[target].to_numpy(dtype=float)
    if method=='no_prior_ols':X=X.drop(columns=['G1','G2'])
    if method=='log_ols':y=np.log(y)
    load_s=time.perf_counter()-t
    def make_pre(data):
        cat=list(data.select_dtypes(exclude='number'))
        num=[c for c in data if c not in cat]
        return ColumnTransformer([('num',StandardScaler(),num),
          ('cat',OneHotEncoder(drop='first',handle_unknown='ignore',sparse_output=False),cat)],sparse_threshold=0)
    pre=make_pre(X);t=time.perf_counter();Z=pre.fit_transform(X)
    pre_s=time.perf_counter()-t;names=pre.get_feature_names_out().tolist()
    k=max(1,Z.shape[1]//2)
    extra={};fit_t=time.perf_counter()
    with warnings.catch_warnings(record=True) as warning_records:
        warnings.simplefilter('always')
        if method in ['load','preprocess']:
            extra['operation']='load/preprocess only'
        elif method in ['ols','log_ols','no_prior_ols']:
            design=sm.add_constant(Z,has_constant='add')
            fit=sm.OLS(y,design).fit()
            t=time.perf_counter()
            sample=design[:min(len(design),2000)]
            interval=fit.get_prediction(sample).summary_frame(alpha=.05)
            interval_s=time.perf_counter()-t
            assert np.isfinite(interval.to_numpy()).all()
            assert (interval.obs_ci_upper-interval.obs_ci_lower >= interval.mean_ci_upper-interval.mean_ci_lower).all()
            # Check package interoperability against an independent sklearn fit.
            check=LinearRegression().fit(Z,y).predict(Z[:len(sample)])
            agreement=float(np.max(np.abs(check-interval['mean'].to_numpy())))
            assert agreement<1e-6
            extra.update(interval_rows=len(sample),interval_s=interval_s,
                         sklearn_statsmodels_prediction_max_error=agreement,
                         design_rank=int(np.linalg.matrix_rank(design)),design_columns=design.shape[1],
                         response_scale='natural log ms' if method=='log_ols' else 'source target units',
                         illustrative_interval_json_bytes=len(interval.to_json(orient='records').encode()))
        elif method=='kbest':
            selector=SelectKBest(f_regression,k=k).fit(Z,y)
            chosen=np.where(selector.get_support())[0].tolist()
            LinearRegression().fit(Z[:,chosen],y)
            extra.update(selected_encoded_columns=len(chosen),candidate_encoded_columns=len(names),refit_ols=True)
        elif method=='rfe':
            selector=RFE(LinearRegression(),n_features_to_select=k,step=1).fit(Z,y)
            chosen=np.where(selector.support_)[0].tolist()
            LinearRegression().fit(Z[:,chosen],y)
            extra.update(selected_encoded_columns=len(chosen),candidate_encoded_columns=len(names),refit_ols=True)
        elif method in ['lasso','elasticnet']:
            ys=(y-y.mean())/y.std()
            selector=(Lasso(alpha=.001,max_iter=10000,tol=1e-5) if method=='lasso' else
                      ElasticNet(alpha=.001,l1_ratio=.5,max_iter=10000,tol=1e-5)).fit(Z,ys)
            chosen=np.flatnonzero(np.abs(selector.coef_)>1e-10).tolist()
            if chosen:LinearRegression().fit(Z[:,chosen],y)
            extra.update(selected_encoded_columns=len(chosen),candidate_encoded_columns=len(names),
                         alpha=.001,target_standardized_for_selector=True,refit_ols=bool(chosen),iterations=int(selector.n_iter_),
                         parameter_scope='single fixed feasibility setting; not tuned performance')
        elif method=='sfs':
            # Cache transforms only after fitting each one to that CV training fold.
            # Fold validation categories are never fitted. Missing train categories
            # yield zero columns on alignment; no target-driven preprocessing.
            folds=[];t=time.perf_counter()
            for train,val in KFold(3,shuffle=True,random_state=17).split(X):
                pp=make_pre(X.iloc[train]);zt=pp.fit_transform(X.iloc[train]);zv=pp.transform(X.iloc[val])
                lookup={name:i for i,name in enumerate(pp.get_feature_names_out())}
                def align(matrix):
                    full=np.zeros((len(matrix),len(names)))
                    for j,name in enumerate(names):
                        if name in lookup:full[:,j]=matrix[:,lookup[name]]
                    return full
                folds.append((align(zt),align(zv),y[train],y[val]))
            cache_s=time.perf_counter()-t
            selected=[];fits=0
            for step in range(k):
                best=None
                for candidate in range(len(names)):
                    if candidate in selected:continue
                    cols=selected+[candidate];losses=[]
                    for zt,zv,yt,yv in folds:
                        pred=LinearRegression().fit(zt[:,cols],yt).predict(zv[:,cols])
                        losses.append(mean_squared_error(yv,pred));fits+=1
                    item=(float(np.mean(losses)),candidate)
                    if best is None or item<best:best=item
                selected.append(best[1])
            LinearRegression().fit(Z[:,selected],y)
            extra.update(selected_encoded_columns=len(selected),candidate_encoded_columns=len(names),
                         cv_folds=3,cv_regression_fits=fits,fold_preprocessing_cache_s=cache_s,
                         preprocessing_scope='Each CV training fold fit independently; held-out fold transformed only.',refit_ols=True)
        else:raise ValueError(method)
    fit_s=time.perf_counter()-fit_t
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_bytes=int(peak if sys.platform=='darwin' else peak*1024)
    result={'dataset':dataset,'method':method,'status':'passed','development_rows':len(X),
       'raw_input_fields':X.shape[1],'encoded_columns':Z.shape[1],
       'import_s':imports_s,'load_s':load_s,'preprocess_s':pre_s,'operation_s':fit_s,
       'wall_s_including_import':time.perf_counter()-started,'cpu_s':time.process_time()-cpu_started,
       'peak_rss_bytes':peak_bytes,'threads_limit':1,'threadpools':threadpool_info(),
       'warning_categories':sorted(set(type(w.message).__name__ for w in warning_records)),
       'final_test_rows_read':0,'model_scope':'feasibility only; no final scores or model export',
       'source_nature':'generated resource-bound fixture, not formal data or third-dataset bonus evidence' if dataset=='stress' else 'actual published development records',**extra}
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['dataset','method','wall_s_including_import','operation_s','peak_rss_bytes','warning_categories']}),flush=True)


def supervise(root,out,stress=False):
    out.mkdir(parents=True,exist_ok=True);results=[]
    cases=[(ds,m) for ds in ['sgemm','student'] for m in ['load','preprocess','ols','kbest','rfe','sfs','lasso','elasticnet']]
    cases += [('sgemm','log_ols'),('student','no_prior_ols')]
    if stress:cases=[('stress',m) for m in ['ols','kbest','rfe','sfs','lasso','elasticnet']]
    for ds,method in cases:
        path=out/f'{ds}-{method}.json';started=time.perf_counter()
        try:
            r=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--root',str(root),'--dataset',ds,
                              '--method',method,'--output',str(path)],capture_output=True,text=True,timeout=300,env=os.environ.copy())
            if r.returncode:
                failure={'dataset':ds,'method':method,'status':'failed','stderr':r.stderr[-5000:]}
                path.write_text(json.dumps(failure,indent=2)+'\n');results.append(failure)
                print(json.dumps(failure),flush=True)
            else:
                data=json.loads(path.read_text());data['fresh_process_wall_s']=time.perf_counter()-started
                path.write_text(json.dumps(data,indent=2)+'\n');results.append(data);print(r.stdout.strip(),flush=True)
        except subprocess.TimeoutExpired:
            data={'dataset':ds,'method':method,'status':'timeout','budget_s':300}
            path.write_text(json.dumps(data,indent=2)+'\n');results.append(data);print(json.dumps(data),flush=True)
        (out/'summary.json').write_text(json.dumps({'scope':'local single-threaded development-only feasibility; not Vercel execution',
          'cases':results},indent=2)+'\n')
    assert all(r['status']=='passed' for r in results),'Inspect failed benchmark cases.'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--dataset');p.add_argument('--method');p.add_argument('--output',type=Path)
    p.add_argument('--stress',action='store_true')
    args=p.parse_args();root=args.root.resolve()
    if args.dataset:run_case(root,args.dataset,args.method,args.output.resolve())
    else:supervise(root,args.output.resolve(),args.stress)
