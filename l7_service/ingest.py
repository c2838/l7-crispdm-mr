import csv,hashlib,io,re
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from .contracts import MAX_CSV_BYTES,MIN_ROWS,MAX_ROWS,MAX_SOURCE_COLUMNS,MAX_RAW_FIELDS,MAX_CATEGORIES,MAX_ENCODED_FIELDS,Options,Problem,finite_json

def parse_csv(data):
    if not data:raise Problem('empty_csv','CSV是空的。')
    if len(data)>MAX_CSV_BYTES:raise Problem('csv_too_large','CSV不得超過3,500,000 bytes。',413)
    try:text=data.decode('utf-8-sig')
    except UnicodeDecodeError as e:raise Problem('encoding','請將資料另存為UTF-8 CSV後再上傳。') from e
    if '\x00' in text or text.lstrip().lower().startswith(('<!doctype','<html','<?xml','%pdf')):
        raise Problem('not_csv','內容不是可接受的文字CSV；請提供資料檔而非網頁、壓縮檔或模型。')
    try:delimiter=csv.Sniffer().sniff(text[:8192],delimiters=',;\t').delimiter
    except csv.Error:delimiter=','
    try:
        reader=csv.reader(io.StringIO(text,newline=''),delimiter=delimiter,strict=True)
        header=next(reader)
        if len(header)<2 or len(header)>MAX_SOURCE_COLUMNS:raise Problem('source_columns','CSV需有2～100個來源欄位；分析前仍須將X設定為最多39欄。')
        if any(not h.strip() or len(h)>128 or h.startswith('__l7_') for h in header):raise Problem('column_names','欄名需非空、最多128字元，且不可使用保留前綴__l7_。')
        if len(set(header))!=len(header):raise Problem('duplicate_headers','CSV有重複欄名，請先改為唯一名稱。')
        count=0
        for row in reader:
            if not row:continue
            if len(row)!=len(header):raise Problem('malformed_csv','CSV某列的欄位數與表頭不一致，請檢查分隔符號與引號。')
            count+=1
            if count>MAX_ROWS:raise Problem('too_many_rows','CSV最多10,000筆；沒有自動抽樣。')
    except (csv.Error,StopIteration) as e:raise Problem('malformed_csv','CSV格式或引號不完整。') from e
    if count<MIN_ROWS:raise Problem('too_few_rows','CSV至少需要50筆資料。')
    try:frame=pd.read_csv(io.StringIO(text),sep=delimiter,keep_default_na=False,na_values=[''])
    except (pd.errors.ParserError,ValueError) as e:raise Problem('malformed_csv','CSV無法解析，請檢查欄位與引號。') from e
    if len(frame)!=count:raise Problem('malformed_csv','CSV列數解析不一致；未刪除任何資料列。')
    return frame,{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'delimiter':delimiter,'encoding':'UTF-8','rows':len(frame),'source_columns':len(frame.columns)}

def describe(frame,source):
    def display(value):return value[:160]+'…' if isinstance(value,str) and len(value)>160 else finite_json(value)
    columns=[]
    for name in frame:
        s=frame[name];numeric=pd.api.types.is_numeric_dtype(s) and not pd.api.types.is_bool_dtype(s)
        examples=[display(x) for x in s.dropna().head(3).tolist()]
        columns.append({'name':name,'kind':'numeric' if numeric else 'categorical','missing':int(s.isna().sum()),
                        'unique':int(s.nunique(dropna=True)),'examples':examples,
                        'possible_id':bool(re.search(r'(^id$|_id$|^index$|^subject[#_]?|^name$)',name,re.I)),
                        'infinite':int(np.isinf(s.to_numpy(dtype=float)).sum()) if numeric else 0})
    return {'source':source,'columns':columns,'preview':[{k:display(v) for k,v in row.items()} for row in frame.head(5).where(frame.notna(),None).to_dict(orient='records')],
            'exact_duplicate_rows':int(frame.duplicated().sum()),'missing_cells':int(frame.isna().sum().sum()),
            'limits':{'bytes':MAX_CSV_BYTES,'rows':[MIN_ROWS,MAX_ROWS],'raw_inputs':MAX_RAW_FIELDS,'encoded_inputs':MAX_ENCODED_FIELDS,'categories_per_field':MAX_CATEGORIES},
            'note':'Schema preview only; no preprocessing or model fitted. Only empty fields are treated as missing.'}

