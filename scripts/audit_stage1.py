"""Audit the approved SGEMM/student datasets; never fit a predictive model.

Requires pandas/numpy. Run with --root PROJECT. Raw public files stay unchanged.
"""
from pathlib import Path
import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone

import numpy as np
import pandas as pd


GPU_FEATURES = ['MWG', 'NWG', 'KWG', 'MDIMC', 'NDIMC', 'MDIMA', 'NDIMB',
                'KWI', 'VWM', 'VWN', 'STRM', 'STRN', 'SA', 'SB']
RUNS = [f'Run{i} (ms)' for i in range(1, 5)]
GPU_ALLOWED = {'MWG': [16,32,64,128], 'NWG': [16,32,64,128], 'KWG': [16,32],
               'MDIMC': [8,16,32], 'NDIMC': [8,16,32], 'MDIMA': [8,16,32],
               'NDIMB': [8,16,32], 'KWI': [2,8], 'VWM': [1,2,4,8],
               'VWN': [1,2,4,8], 'STRM': [0,1], 'STRN': [0,1], 'SA': [0,1], 'SB': [0,1]}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def fixed_split(frame, features):
    # No target-based stratification, no fitted preprocessor, no score-based split.
    assert not frame[features].duplicated().any(), 'Repeated inputs require a group split.'
    count = int(np.ceil(len(frame) * .2))
    indices = np.random.Generator(np.random.PCG64(0)).permutation(len(frame))[:count]
    final = np.zeros(len(frame), dtype=bool)
    final[indices] = True
    return pd.DataFrame({'source_row_index_0_based': np.arange(len(frame)),
                         'split': np.where(final, 'final_test', 'development')}), ~final


def schema(frame, features, target):
    rows = []
    for pos, name in enumerate(frame, 1):
        col = frame[name]
        role = 'feature' if name in features else 'target' if name == target else 'excluded_repeat_measurement'
        item = {'column': name, 'position_1_based': pos, 'role': role,
                'storage_type': str(col.dtype), 'missing': int(col.isna().sum()),
                'unique_nonmissing': int(col.nunique())}
        if pd.api.types.is_numeric_dtype(col):
            item.update(min=float(col.min()), max=float(col.max()))
        else:
            item['categories'] = sorted(map(str, col.unique()))
        rows.append(item)
    return rows


