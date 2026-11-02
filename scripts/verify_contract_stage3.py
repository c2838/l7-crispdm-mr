"""Validate the saved result protocol with the already installed Pydantic."""
from pathlib import Path
import argparse,json
from typing import Any,Literal
from pydantic import BaseModel,ConfigDict,Field,ValidationError

class StrictRecord(BaseModel):
    model_config=ConfigDict(extra='allow',strict=True,allow_inf_nan=False)
class CVMetrics(StrictRecord):
    mae:float=Field(ge=0);mse:float=Field(ge=0);rmse:float=Field(ge=0)
    r2:float|None;fold_rmse_std:float=Field(ge=0)
class Candidate(StrictRecord):
    id:str;method:str;parameters:dict[str,Any]
    status:Literal['completed','incomplete_or_failed']
    folds:list[dict[str,Any]]
    cv:CVMetrics|None=None
class Result(StrictRecord):
    schema_version:Literal['1.0'];dataset_id:str
    status:Literal['completed','partial_timeout','cancelled','running']
    rows:int=Field(gt=0);raw_input_fields:int=Field(gt=0)
    cv_results:list[Candidate]
    representative_candidate_id:str|None
    representative_model_available:bool
    completed_methods:list[str];unavailable_methods:list[str]
    method_winner_ids:dict[str,str]
    models:dict[str,Any]|None=None
    model_files:dict[str,str]|None=None

def main(root):
    paths=list((root/'artifacts/analysis/models').glob('*/result.json'));assert len(paths)==4
    for p in paths:Result.model_validate(json.loads(p.read_text()))
    sample=json.loads(paths[0].read_text());sample['cv_results'][0]['cv']['rmse']='invalid'
    try:Result.model_validate(sample)
    except ValidationError:pass
    else:raise AssertionError('Invalid metric type was accepted.')
    sample['cv_results'][0]['cv']['rmse']=float('nan')
    try:Result.model_validate(sample)
    except ValidationError:pass
    else:raise AssertionError('NaN metric was accepted.')
    (root/'docs/RESULT_SCHEMA.json').write_text(json.dumps(Result.model_json_schema(),ensure_ascii=False,indent=2)+'\n')
    report={'saved_results_validated':4,'negative_fixtures_rejected':['string RMSE','NaN RMSE'],
            'scope':'core result protocol; field dependencies and model dimensions checked by verify_stage3.py'}
    (root/'artifacts/validation/stage3-contract.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);a=p.parse_args();main(a.root.resolve())
