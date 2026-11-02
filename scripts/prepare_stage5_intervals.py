"""Enrich candidate development display intervals without fitting or reading test rows."""
from pathlib import Path
import argparse,hashlib,json,sys,os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import numpy as np
from l7_analysis.data import SCENARIOS,load_development
from l7_analysis.inference import predict_with_intervals
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
def main(root):
    mp=root/'artifacts/analysis/website/export-manifest.json';manifest=read(mp)
    assert all(sha(root/p)==h for p,h in manifest['protected_sha256'].items())
    count=0
    for scenario in SCENARIOS:
        frame,ids,config,source=load_development(root,scenario)
        sample=np.linspace(0,len(frame)-1,min(300,len(frame)),dtype=int)
        case=read(root/'web/data'/(scenario+'.json'));cache={}
        for card in case['candidates']:
            path=root/'web'/card['detail'];detail=read(path);spec=detail['inference']
            if not spec:continue
            key=spec['model_equation_sha256']
            if key not in cache:
                prediction,_=predict_with_intervals(detail['artifact'],spec,frame.iloc[sample])
                columns=['location_ci_lower','location_ci_upper','observation_pi_lower','observation_pi_upper','location_ci_hc3_lower','location_ci_hc3_upper']
                cache[key]={k:prediction[k].tolist() for k in columns}
            detail['development_plot']['rows'].update(cache[key]);save(path,detail);count+=1
    assert all(sha(root/p)==h for p,h in manifest['protected_sha256'].items())
    manifest['initial_export_sha256']=manifest['export_sha256']
    manifest['export_sha256']={p:sha(root/p) for p in manifest['export_sha256']}
    manifest['source_sha256'][str(Path(__file__).resolve().relative_to(root))]=sha(Path(__file__).resolve())
    manifest['development_interval_displays']=count
    save(mp,manifest);print(json.dumps({'development_interval_displays':count,'new_fits':0,'test_rows_parsed':0}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);a=p.parse_args();main(a.root.resolve())
