from pathlib import Path
import argparse,json,os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/l7-stage4-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

TITLES={'sgemm':'GPU runtime - primary OLS','sgemm_log':'GPU runtime - log-target supplement',
 'student':'Student grades - prior grades included','student_background':'Student grades - background only'}
METHODS={'dummy':'Mean baseline','ols':'All-feature OLS','kbest':'SelectKBest -> OLS','rfe':'RFE -> OLS',
 'sfs':'Forward SFS -> OLS','lasso_select':'Lasso selection -> OLS','elasticnet_select':'ElasticNet selection -> OLS',
 'ridge':'Ridge prediction','lasso_reg':'Lasso prediction'}

def main(root):
    out=root/'artifacts/analysis/evaluation';coef=pd.read_csv(out/'coefficient-intervals.csv')
    rendered=[]
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    for scenario,title in TITLES.items():
        case=json.loads((out/scenario/'evaluation.json').read_text());rep=case['representative'];directory=out/scenario
        p=json.loads((root/rep['interval_plot_data_path']).read_text());v={k:np.asarray(x) for k,x in p['rows'].items()}
        spec=json.loads((root/rep['interval_spec_path']).read_text())
        diagnostic=json.loads((root/rep['diagnostics_path']).read_text())
        d=json.loads((root/rep['diagnostic_plot_data_path']).read_text())
        unit='ms' if scenario.startswith('sgemm') else 'grade points'
        location='Geometric-location CI' if scenario=='sgemm_log' else 'Mean-response CI'
        x=v['prediction_rank']
        fig,ax=plt.subplots(1,2,figsize=(15,5.4),layout='constrained')
        ax[0].fill_between(x,v['observation_pi_lower'],v['observation_pi_upper'],color='#d7e4f4',label='95% classical observation PI')
        ax[0].fill_between(x,v['location_ci_lower'],v['location_ci_upper'],color='#315c99',alpha=.45,label='95% '+location)
        ax[0].plot(x,v['prediction'],color='#244a7a',lw=1.1,label='Frozen-model point prediction')
        ax[0].scatter(x,v['actual'],s=6,color='#b47734',alpha=.5,label='Held-out observations')
        coverage=rep['interval_summary']['observation_pi_coverage']
        ax[0].set(xlabel='Held-out sample rank, sorted by frozen prediction',ylabel='Target ('+unit+')',
                  title=f'Nominal 95% PI | observed coverage {coverage:.2%}')
        ax[0].legend(fontsize=8,loc='upper left')
        classic=(v['location_ci_upper']-v['location_ci_lower'])/2
        hc3=(v['location_ci_hc3_upper']-v['location_ci_hc3_lower'])/2
        ax[1].plot(x,classic,label='Classical location CI half-width',color='#315c99')
        ax[1].plot(x,hc3,label='HC3 location CI half-width',color='#198c83')
        ax[1].set(xlabel='Held-out prediction rank',ylabel='CI half-width ('+unit+')',title='Location uncertainty only; HC3 does not repair PI noise')
        ax[1].legend(fontsize=8)
        fig.suptitle(title+' | conditional intervals after feature selection',fontsize=14)
        path=directory/'intervals.png';fig.savefig(path,dpi=160);plt.close(fig);rendered.append(str(path.relative_to(root)))

        fig,ax=plt.subplots(2,2,figsize=(13,9),layout='constrained')
        fitted=np.asarray(d['fitted']);residual=np.asarray(d['residual']);student=np.asarray(d['studentized_internal'])
        ax[0,0].scatter(fitted,residual,s=7,alpha=.35,color='#315c99');ax[0,0].axhline(0,color='#777',ls='--')
        ax[0,0].set(xlabel='Development fitted response',ylabel='Residual',title='Residual pattern (display sample)')
        theoretical=np.asarray(d['qq_theoretical']);observed=np.asarray(d['qq_observed'])
        ax[0,1].scatter(theoretical,observed,s=6,alpha=.5,color='#315c99')
        limits=[min(theoretical.min(),observed.min()),max(theoretical.max(),observed.max())]
        ax[0,1].plot(limits,limits,color='#777',ls='--');ax[0,1].set(xlabel='Standard normal quantile',ylabel='Standardized residual quantile',title='Q-Q: quantiles from all development residuals')
        ax[1,0].scatter(fitted,np.sqrt(np.abs(student)),s=7,alpha=.35,color='#198c83')
        ax[1,0].set(xlabel='Development fitted response',ylabel='sqrt(abs(internally studentized residual))',title='Scale-location pattern')
        ax[1,1].scatter(d['leverage'],student,s=8,alpha=.3,color='#315c99',label='Display sample')
        top=diagnostic['influence']['top_rows']
        ax[1,1].scatter([x['leverage'] for x in top],[x['studentized_internal'] for x in top],s=32,marker='x',color='#b47734',label="Top 20 Cook's distance")
        ax[1,1].axhline(0,color='#777',ls='--');ax[1,1].set(xlabel='Leverage',ylabel='Internally studentized residual',title='Influential training observations; none deleted')
        ax[1,1].legend(fontsize=8)
        fig.suptitle(title+' | development diagnostics, not pass/fail guarantees',fontsize=14)
        path=directory/'diagnostics.png';fig.savefig(path,dpi=160);plt.close(fig);rendered.append(str(path.relative_to(root)))

        selected=coef[(coef.scenario==scenario)&(coef.candidate_id==rep['candidate_id'])&(coef.basis=='standardized_encoded')&(coef.column!='Intercept')]
        classical=selected[selected.covariance=='classical'];robust=selected[selected.covariance=='HC3']
        names=classical.column.tolist();positions=np.arange(len(names))
        fig,ax=plt.subplots(1,2,figsize=(14,6),layout='constrained')
        for records,offset,color,label in [(classical,-.12,'#315c99','Classical 95% CI'),(robust,.12,'#198c83','HC3 95% CI')]:
            beta=records.coefficient.to_numpy();errors=np.vstack([beta-records.ci_lower,records.ci_upper-beta])
            ax[0].errorbar(beta,positions+offset,xerr=errors,fmt='o',ms=3,color=color,label=label,capsize=2)
        ax[0].axvline(0,color='#777',ls='--');ax[0].set(yticks=positions,yticklabels=names,
          xlabel='Effect per 1 SD encoded input ('+('log target' if scenario=='sgemm_log' else unit)+')',title='Conditional coefficient intervals; not causal effects')
        ax[0].legend(fontsize=8)
        vif=diagnostic['vif'];values=[r['vif'] if r['vif'] is not None else np.nan for r in vif]
        ax[1].barh(np.arange(len(vif)),values,color='#315c99')
        ax[1].set(yticks=np.arange(len(vif)),yticklabels=[r['label'] for r in vif],xlabel='Variance inflation factor',title='Collinearity in selected standardized design')
        fig.suptitle(title+' | coefficient uncertainty and VIF',fontsize=14)
        path=directory/'coefficients-vif.png';fig.savefig(path,dpi=160);plt.close(fig);rendered.append(str(path.relative_to(root)))

    fig,ax=plt.subplots(1,2,figsize=(17,6),layout='constrained')
    for axis,scenario in zip(ax,['sgemm','student']):
        case=json.loads((out/scenario/'evaluation.json').read_text());dev=json.loads((root/'artifacts/analysis/models'/scenario/'result.json').read_text())
        ordered=[next(x for x in case['models'] if x['method']==m) for m in METHODS]
        cv=[next(c['cv']['rmse'] for c in dev['cv_results'] if c['id']==x['candidate_id']) for x in ordered]
        test=[x['test_metrics']['rmse'] for x in ordered];p=np.arange(len(ordered))
        axis.barh(p-.17,cv,height=.32,color='#b8c9dd',label='Tuning CV RMSE')
        axis.barh(p+.17,test,height=.32,color=['#b47734' if x['representative_frozen'] else '#315c99' for x in ordered],label='Held-out RMSE')
        axis.set(yticks=p,yticklabels=[METHODS[x['method']]+(' *' if x['representative_frozen'] else '') for x in ordered],
                 xlabel='RMSE ('+('ms' if scenario=='sgemm' else 'grade points')+')',title=TITLES[scenario])
        axis.invert_yaxis();axis.legend(fontsize=8)
    fig.suptitle('Fixed-method evaluation | * representative frozen from development CV',fontsize=14)
    path=out/'test-comparison.png';fig.savefig(path,dpi=160);plt.close(fig);rendered.append(str(path.relative_to(root)))
    (out/'plots-manifest.json').write_text(json.dumps({'rendered':rendered,'count':len(rendered),'scope':'4 frozen representatives plus fixed-order primary method comparison'},indent=2)+'\n')
    print(json.dumps({'rendered':len(rendered)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();main(a.root.resolve())
