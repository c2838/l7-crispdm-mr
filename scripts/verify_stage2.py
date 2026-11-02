"""Verify actual Stage 2 evidence without refitting or reading final test for scores."""
from pathlib import Path
import argparse
import hashlib
import importlib.metadata as md
import json
import math
import subprocess
import sys
from datetime import datetime,timezone

def main(root):
    out=root/'artifacts/feasibility';checks=[]
    def read(rel):return json.loads((root/rel).read_text())
    def check(name,actual,expected=True,method='actual saved evidence and file inspection'):
        passed=actual==expected;checks.append({'name':name,'method':method,'expected':expected,'actual':actual,'passed':passed})
        assert passed,(name,actual,expected)
    def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    check('project-owned independent virtual environment',Path(sys.prefix).resolve(),(root/'.venv').resolve())
    # Convert Path objects for the report.
    checks[-1]['actual']=str(checks[-1]['actual']);checks[-1]['expected']=str(checks[-1]['expected'])
    check('Python 3.12',sys.version_info[:2],(3,12))
    checks[-1]['actual']=list(checks[-1]['actual']);checks[-1]['expected']=list(checks[-1]['expected'])
    pip=subprocess.run([sys.executable,'-m','pip','--isolated','check','--disable-pip-version-check'],text=True,capture_output=True)
    check('installed dependency consistency',pip.returncode,0,'pip check in new L7 .venv')
    locks=[]
    for line in (root/'requirements.txt').read_text().splitlines():
        name,version=line.split('==');locks.append(md.version(name)==version)
    check('runtime exact lock matches installed environment',all(locks))
    real=read('artifacts/feasibility/benchmarks/summary.json')['cases']
    stress=read('artifacts/feasibility/stress/summary.json')['cases']
    check('real development benchmark count',len(real),18)
    check('resource-fixture benchmark count',len(stress),6)
    check('all executed cases passed',all(x['status']=='passed' for x in real+stress))
    check('all model cases use one BLAS/compute thread',all(x['threads_limit']==1 and all(p['num_threads']==1 for p in x['threadpools']) for x in real+stress))
    check('no final test data records read by benchmark',all(x['final_test_rows_read']==0 for x in real+stress),method='inspect skiprows loader plus recorded per-case scope; full source hash verification is separate')
    check('real development sample sizes',sorted(set((x['dataset'],x['development_rows']) for x in real)),[('sgemm',193280),('student',519)])
    check('exact resource fixture boundary',all((x['development_rows'],x['raw_input_fields'],x['encoded_columns'])==(10000,39,64) for x in stress))
    check('resource fixture clearly separated from formal data',all('not formal data' in x['source_nature'] for x in stress))
    check('all five methods actually present for both formal datasets',all({x['method'] for x in real if x['dataset']==ds}>={'kbest','rfe','sfs','lasso','elasticnet'} for ds in ['sgemm','student']))
    check('SFS candidate/fold fit counts',all(x['cv_regression_fits']==sum(x['candidate_encoded_columns']-i for i in range(x['selected_encoded_columns']))*3 for x in real+stress if x['method']=='sfs'))
    check('representative methods below engineering deadline',all(x['wall_s_including_import']<120 for x in real+stress))
    check('representative whole process RSS below 1 GiB margin',all(x['peak_rss_bytes']<2**30 for x in real+stress))
    check('no convergence warnings',all('ConvergenceWarning' not in x['warning_categories'] for x in real+stress))
    ols=[x for x in real+stress if x['method'] in ['ols','log_ols','no_prior_ols']]
    check('OLS package prediction agreement',all(x['sklearn_statsmodels_prediction_max_error']<1e-6 for x in ols))
    check('OLS design matrices full rank',all(x['design_rank']==x['design_columns'] for x in ols))
    check('illustrative interval JSON below response budget',all(x['illustrative_interval_json_bytes']<3000000 for x in ols))
    http=read('artifacts/feasibility/http-probes.json')
    check('actual localhost HTTP checks',http['passed_checks'],11)
    check('all HTTP expectations met',all(x['passed'] for x in http['checks']))
    check('HTTP prototype not misrepresented as model analysis',http['no_model_analysis'])
    url=read('artifacts/feasibility/public-url-probe.json')
    check('public HTTPS CSV reachable and parseable',(url['status'],url['rows'],url['columns'],url['target_present']),(200,649,33,True))
    linux=read('artifacts/feasibility/linux-wheel-sizes.json')
    check('Linux runtime wheel coverage',len(linux['wheels']),len(locks))
    check('Linux required dependency metadata satisfied',linux['linux_dependency_metadata_closed'])
    check('wheel content estimate below standard bundle ceiling',linux['uncompressed_bytes']<500000000,method='sum of actual wheel ZipInfo.file_size; excludes application/bytecode/build overhead, not deployed size')
    check('matplotlib actual PNG output',(out/'local-performance.png').read_bytes()[:8]==b'\x89PNG\r\n\x1a\n')
    manifest=read('artifacts/reference/datasets-manifest.json')
    check('source data bytes unchanged',all(sha(root/r['path'])==r['sha256'] for ds in manifest['datasets'] for r in ds['raw_files']))
    check('model input data bytes unchanged',all(sha(root/r['path'])==r['sha256'] for r in manifest['processed_files']))
    import numpy as np
    import pandas as pd
    for letter,n in [('a',241600),('b',649)]:
        split=pd.read_csv(root/f'artifacts/analysis/data-audit/dataset-{letter}-split.csv')
        expected=set(np.random.Generator(np.random.PCG64(0)).permutation(n)[:math.ceil(n*.2)].tolist())
        actual=set(split.loc[split.split=='final_test','source_row_index_0_based'].tolist())
        check(letter+' original fixed split preserved',actual==expected,method='recompute original numpy PCG64(0) held-out row indices; no scoring')
    check('Stage 3 remains pending approval','待使用者確認，尚未實作' in (root/'docs/STAGE3_PROPOSAL.md').read_text())
    check('no production app entrypoint created',not (root/'app.py').exists())
    check('no repository initialized by this stage',not (root/'.git').exists())
    check('current stage2 checklist complete','- [ ]' not in (root/'docs/STAGE2_PROPOSAL.md').read_text())
    evidence=[p for p in out.rglob('*') if p.is_file()]
    result={'recorded_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
      'status':'passed_local_feasibility_cloud_unverified','scope':'new L7 environment, actual development data, labeled generated fixture, real localhost HTTP and public URL parser',
      'passed_checks':len(checks),'checks':checks,
      'visual_review':'Agent inspected actual matplotlib timing/RSS chart; legends, units and local-only labels legible.',
      'evidence_sha256':{str(p.relative_to(root)):sha(p) for p in evidence},
      'limitations':['No final test model scoring, final feature/model selection or exported formal model.',
        'Representative k/alpha/CV timings are not the cost of the full planned analysis grid.',
        'Linux wheel availability/metadata/size checked; Linux binaries and Vercel build/runtime not executed.',
        'Actual Vercel account/project settings and remaining monthly usage not inspected; user selected Hobby design basis.',
        'No product API, online third-dataset analysis, deployment or submission.',
        'Cancellation, deadlines and public URL policy are architecture requirements to implement in subsequent stages.']}
    dest=root/'artifacts/validation/stage2.json';dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'passed_checks':len(checks),'evidence_files':len(evidence)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args();main(args.root.resolve())
