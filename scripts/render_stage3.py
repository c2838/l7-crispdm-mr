from pathlib import Path
import argparse,json,os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/l7-stage3-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def render(root):
    out=root/'artifacts/analysis/models';summary=[]
    titles={'sgemm':'GPU runtime - primary OLS analysis','sgemm_log':'GPU runtime - log-target supplement',
            'student':'Student grades - with prior-period grades','student_background':'Student grades - background variables only'}
    labels={'dummy':'Mean baseline','ols':'All-feature OLS','kbest':'SelectKBest -> OLS','rfe':'RFE -> OLS','sfs':'Forward SFS -> OLS',
            'lasso_select':'Lasso selection -> OLS','elasticnet_select':'ElasticNet selection -> OLS','ridge':'Ridge prediction','lasso_reg':'Lasso prediction'}
    for scenario,title in titles.items():
        r=json.loads((out/scenario/'result.json').read_text());items=[x for x in r['cv_results'] if x['status']=='completed']
        fig,ax=plt.subplots(1,2,figsize=(15,5),layout='constrained')
        for method,color in [('kbest','#315c99'),('rfe','#198c83'),('sfs','#b47734')]:
            rows=sorted([x for x in items if x['method']==method],key=lambda x:x['parameters']['k'])
            ax[0].plot([x['parameters']['k'] for x in rows],[x['cv']['rmse'] for x in rows],label=labels[method],color=color,linewidth=1.6)
        baseline=next(x for x in items if x['method']=='ols')['cv']['rmse']
        ax[0].axhline(baseline,ls='--',color='#6f7580',label='All-feature OLS')
        ax[0].set(xlabel='Selected encoded columns (k)',ylabel='Development CV RMSE (ms)' if scenario.startswith('sgemm') else 'Development CV RMSE (grade points)',title='Feature-count comparison')
        ax[0].legend(fontsize=8)
        chosen=[next(x for x in items if x['id']==r['method_winner_ids'][m]) for m in labels]
        values=[x['cv']['rmse'] for x in chosen]
        colors=['#b47734' if x['id']==r['representative_candidate_id'] else '#315c99' for x in chosen]
        ax[1].barh(np.arange(len(chosen)),values,color=colors)
        ax[1].set(yticks=range(len(chosen)),yticklabels=[labels[x['method']] for x in chosen],
                  xlabel='Development CV RMSE (lower is better)',title='Best explored setting per method')
        ax[1].invert_yaxis()
        for i,v in enumerate(values):ax[1].text(v+max(values)*.01,i,f'{v:.3f}',va='center',fontsize=8)
        ax[1].set_xlim(0,max(values)*1.14)
        fig.suptitle(title+' | tuning CV, not final-test scores',fontsize=14)
        fig.savefig(out/scenario/'cv-comparison.png',dpi=160);plt.close(fig)
        winner=next(x for x in items if x['id']==r['representative_candidate_id'])
        summary.append({'scenario':scenario,'representative':winner['id'],'cv':winner['cv'],
             'candidates':len(items),'elapsed_s':r['execution']['wall_s_including_load_export'],
             'peak_rss_mib':r['execution']['peak_rss_bytes']/2**20})
    (out/'run-summary.json').write_text(json.dumps({'scope':'development tuning CV only','scenarios':summary},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'rendered':4,'scope':'development tuning CV, not final-test evaluation'}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();render(a.root.resolve())
