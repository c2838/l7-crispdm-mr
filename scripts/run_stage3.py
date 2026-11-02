"""Run approved formal development CV; final test data records are skipped."""
from pathlib import Path
import argparse
import dataclasses
import hashlib
import importlib.metadata as md
import json
import os
import platform
import resource
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
import numpy as np
import pandas as pd
from l7_analysis import run_analysis,__version__
from l7_analysis.data import load_development,SCENARIOS

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def run(root,scenario,budget=None,methods=None):
    started=time.perf_counter();cpu=time.process_time()
    frame,ids,cfg,source=load_development(root,scenario)
    if budget is not None:cfg=dataclasses.replace(cfg,budget_seconds=budget)
    if methods:cfg=dataclasses.replace(cfg,methods=tuple(methods.split(',')))
    out=root/'artifacts/analysis/models'/scenario
    if (out/'result.json').exists():raise RuntimeError('Existing result must be explicitly archived before rerun.')
    out.mkdir(parents=True,exist_ok=True)
    with (out/'events.jsonl').open('w') as log:
        def progress(event):
            log.write(json.dumps(event,ensure_ascii=False)+'\n');log.flush()
            if event['event'] in ['fold_completed','refit_completed','finished']:
                print(json.dumps({'scenario':scenario,**event}),flush=True)
        result=run_analysis(frame,cfg,progress=progress)
    model_paths={}
    for identifier,artifact in result.pop('models').items():
        name=hashlib.sha256(identifier.encode()).hexdigest()[:16]+'.json'
        write_json(out/'models'/name,artifact);model_paths[identifier]='models/'+name
    result['model_files']=model_paths
    assignments=result.pop('cv_validation_fold_by_row')
    pd.DataFrame({'development_position':np.arange(len(ids)),'source_row_index_0_based':ids,
                  'validation_fold':assignments}).to_csv(out/'cv-fold-assignments.csv',index=False)
    summary=[]
    for entry in result['cv_results']:
        summary.append({'candidate_id':entry['id'],'method':entry['method'],'status':entry['status'],
                        'parameters':json.dumps(entry['parameters'],sort_keys=True),
                        'mean_selected_count':entry.get('mean_selected_count'),**entry.get('cv',{})})
    pd.DataFrame(summary).to_csv(out/'cv-comparison.csv',index=False)
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    result['execution']={'wall_s_including_load_export':time.perf_counter()-started,'cpu_s':time.process_time()-cpu,
       'peak_rss_bytes':int(peak if sys.platform=='darwin' else peak*1024),'threads':1,'python':platform.python_version(),
       'versions':{n:md.version(n) for n in ['numpy','pandas','scipy','scikit-learn']},'engine_version':__version__,
       'engine_code_sha256':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'l7_analysis').glob('*.py'))}}
    result['source']=source
    write_json(out/'result.json',result)
    print(json.dumps({'scenario':scenario,'status':result['status'],'candidates':len(summary),
                     'representative':result['representative_candidate_id'],'wall_s':result['execution']['wall_s_including_load_export']}),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT)
    p.add_argument('--scenario',choices=SCENARIOS,required=True);p.add_argument('--budget-seconds',type=float);p.add_argument('--methods')
    a=p.parse_args();result=run(a.root.resolve(),a.scenario,a.budget_seconds,a.methods)
    if result['status']!='completed':raise SystemExit(2)
