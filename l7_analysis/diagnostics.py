"""Development-only OLS diagnostics and influence sensitivity, never deletion rules."""
import numpy as np
from scipy import stats
import statsmodels.api as sm
from statsmodels.stats.diagnostic import het_breuschpagan

def probability(value):
    value=float(value)
    return {'p_value':value,'p_display':'< floating-point resolution' if value==0 else f'{value:.4g}'}

def influence_arrays(bundle):
    fit=bundle['fit'];X=bundle['design'];q=X.shape[1]
    h=np.einsum('ij,jk,ik->i',X,fit.normalized_cov_params,X)
    if (h>=1-1e-12).any():return {'status':'unavailable_leverage_near_one'}
    residual=np.asarray(fit.resid);sigma2=float(fit.mse_resid)
    studentized=residual/np.sqrt(sigma2*(1-h))
    cook=residual**2*h/(q*sigma2*(1-h)**2)
    return {'status':'available','leverage':h,'studentized_internal':studentized,'cooks_distance':cook}

def deletion_sensitivity(bundle,index):
    """Exact one-row OLS deletion identity; not a new selected/production model."""
    X=bundle['design'];fit=bundle['fit'];influence=influence_arrays(bundle)
    if influence['status']!='available':return {'status':influence['status']}
    h=influence['leverage'][index]
    delta=-(fit.normalized_cov_params@X[index])*fit.resid[index]/(1-h)
    shift=X@delta
    return {'status':'diagnostic_only','deleted_training_position_for_sensitivity':int(index),
      'coefficients_after_one_row_deletion':(fit.params+delta).tolist(),
      'max_absolute_coefficient_change':float(np.abs(delta).max()),
      'development_fitted_change_rms':float(np.sqrt(np.mean(shift**2))),
      'development_fitted_change_max_abs':float(np.abs(shift).max()),
      'response_scale':'log target' if bundle['artifact']['target_transform']=='log' else 'original target units',
      'production_model_changed':False,'test_rows_deleted':0}

def diagnose(bundle,source_ids,max_points=2000):
    if bundle['status']!='available':return {'status':bundle['status']},{}
    X=bundle['design'];fit=bundle['fit'];resid=np.asarray(fit.resid);fitted=np.asarray(fit.fittedvalues)
    n,q=X.shape;artifact=bundle['artifact'];spec=bundle['spec'];influence=influence_arrays(bundle)
    jb=stats.jarque_bera(resid)
    normal={'test':'Jarque-Bera on all development residuals','statistic':float(jb.statistic),**probability(jb.pvalue),
            'skewness':float(stats.skew(resid,bias=False)),'excess_kurtosis':float(stats.kurtosis(resid,fisher=True,bias=False)),
            'interpretation':'Large-sample p-values are sensitive; use residual shape and effects, not a pass/fail label.'}
    hetero={'status':'unavailable_intercept_only'}
    if q>1:
        lm,p,f,fp=het_breuschpagan(resid,X,robust=True)
        hetero={'status':'computed','test':'Koenker/studentized Breusch-Pagan','lm_statistic':float(lm),**probability(p),
                'f_statistic':float(f),'f_p_value':float(fp),
                'corr_abs_residual_fitted':float(np.corrcoef(np.abs(resid),fitted)[0,1]) if fitted.std()>0 else None}
    reset={'status':'unavailable_constant_or_collinear_fitted_response'}
    if fitted.std()>0:
        z=(fitted-fitted.mean())/fitted.std();aug=np.column_stack([X,z*z])
        if np.linalg.matrix_rank(aug)==q+1 and n>q+1:
            test=sm.OLS(bundle['response'],aug).fit(cov_type='HC3',use_t=True).f_test(np.eye(q+1)[-1:])
            reset={'status':'computed','test':'Quadratic fitted-value RESET-style test with HC3 covariance',
                   'f_statistic':float(np.asarray(test.fvalue).item()),**probability(np.asarray(test.pvalue).item()),
                   'diagnostic_only':True,'frozen_model_replaced':False}
    vif=[]
    for j,column in enumerate(artifact['selected_columns'],1):
        auxiliary=np.delete(X,j,axis=1);values=X[:,j]
        residual=values-auxiliary@np.linalg.lstsq(auxiliary,values,rcond=None)[0]
        total=float(np.square(values-values.mean()).sum());den=float(np.square(residual).sum())
        vif.append({'key':column['key'],'label':column['label'],'vif':float(total/den) if den>np.finfo(float).eps*total else None,
                    'status':'finite' if den>np.finfo(float).eps*total else 'infinite_or_near_collinear'})
    sample=np.linspace(0,n-1,min(n,max_points),dtype=int)
    quantile_positions=np.linspace(0,n-1,min(n,max_points),dtype=int)
    ordered=np.sort(resid/np.sqrt(fit.mse_resid))
    plot={'scope':'development diagnostics; display thinning only, statistics use every development row',
      'sample_development_positions':sample.tolist(),'sample_source_rows':np.asarray(source_ids)[sample].tolist(),
      'fitted':fitted[sample].tolist(),'residual':resid[sample].tolist(),
      'qq_theoretical':stats.norm.ppf((quantile_positions+.5)/n).tolist(),'qq_observed':ordered[quantile_positions].tolist()}
    influence_summary={'status':influence['status']}
    top=[];sensitivity={'status':'unavailable'}
    if influence['status']=='available':
        h=influence['leverage'];cook=influence['cooks_distance'];student=influence['studentized_internal']
        top_indices=np.argsort(cook)[-min(20,n):][::-1]
        for i in top_indices:
            top.append({'development_position':int(i),'source_row_index_0_based':int(source_ids[i]),
             'leverage':float(h[i]),'cooks_distance':float(cook[i]),'studentized_internal':float(student[i]),'residual':float(resid[i])})
        influence_summary={'status':'available','cook_heuristic':4/n,'leverage_heuristic':2*q/n,
          'cook_flagged_rows':int((cook>4/n).sum()),'leverage_flagged_rows':int((h>2*q/n).sum()),
          'max_cooks_distance':float(cook.max()),'max_leverage':float(h.max()),'top_rows':top,
          'interpretation':'Heuristics locate potentially influential training observations; none are automatically deleted.'}
        sensitivity=deletion_sensitivity(bundle,int(top_indices[0]))
        sensitivity['source_row_index_0_based']=int(source_ids[top_indices[0]])
        plot.update(leverage=h[sample].tolist(),studentized_internal=student[sample].tolist(),cooks_distance=cook[sample].tolist())
    diagnostics={'status':'computed','training_rows':n,'design_columns_including_intercept':q,
      'response_scale':'natural log target' if artifact['target_transform']=='log' else 'original target units',
      'development_ols_r2':float(fit.rsquared),'development_ols_adjusted_r2':float(fit.rsquared_adj),
      'development_residual_df':float(fit.df_resid),'residual_std':float(np.sqrt(fit.mse_resid)),
      'normality':normal,'heteroskedasticity':hetero,'functional_form':reset,'vif':vif,
      'condition_number_standardized_design':float(np.linalg.cond(X)),
      'influence':influence_summary,'sensitivity':sensitivity,
      'independence':{'status':'not_established','reason':'No temporal ordering or sufficient independent clusters established. Random row order is not a time series; no mechanical Durbin-Watson test.',
        'source_limit':'Student data come from only two schools; GPU data come from one benchmark hardware/workload. HC3 does not establish independence.'},
      'post_selection_caveat':spec['selection_conditioning'],'hc3_caveat':spec['HC3_scope']}
    return diagnostics,plot
