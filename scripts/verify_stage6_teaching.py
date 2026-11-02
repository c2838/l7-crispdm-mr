"""Actual assignment-provided categorical example, plus changed Target/X settings."""
from pathlib import Path
import argparse,json,sys,io,hashlib
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import httpx,pandas as pd
from l7_analysis.models import predict_artifact
from l7_analysis.inference import predict_with_intervals
URL='https://raw.githubusercontent.com/Avik-Jain/100-Days-Of-ML-Code/master/datasets/50_Startups.csv'
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main(root,origin):
    checks=[]
    def check(name,value):checks.append({'name':name,'passed':bool(value)});assert value,name
    options={'target':'Profit','exclude':[],'categorical':[],'group':None,'target_transform':'identity','seed':0}
    with httpx.Client(base_url=origin,timeout=240,trust_env=False) as client:
        remote=client.post('/api/data/url',json={'url':URL});check('actual assignment example URL',remote.status_code==200);data=remote.content;source_sha=hashlib.sha256(data).hexdigest()
        preview=client.post('/api/data/preview',files={'file':('teaching.csv',data,'text/csv')});check('50-row categorical preview',preview.status_code==200 and preview.json()['source']['rows']==50)
        results=[]
        def post(method,config):return client.post('/api/analyze/'+method,files={'file':('teaching.csv',data,'text/csv')},data={'options':json.dumps(config),'sha256':source_sha})
        for method in ['baseline','kbest','rfe','sfs','lasso_select','elasticnet_select']:
            response=post(method,options);check(method+' actual complete categorical request',response.status_code==200 and response.json()['status']=='completed');result=response.json();results.append(result)
            save(root/'artifacts/validation/stage6-teaching'/(method+'.json'),result)
        base=results[0];ols=next(m for m in base['models'] if m['method']=='ols')
        check('four raw inputs and five encoded columns',base['raw_input_fields']==4 and len(ols['artifact']['preprocessor']['columns'])==5)
        check('teaching scope below 14 disclosed',any('少於14' in w for w in base['warnings']))
        changed_target=post('kbest',{**options,'target':'Administration','exclude':['Profit']});check('changed Target executes',changed_target.status_code==200 and changed_target.json()['status']=='completed')
        changed_x=post('kbest',{**options,'exclude':['Marketing Spend']});check('changed excluded field executes',changed_x.status_code==200 and changed_x.json()['status']=='completed')
        a,b=changed_target.json(),changed_x.json()
        check('same CSV new settings have different analysis binding',len({base['analysis_id'],a['analysis_id'],b['analysis_id']})==3 and a['data_sha256']==b['data_sha256']==base['data_sha256'])
        check('actual new target and exclusion used',a['models'][0]['artifact']['target']=='Administration' and 'Profit' not in a['models'][0]['artifact']['raw_input_fields'] and 'Marketing Spend' not in b['models'][0]['artifact']['raw_input_fields'])
        save(root/'artifacts/validation/stage6-teaching/changed-target.json',a);save(root/'artifacts/validation/stage6-teaching/changed-x.json',b)
    fp=root/'artifacts/validation/stage6-prediction-fixtures.json';fixtures=json.loads(fp.read_text());fixtures=[f for f in fixtures if f['artifact']['target']=='total_UPDRS']
    for m in [m for r in results for m in r['models']]:
        samples=[(None,m['defaults'])]
        if m['method']=='ols':
            samples.extend([('unknown_category',{**m['defaults'],'State':'NEW_REGION'}),('missing_numeric',{**m['defaults'],'R&D Spend':None}),('new_numeric',{**m['defaults'],'R&D Spend':150000.})])
        for case,values in samples:
            frame=pd.DataFrame([values]);prediction,_=predict_artifact(m['artifact'],frame);expected={'prediction':float(prediction[0])}
            if m['inference']:
                interval,_=predict_with_intervals(m['artifact'],m['inference'],frame)
                expected.update({k:float(interval.iloc[0][k]) for k in ['location_ci_lower','location_ci_upper','observation_pi_lower','observation_pi_upper','location_ci_hc3_lower','location_ci_hc3_upper']})
            fixtures.append({'artifact':m['artifact'],'inference':m['inference'],'forms':m['forms'],'input':values,'expected':expected,'method':m['method'],'case':case})
    save(fp,fixtures)
    report={'status':'passed','checks':checks,'passed_checks':len(checks),'source_sha256':source_sha,'url':URL,'scope':'Actual localhost HTTP with real assignment-provided public example; categorical/minimum-row/change-setting validation. UCI remains the independent third dataset proof.','raw_csv_saved':False}
    save(root/'artifacts/validation/stage6-teaching.json',report);print(json.dumps({'status':'passed','checks':len(checks),'fixtures':len(fixtures)}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--origin',default='http://127.0.0.1:8768');a=p.parse_args();main(a.root.resolve(),a.origin)