def audit(root):
    out = root / 'artifacts/analysis/data-audit'
    out.mkdir(parents=True, exist_ok=True)
    (root / 'data/processed').mkdir(parents=True, exist_ok=True)
    ap = root / 'data/raw/sgemm/sgemm_product.csv'
    bp = root / 'data/raw/student/student-por.csv'
    a = pd.read_csv(ap)
    b = pd.read_csv(bp)
    assert a.shape == (241600,18) and list(a) == GPU_FEATURES + RUNS
    assert b.shape == (649,33) and list(b)[-3:] == ['G1','G2','G3']
    assert a.equals(pd.read_csv(root / 'artifacts/reference/datasets/sgemm-uci-original.csv'))
    assert b.equals(pd.read_csv(root / 'artifacts/reference/datasets/student-por-uci-original.csv', sep=';'))
    assert all(a[c].isin(values).all() for c, values in GPU_ALLOWED.items())
    assert (a[RUNS] > 0).all().all() and b[['G1','G2','G3']].apply(lambda s: s.between(0,20).all()).all()
    model_a = a[GPU_FEATURES].copy()
    model_a['runtime_mean_ms'] = a[RUNS].mean(axis=1)
    model_b = b.copy()
    b_features = [c for c in b if c != 'G3']
    model_a.to_csv(root / 'data/processed/sgemm-model-input.csv', index=False)
    model_b.to_csv(root / 'data/processed/student-model-input.csv', index=False)
    records = {}
    plot_data = {}
    for label, raw, model, features, target, path in [
        ('a',a,model_a,GPU_FEATURES,'runtime_mean_ms',ap),
        ('b',b,model_b,b_features,'G3',bp)]:
        numeric = raw.select_dtypes('number')
        assert not raw.isna().any().any() and np.isfinite(numeric.to_numpy()).all()
        assert not raw.duplicated().any()
        split, dev_mask = fixed_split(model, features)
        split.to_csv(out / f'dataset-{label}-split.csv', index=False)
        dev = model.loc[dev_mask]
        numeric_dev = dev.select_dtypes('number')
        numeric_dev.describe().T.to_csv(out / f'dataset-{label}-development-summary.csv')
        corr = numeric_dev.corr()
        corr.to_csv(out / f'dataset-{label}-development-correlations.csv')
        categories = list(dev.select_dtypes(exclude='number').columns)
        encoded_count = len(features) - len(categories) + sum(dev[c].nunique()-1 for c in categories)
        # Count only: actual fold-local encoders are constructed in later stages.
        rows = schema(raw, features, target)
        if label == 'a':
            rows.append({'column':target,'role':'derived_target','definition':'arithmetic mean of Run1..Run4 (ms)',
                         'missing':0,'min':float(model[target].min()),'max':float(model[target].max())})
        write_json(out / f'dataset-{label}-schema.json', rows)
        pd.DataFrame(rows).drop(columns='categories', errors='ignore').to_csv(out / f'dataset-{label}-columns.csv', index=False)
        record = {'id':'sgemm' if label=='a' else 'student-por','rows':len(raw),
                  'source_columns':len(raw.columns),'raw_feature_count':len(features),'features':features,
                  'target':target,'target_definition':'mean(Run1, Run2, Run3, Run4), milliseconds' if label=='a' else 'G3 final period grade, documented scale 0..20',
                  'missing_values':int(raw.isna().sum().sum()),'infinite_values':int(np.isinf(numeric.to_numpy()).sum()),
                  'exact_duplicate_rows':int(raw.duplicated().sum()),'duplicate_feature_vectors':int(model[features].duplicated().sum()),
                  'constant_columns':[c for c in raw if raw[c].nunique()<2],
                  'target_range':[float(model[target].min()),float(model[target].max())],
                  'development_rows':int(dev_mask.sum()),'final_test_rows':int((~dev_mask).sum()),
                  'split_generator':'numpy Generator(PCG64(0)); first ceil(0.2*n) permuted indices = final_test',
                  'split_scope':'random held-out records from this source population, not an external deployment test',
                  'eda_scope':'development rows only; source-quality checks use all rows',
                  'categorical_features':categories,'encoded_feature_count_estimate_drop_first_development':int(encoded_count),
                  'encoder_fitted':False,'raw_sha256':sha(path),'predictive_model_fitted':False}
        if label == 'a':
            record.update(excluded_source_outputs=RUNS, input_allowed_values=GPU_ALLOWED,
                          source_nature='Measured GPU benchmark on the source hardware; not newly simulated by agent',
                          limitation='Performance relationships can be nonlinear. Hardware/workload generalization is untested. No log transform or outlier removal applied.')
        else:
            record.update(source_nature='Published school reports and questionnaires from two Portuguese schools',
                          school_counts=b.school.value_counts().to_dict(),
                          limitation='Retrospective conditional estimation. G1/G2 are prior-period grades; absences/questionnaire timing does not establish a prospective early-warning scenario. No causal or individual intervention claims.',
                          auxiliary_comparison='Plan a 30-background-feature sensitivity analysis excluding G1/G2; not yet run.')
        records[label] = record
        write_json(out / f'dataset-{label}-audit.json', record)
        counts, edges = np.histogram(dev[target], bins=40 if label=='a' else np.arange(-.5,21.5))
        plot_data[label] = {'hist_counts':counts.tolist(),'hist_edges':edges.tolist(),
                            'corr_names':list(corr),'corr_matrix':corr.to_numpy().tolist(),
                            'target':target,'development_rows':len(dev)}
        if label=='a':
            counts,edges=np.histogram(np.log10(dev[target]),bins=40)
            plot_data[label].update(log_hist_counts=counts.tolist(),log_hist_edges=edges.tolist())
        else:
            plot_data[label]['school_counts_development']=dev.school.value_counts().to_dict()
    summary = {'recorded_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
               'revision':'sgemm-student-approved','analysis_runtime':{'python':platform.python_version(),'pandas':pd.__version__,'numpy':np.__version__},
               'method':'Actual Kaggle CSV values compared with UCI originals; schema, source-quality audit, fixed split and development-only EDA. No fitted predictive models.',
               **records}
    write_json(out / 'summary.json',summary)
    write_json(out / 'plot-data.json',plot_data)
    manifest_path=root/'artifacts/reference/datasets-manifest.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        manifest['analysis_runtime']=summary['analysis_runtime']
        manifest['processed_files']=[{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in
                                     [root/'data/processed/sgemm-model-input.csv',root/'data/processed/student-model-input.csv']]
        write_json(manifest_path,manifest)
    print(json.dumps({k:{f:v[f] for f in ['rows','raw_feature_count','target','development_rows','final_test_rows','encoded_feature_count_estimate_drop_first_development']} for k,v in records.items()}))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    audit(parser.parse_args().root.resolve())
