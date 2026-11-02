"""Development-only descriptive plots; no model fitting or final-test scores."""
from pathlib import Path
import argparse
import json
import os
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/l7-stage1-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def histogram(ax, data, xlabel, log=False):
    prefix='log_hist' if log else 'hist'
    edges=np.asarray(data[prefix+'_edges']);counts=data[prefix+'_counts']
    ax.bar(edges[:-1],counts,width=np.diff(edges),align='edge',color='#315c99',edgecolor='white')
    ax.set(xlabel=xlabel,ylabel='Development rows')

def main(root):
    out=root/'artifacts/analysis/data-audit';d=json.loads((out/'plot-data.json').read_text())
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,
                         'figure.facecolor':'#f6f8fb','axes.facecolor':'white'})
    fig,ax=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
    histogram(ax[0],d['a'],'Mean of four runtime measurements (ms)')
    ax[0].set_title('Observed runtime distribution')
    histogram(ax[1],d['a'],'log10(mean runtime in ms)',log=True)
    ax[1].set_title('Log scale for display only; no model transform')
    fig.suptitle('Dataset A - SGEMM GPU runtime | development rows only',fontsize=14)
    fig.savefig(out/'dataset-a-overview.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,8),layout='constrained')
    names=d['a']['corr_names'];im=ax.imshow(d['a']['corr_matrix'],vmin=-1,vmax=1,cmap='RdBu_r')
    ax.set(xticks=range(len(names)),yticks=range(len(names)),xticklabels=names,yticklabels=names,
           title='Dataset A - Numeric Pearson correlations | development rows only')
    plt.setp(ax.get_xticklabels(),rotation=55,ha='right',fontsize=8);ax.tick_params(axis='y',labelsize=8)
    fig.colorbar(im,ax=ax,label='Pearson r')
    fig.savefig(out/'dataset-a-correlations.png',dpi=170);plt.close(fig)
    fig,ax=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
    histogram(ax[0],d['b'],'Final grade G3 (documented scale: 0-20)')
    ax[0].set(xticks=range(0,21,2),title='Observed final-grade distribution')
    names=list(d['b']['school_counts_development']);values=list(d['b']['school_counts_development'].values())
    ax[1].bar(names,values,color='#198c83');ax[1].set(xlabel='Source school',ylabel='Development rows',title='School composition')
    fig.suptitle('Dataset B - Portuguese course performance | development rows only',fontsize=14)
    fig.savefig(out/'dataset-b-overview.png',dpi=170);plt.close(fig)
    print(json.dumps({'rendered':3,'matplotlib':matplotlib.__version__,'scope':'development EDA only'}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    main(parser.parse_args().root.resolve())
