from pathlib import Path
import hashlib
import json
import pandas as pd
from .config import AnalysisConfig,InputError

SCENARIOS={
 'sgemm':{'letter':'a','file':'sgemm-model-input.csv','target':'runtime_mean_ms','transform':'identity','exclude':()},
 'sgemm_log':{'letter':'a','file':'sgemm-model-input.csv','target':'runtime_mean_ms','transform':'log','exclude':()},
 'student':{'letter':'b','file':'student-model-input.csv','target':'G3','transform':'identity','exclude':()},
 'student_background':{'letter':'b','file':'student-model-input.csv','target':'G3','transform':'identity','exclude':('G1','G2')},
}

def load_development(root,scenario):
    info=SCENARIOS[scenario];manifest=json.loads((root/'artifacts/reference/datasets-manifest.json').read_text())
    file=root/'data/processed'/info['file']
    record=next(x for x in manifest['processed_files'] if x['path']==str(file.relative_to(root)))
    if hashlib.sha256(file.read_bytes()).hexdigest()!=record['sha256']:raise InputError('Source hash mismatch.')
    split_path=root/f"artifacts/analysis/data-audit/dataset-{info['letter']}-split.csv"
    split=pd.read_csv(split_path)
    ids=split.loc[split.split=='development','source_row_index_0_based'].to_numpy()
    allowed=set(ids.tolist())
    frame=pd.read_csv(file,skiprows=lambda i:i>0 and i-1 not in allowed)
    assert len(frame)==len(ids) and not allowed&set(split.loc[split.split=='final_test','source_row_index_0_based'])
    metadata={'scenario':scenario,'input_path':str(file.relative_to(root)),'input_sha256':record['sha256'],
      'split_path':str(split_path.relative_to(root)),'split_sha256':hashlib.sha256(split_path.read_bytes()).hexdigest(),
      'development_source_rows_sha256':hashlib.sha256(ids.astype('<i8').tobytes()).hexdigest(),
      'development_rows':len(frame),'reserved_final_rows':int((split.split=='final_test').sum()),
      'final_test_rows_parsed_for_modeling':0,'source_nature':'actual published data; only fixed development records parsed for modeling'}
    cfg=AnalysisConfig(target=info['target'],dataset_id=scenario,target_transform=info['transform'],exclude=info['exclude'])
    return frame,ids,cfg,metadata