def prepare(frame,source,options:Options):
    names=set(frame.columns)
    if options.target not in names:raise Problem('target_missing','找不到指定的Target。')
    if len(set(options.exclude))!=len(options.exclude) or len(set(options.categorical))!=len(options.categorical):raise Problem('duplicate_options','設定清單包含重複欄位。')
    if not set(options.exclude)<=names or not set(options.categorical)<=names:raise Problem('unknown_field','設定引用不存在的欄位。')
    if options.target in options.exclude:raise Problem('target_excluded','Target不能同時列為排除欄位。')
    if options.group:
        if options.group not in names or options.group==options.target:raise Problem('invalid_group','群組欄位需存在且不能等於Target。')
        if frame[options.group].isna().any():raise Problem('missing_group','群組欄位不能有缺值。')
    fields=[n for n in frame if n not in {options.target,options.group,*options.exclude}]
    if not 1<=len(fields)<=MAX_RAW_FIELDS:raise Problem('feature_count','請設定1～39個原始輸入；14以下會標示為教學示範。')
    if not set(options.categorical)<=set(fields):raise Problem('categorical_excluded','類別覆寫只能包含目前有效的X欄位。')
    try:y=pd.to_numeric(frame[options.target],errors='raise').to_numpy(dtype=float)
    except (ValueError,TypeError) as e:raise Problem('target_not_numeric','Target必須是數值，不能使用類別標籤。') from e
    if not np.isfinite(y).all():raise Problem('invalid_target','Target有缺值或無限值；Target不會被填補或刪列。')
    if np.ptp(y)==0:raise Problem('constant_target','Target為常數，無法進行有意義的回歸評估。')
    if options.target_transform=='log' and (y<=0).any():raise Problem('log_target','log Target要求每筆值都大於0。')
    work=frame[fields].copy();encoded_estimate=0;warnings=[]
    for name in fields:
        s=work[name];cat=name in options.categorical or not pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s)
        if cat:
            if any(len(str(value))>256 for value in s.dropna().unique()):raise Problem('category_label_length',f'欄位「{name}」含超過256字元的類別標籤，請排除長文字欄位或選用合適輸入。')
            count=int(s.nunique(dropna=True))
            if count>MAX_CATEGORIES:raise Problem('category_budget',f'欄位「{name}」超過20類，請排除ID／高基數欄位或重新選擇X。')
            encoded_estimate+=max(0,count-1)
        else:
            if np.isinf(s.to_numpy(dtype=float)).any():raise Problem('infinite_input',f'輸入「{name}」含無限值，請先修正。')
            encoded_estimate+=int(s.nunique(dropna=True)>1)
    if encoded_estimate>MAX_ENCODED_FIELDS:raise Problem('encoded_budget','預估編碼欄位超過64，請調整排除欄位或類別設定；未截斷欄位。')
    if not encoded_estimate:raise Problem('constant_inputs','所有有效輸入均為常數／全缺值，請選擇至少一個有變異的輸入。')
    if len(fields)<14:warnings.append('少於14個原始輸入：可用於教學／任意Dataset示範，不符合正式題目最低特徵數。')
    # Union identical X and explicit groups so neither can cross holdout/CV boundaries.
    parent=np.arange(len(frame))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=int(parent[i])
        return i
    def union(i,j):
        a,b=find(i),find(j)
        if a!=b:parent[b]=a
    hashes=pd.util.hash_pandas_object(work,index=False).to_numpy();seen={}
    for i,v in enumerate(hashes):
        if int(v) in seen:union(i,seen[int(v)])
        else:seen[int(v)]=i
    duplicate_x=len(frame)-len(seen)
    if options.group:
        seen_groups={}
        for i,v in enumerate(pd.factorize(frame[options.group],sort=True)[0]):
            if int(v) in seen_groups:union(i,seen_groups[int(v)])
            else:seen_groups[int(v)]=i
    grouped=bool(options.group or duplicate_x)
    effective_groups=np.array([find(i) for i in range(len(frame))])
    if grouped:
        if len(np.unique(effective_groups))<7:raise Problem('insufficient_groups','合併重複X與指定群組後，至少需7個獨立群組，才能保留test並做五折CV。')
        development,test=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=0).split(work,groups=effective_groups))
        work['__l7_effective_group__']=effective_groups
        if len(np.unique(effective_groups[development]))<5:raise Problem('insufficient_cv_groups','固定切分後development不足5個群組；未為改善成績重新切分。')
        warnings.append('重複X／指定群組已合併隔離；OLS傳統區間仍未修正群內相關，HC3不等於cluster-robust PI。')
    else:
        order=np.random.default_rng(0).permutation(len(frame));n_test=int(np.ceil(len(frame)*.2))
        test=np.sort(order[:n_test]);development=np.sort(order[n_test:])
    if len(development)<10 or len(test)<2:raise Problem('split_size','固定切分後訓練或測試資料不足。')
    if np.ptp(y[development])==0:raise Problem('constant_training_target','固定development Target為常數；未重新切分追求較好結果。')
    work[options.target]=y
    split={'development_rows':len(development),'test_rows':len(test),'grouped':grouped,'group_column':options.group,
           'duplicate_input_rows':duplicate_x,'effective_groups':int(len(np.unique(effective_groups))) if grouped else None,
           'training_test_groups_disjoint':not bool(set(effective_groups[development])&set(effective_groups[test])) if grouped else None,
           'development_source_rows_sha256':hashlib.sha256(np.asarray(development,dtype='<i8').tobytes()).hexdigest(),
           'test_source_rows_sha256':hashlib.sha256(np.asarray(test,dtype='<i8').tobytes()).hexdigest(),
           'seed':0,'policy':'GroupShuffleSplit on union of groups/identical-X' if grouped else 'PCG64(0), first ceil(20%) reserved',
           'final_test_used_for_selection':False}
    return work.iloc[development].copy(),work.iloc[test].copy(),development,test,fields,split,warnings
