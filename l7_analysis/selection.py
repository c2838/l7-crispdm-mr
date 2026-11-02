import numpy as np
import pandas as pd
from sklearn.feature_selection import SelectKBest,f_regression,RFE
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import KFold,GroupKFold
from .config import InputError
from .preprocessing import FrameEncoder
from .models import response

def folds_for(frame,n_splits,seed,groups=None):
    if len(frame)<n_splits*2:raise InputError('Insufficient observations for the requested CV folds.')
    if groups is not None:
        if len(np.unique(groups))<n_splits:raise InputError('Insufficient independent groups for CV.')
        pairs=list(GroupKFold(n_splits=n_splits,shuffle=True,random_state=seed).split(frame,groups=groups))
    else:pairs=list(KFold(n_splits=n_splits,shuffle=True,random_state=seed).split(frame))
    for tr,va in pairs:
        assert not set(tr)&set(va)
        if groups is not None:assert not set(groups[tr])&set(groups[va])
    return pairs

def kbest_path(Z,y,transform,ks,guard):
    # Use the real SelectKBest estimator; each mask is trained on this fold only.
    result={}
    for k in ks:
        guard.check();selector=SelectKBest(f_regression,k=k).fit(Z,response(y,transform))
        result[k]=np.flatnonzero(selector.get_support()).tolist()
    return result

def rfe_path(Z,y,transform,ks,guard):
    guard.check()
    # RFE(step=1,target=1) yields the full nested elimination ordering.
    selector=RFE(LinearRegression(),n_features_to_select=1,step=1).fit(Z,response(y,transform))
    ordering=np.argsort(selector.ranking_,kind='stable')
    guard.check()
    return {k:sorted(ordering[:k].tolist()) for k in ks}

def sfs_path(frame,y,keys,transform,ks,config,guard,groups=None):
    if not ks:return {},{'regression_fits':0,'inner_folds':config.inner_folds}
    cached=[]
    for tr,va in folds_for(frame,config.inner_folds,config.seed+101,groups):
        guard.check();enc=FrameEncoder(config.categorical).fit(frame.iloc[tr])
        cached.append((enc.transform(frame.iloc[tr],keys)[0],enc.transform(frame.iloc[va],keys)[0],
                       response(y[tr],transform),y[va]))
    selected=[];paths={};fits=0;trace=[]
    for step in range(max(ks)):
        guard.check();remaining=[i for i in range(len(keys)) if i not in selected]
        if len(remaining)==1:
            chosen=remaining[0];best_loss=None
        else:
            best=None
            for candidate in remaining:
                guard.check();cols=selected+[candidate];sse=0.;n=0
                for Zt,Zv,yt,yv in cached:
                    guard.check();pred=LinearRegression().fit(Zt[:,cols],yt).predict(Zv[:,cols]);fits+=1
                    if transform=='log':
                        with np.errstate(over='ignore'):pred=np.exp(pred)
                    if not np.isfinite(pred).all():raise InputError('SFS prediction overflow.')
                    sse+=float(np.square(yv-pred).sum());n+=len(yv)
                item=(sse/n,candidate)
                if best is None or item<best:best=item
            best_loss,chosen=best
        selected.append(chosen)
        if len(selected) in ks:paths[len(selected)]=sorted(selected)
        trace.append({'k':len(selected),'added_key':keys[chosen],'inner_mse_original_units':best_loss,
                      'trivial_final_step':len(remaining)==1})
    return paths,{'regression_fits':fits,'inner_folds':config.inner_folds,'trace':trace,
                  'preprocessing_scope':'Each inner training fold fitted independently; cache shared only among its candidates.'}
