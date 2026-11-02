import warnings
import numpy as np
from sklearn.linear_model import LinearRegression,Ridge,Lasso,ElasticNet
from sklearn.exceptions import ConvergenceWarning
from .config import InputError
from .preprocessing import FrameEncoder

def response(y,transform):
    if transform=='log':
        if (y<=0).any():raise InputError('Log target requires strictly positive values.')
        return np.log(y)
    return np.asarray(y,dtype=float)

def fit_linear(Z,y,transform='identity',kind='ols',alpha=None):
    values=response(y,transform);center=float(values.mean());scale=float(values.std()) or 1.
    if Z.shape[1]==0:
        return {'coefficients':[],'intercept':center,'design_rank':1,'design_columns':1,
                'inference_status':'eligible_intercept_only' if len(y)>1 else 'insufficient_df','warning_categories':[]}
    estimator=Ridge(alpha=alpha) if kind=='ridge' else Lasso(alpha=alpha,max_iter=20000,tol=1e-7) if kind=='lasso_reg' else LinearRegression()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always');estimator.fit(Z,(values-center)/scale)
    if any(isinstance(w.message,ConvergenceWarning) for w in caught):raise RuntimeError('ConvergenceWarning: candidate not eligible for selection.')
    coef=np.asarray(estimator.coef_)*scale;intercept=float(estimator.intercept_*scale+center)
    rank=int(np.linalg.matrix_rank(np.column_stack([np.ones(len(Z)),Z])))
    eligible=rank==Z.shape[1]+1 and len(Z)>rank
    return {'coefficients':coef.tolist(),'intercept':intercept,'design_rank':rank,'design_columns':Z.shape[1]+1,
            'inference_status':('eligible_pending_diagnostics' if eligible else 'unavailable_rank_or_df') if kind=='ols' else 'regularized_not_OLS_inference',
            'warning_categories':sorted(set(type(w.message).__name__ for w in caught))}

def predict_linear(model,Z,transform='identity'):
    value=Z@np.asarray(model['coefficients'])+model['intercept']
    if transform=='log':
        with np.errstate(over='ignore'):value=np.exp(value)
    if not np.isfinite(value).all():raise InputError('Prediction overflow; no clipping performed.')
    return value

def sparse_selector(Z,y,transform,alpha,l1_ratio=None):
    values=response(y,transform);ys=(values-values.mean())/(values.std() or 1.)
    estimator=Lasso(alpha=alpha,max_iter=20000,tol=1e-7) if l1_ratio is None else ElasticNet(alpha=alpha,l1_ratio=l1_ratio,max_iter=20000,tol=1e-7)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always');estimator.fit(Z,ys)
    if any(isinstance(w.message,ConvergenceWarning) for w in caught):raise RuntimeError('ConvergenceWarning in sparse selector.')
    selected=np.flatnonzero(np.abs(estimator.coef_)>1e-10).tolist()
    return selected,{'nonzero_tolerance':1e-10,'nonzero_count':len(selected),'selector_iterations':int(estimator.n_iter_),
                     'target_standardized_for_selector':True,'zero_coefficients_padded':False}

def predict_artifact(artifact,frame):
    if artifact['method']=='dummy':return np.full(len(frame),artifact['model']['intercept']),{}
    encoder=FrameEncoder.from_spec(artifact['preprocessor'])
    matrix,notes=encoder.transform(frame,artifact['selected_keys'])
    return predict_linear(artifact['model'],matrix,artifact['target_transform']),notes
