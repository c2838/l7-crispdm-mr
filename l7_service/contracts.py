import hashlib,json,math
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field

MAX_CSV_BYTES=3_500_000
MAX_REQUEST_BYTES=3_570_000
MAX_JSON_BYTES=3_000_000
MAX_ROWS=10_000
MIN_ROWS=50
MAX_SOURCE_COLUMNS=100
MAX_RAW_FIELDS=39
MAX_ENCODED_FIELDS=64
MAX_CATEGORIES=20
METHOD_SECONDS=120.
URL_SECONDS=15.
SELECTION_METHODS=('kbest','rfe','sfs','lasso_select','elasticnet_select')
REQUEST_METHODS=('baseline',*SELECTION_METHODS)

class Problem(ValueError):
    def __init__(self,code,message,status=422):
        super().__init__(message);self.code=code;self.message=message;self.status=status

class Options(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    target:str=Field(min_length=1,max_length=128)
    exclude:list[str]=Field(default_factory=list,max_length=100)
    categorical:list[str]=Field(default_factory=list,max_length=39)
    group:str|None=None
    target_transform:Literal['identity','log']='identity'
    seed:Literal[0]=0

def fingerprint(options,data_sha256):
    value={'data_sha256':data_sha256,'options':options.model_dump(),'pipeline':'custom-v1:holdout-20:cv5-inner3-seed17'}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()

def finite_json(value):
    """Non-finite diagnostic scalars are unavailable, never nonstandard JSON NaN."""
    import numpy as np
    if isinstance(value,dict):return {str(k):finite_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [finite_json(v) for v in value]
    if isinstance(value,np.ndarray):return finite_json(value.tolist())
    if isinstance(value,(np.integer,)):return int(value)
    if isinstance(value,(float,np.floating)):return float(value) if math.isfinite(value) else None
    if isinstance(value,np.bool_):return bool(value)
    return value

def json_bytes(value):return json.dumps(finite_json(value),ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
