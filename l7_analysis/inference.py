"""Conditional OLS uncertainty for frozen models; no feature/parameter selection.

HC3 is used for coefficient/location uncertainty only. The observation PI keeps
the classical homoskedastic noise model and is never called heteroskedastic-robust.
"""
import hashlib
import json
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.api as sm
from .config import InputError,OLS_METHODS
from .preprocessing import FrameEncoder
from .models import response,predict_artifact

def equation_hash(artifact):
    selected={'preprocessor':artifact['preprocessor'],'selected_keys':artifact['selected_keys'],
       'coefficients':artifact['model']['coefficients'],'intercept':artifact['model']['intercept'],
       'target':artifact['target'],'transform':artifact['target_transform']}
    return hashlib.sha256(json.dumps(selected,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def design_for(artifact,frame):
    encoder=FrameEncoder.from_spec(artifact['preprocessor'])
    encoded,notes=encoder.transform(frame,artifact['selected_keys'])
    return np.column_stack([np.ones(len(frame)),encoded]),notes

def fit_inference(artifact,training,alpha=.05):
    if not 0<alpha<1:raise InputError('alpha must be between zero and one.')
    if artifact['method'] not in OLS_METHODS:raise InputError('Classical OLS inference is not attached to regularized/baseline models.')
    design,_=design_for(artifact,training)
    y=response(training[artifact['target']].to_numpy(dtype=float),artifact['target_transform'])
    if not np.isfinite(y).all():raise InputError('Training target must be finite.')
    fit=sm.OLS(y,design).fit()
    bundle={'status':'available','fit':fit,'design':design,'response':y,'artifact':artifact,'spec':None}
    rank=int(np.linalg.matrix_rank(design))
    if rank<design.shape[1] or len(y)<=rank:
        bundle['status']='unavailable_rank_or_df';return bundle
    expected=np.r_[artifact['model']['intercept'],artifact['model']['coefficients']]
    if not np.allclose(fit.params,expected,rtol=1e-7,atol=1e-7):raise InputError('Frozen coefficient and OLS reconstruction mismatch.')
    floor=np.finfo(float).eps*max(float(np.var(y)),1.)
    if not np.isfinite(fit.mse_resid) or fit.mse_resid<=floor:
        bundle['status']='unavailable_numerically_zero_residual_variance';return bundle
    robust=fit.get_robustcov_results(cov_type='HC3',use_t=True)
    if not np.isfinite(robust.cov_params()).all():
        bundle['status']='unavailable_nonfinite_HC3_covariance';return bundle
    bundle['robust']=robust
    bundle['spec']={'schema_version':'1.0','status':'computed_under_conditional_OLS_assumptions',
       'model_equation_sha256':equation_hash(artifact),'alpha':alpha,'coefficients_with_intercept':fit.params.tolist(),
       'covariance_classical':fit.cov_params().tolist(),'covariance_hc3':robust.cov_params().tolist(),
       'mse_resid':float(fit.mse_resid),'df_resid':float(fit.df_resid),'training_rows':len(y),
       'design_columns_including_intercept':design.shape[1],'design_rank':rank,
       'target_transform':artifact['target_transform'],
       'location_kind':'conditional_arithmetic_mean' if artifact['target_transform']=='identity' else 'exp(E[log(Y)|X]), geometric location; not arithmetic conditional mean',
       'observation_kind':'new row target under homoskedastic Gaussian regression error; GPU target is mean of four runs',
       'HC3_scope':'coefficient and location CI only; not a robust observation PI',
       'selection_conditioning':'Intervals condition on selected columns and fitted preprocessing; feature-selection uncertainty not corrected.'}
    return bundle

def predict_with_intervals(artifact,spec,frame,alpha=None):
    if spec['model_equation_sha256']!=equation_hash(artifact):raise InputError('Interval specification does not match frozen model.')
    alpha=spec['alpha'] if alpha is None else alpha
    if not 0<alpha<1:raise InputError('Invalid alpha.')
    if spec['df_resid']<=0 or spec['mse_resid']<=0:raise InputError('Positive residual df and variance required.')
    X,notes=design_for(artifact,frame);beta=np.asarray(spec['coefficients_with_intercept'])
    if len(beta)!=X.shape[1]:raise InputError('Interval design dimensions disagree.')
    reg=X@beta;t=float(stats.t.ppf(1-alpha/2,spec['df_resid']))
    def variance(cov):
        matrix=np.asarray(cov,dtype=float)
        if matrix.shape!=(X.shape[1],X.shape[1]):raise InputError('Invalid covariance dimensions.')
        v=np.einsum('ij,jk,ik->i',X,matrix,X)
        if not np.isfinite(v).all() or (v < -1e-8).any():raise InputError('Invalid prediction variance.')
        return np.maximum(v,0.)
    vm=variance(spec['covariance_classical']);vr=variance(spec['covariance_hc3'])
    hm=t*np.sqrt(vm);hr=t*np.sqrt(vr);hp=t*np.sqrt(vm+spec['mse_resid'])
    result=pd.DataFrame({'regression_location':reg,'regression_location_ci_lower':reg-hm,
      'regression_location_ci_upper':reg+hm,'regression_observation_pi_lower':reg-hp,
      'regression_observation_pi_upper':reg+hp,'regression_location_ci_hc3_lower':reg-hr,
      'regression_location_ci_hc3_upper':reg+hr})
    mapping={'prediction':'regression_location','location_ci_lower':'regression_location_ci_lower',
      'location_ci_upper':'regression_location_ci_upper','observation_pi_lower':'regression_observation_pi_lower',
      'observation_pi_upper':'regression_observation_pi_upper','location_ci_hc3_lower':'regression_location_ci_hc3_lower',
      'location_ci_hc3_upper':'regression_location_ci_hc3_upper'}
    for name,source in mapping.items():
        with np.errstate(over='ignore'):result[name]=np.exp(result[source]) if spec['target_transform']=='log' else result[source]
    if not np.isfinite(result.to_numpy()).all():raise InputError('Non-finite interval endpoints; no clipping performed.')
    frozen,_=predict_artifact(artifact,frame)
    if not np.allclose(result.prediction,frozen,rtol=1e-7,atol=1e-7):raise InputError('Frozen prediction and interval model disagree.')
    return result,notes

def coefficient_intervals(bundle):
    if bundle['status']!='available':return []
    artifact=bundle['artifact'];spec=bundle['spec'];fit=bundle['fit'];q=len(fit.params)
    lookup={x['key']:i for i,x in enumerate(artifact['preprocessor']['columns'])}
    positions=[lookup[k] for k in artifact['selected_keys']]
    scale=np.asarray(artifact['preprocessor']['scale'])[positions];center=np.asarray(artifact['preprocessor']['center'])[positions]
    T=np.eye(q)
    if q>1:T[0,1:]=-center/scale;T[1:,1:]=np.diag(1/scale)
    labels=['Intercept']+[x['label'] for x in artifact['selected_columns']]
    critical=stats.t.ppf(1-spec['alpha']/2,spec['df_resid']);rows=[]
    for basis,operator in [('standardized_encoded',np.eye(q)),('unscaled_encoded',T)]:
        beta=operator@fit.params
        for cov_name,cov in [('classical',fit.cov_params()),('HC3',bundle['robust'].cov_params())]:
            se=np.sqrt(np.maximum(np.diag(operator@cov@operator.T),0.))
            for i,label in enumerate(labels):
                rows.append({'column':label,'basis':basis,'covariance':cov_name,'coefficient':float(beta[i]),
                  'standard_error':float(se[i]),'ci_lower':float(beta[i]-critical*se[i]),'ci_upper':float(beta[i]+critical*se[i]),
                  'p_value':float(2*stats.t.sf(abs(beta[i]/se[i]),spec['df_resid'])) if se[i]>0 else None,
                  'response_scale':'natural log target' if spec['target_transform']=='log' else 'original target units',
                  'interpretation':'conditional association after model selection; not causal'})
    return rows

def interval_summary(actual,intervals):
    y=np.asarray(actual);lower=intervals.observation_pi_lower.to_numpy();upper=intervals.observation_pi_upper.to_numpy()
    if len(y)!=len(lower):raise InputError('Coverage input length mismatch.')
    covered=(y>=lower)&(y<=upper)
    return {'rows':len(y),'covered_count':int(covered.sum()),'observation_pi_coverage':float(covered.mean()),
      'observation_pi_mean_width':float(np.mean(upper-lower)),
      'location_ci_mean_width':float(np.mean(intervals.location_ci_upper-intervals.location_ci_lower)),
      'location_ci_hc3_mean_width':float(np.mean(intervals.location_ci_hc3_upper-intervals.location_ci_hc3_lower)),
      'location_ci_coverage_against_individual_y':None,
      'location_ci_coverage_reason':'Individual observations do not reveal the true conditional mean.',
      'negative_prediction_count':int((intervals.prediction<0).sum()),'negative_pi_lower_count':int((lower<0).sum()),
      'coverage_interpretation':'descriptive held-out observation-PI coverage; not an assumption test or guaranteed future coverage'}
