"""Render local timing evidence with the new project's own matplotlib."""
from pathlib import Path
import argparse,json,os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/l7-stage2-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);root=p.parse_args().root.resolve()
out=root/'artifacts/feasibility'
real=json.loads((out/'benchmarks/summary.json').read_text())['cases']
stress=json.loads((out/'stress/summary.json').read_text())['cases']
methods=['ols','kbest','rfe','sfs','lasso','elasticnet']
labels=['OLS + intervals','SelectKBest','RFE','Forward SFS','Lasso selection','ElasticNet selection']
fig,ax=plt.subplots(1,2,figsize=(14,5),layout='constrained')
for i,(dataset,color,label) in enumerate([('sgemm','#315c99','GPU: 193,280 development rows'),('student','#198c83','Student: 519 development rows'),('stress','#b47734','Generated resource fixture: 10,000 rows')]):
    rows=stress if dataset=='stress' else [x for x in real if x['dataset']==dataset]
    lookup={x['method']:x for x in rows}
    seconds=[lookup[m]['operation_s'] for m in methods]
    ax[0].barh(np.arange(6)+(.24*(i-1)),seconds,height=.22,color=color,label=label)
    ax[1].bar(i,max(x['peak_rss_bytes'] for x in rows)/2**20,color=color)
ax[0].set_xscale('log')
ax[0].set_xlim(.0005,10)
ax[0].set(yticks=range(6),yticklabels=labels,xlabel='Operation time (seconds, log scale; imports/loading excluded)',title='Representative method operations')
ax[0].legend(loc='lower right',fontsize=8)
ax[1].set(xticks=range(3),xticklabels=['GPU','Student','Generated fixture'],ylabel='Peak process RSS (MiB)',title='Whole process memory, including package imports')
fig.suptitle('Stage 2 - Local single-threaded feasibility | not Vercel performance',fontsize=14)
fig.savefig(out/'local-performance.png',dpi=160);plt.close(fig)
print(json.dumps({'rendered':'artifacts/feasibility/local-performance.png','matplotlib':matplotlib.__version__}))
