import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
import crypto from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const {predict,unscaledCoefficients}=await import(pathToFileURL(path.join(root,'web/prediction.mjs')));
const fixtures=JSON.parse(fs.readFileSync(path.join(root,'artifacts/validation/stage6-prediction-fixtures.json'),'utf8'));
let checks=0,maxAbsoluteError=0;
for(const f of fixtures){
  const actual=predict(f.artifact,f.inference,f.input,f.forms);
  for(const [key,expected] of Object.entries(f.expected)){
    const difference=Math.abs(actual[key]-expected);assert.ok(difference<=1e-7+1e-8*Math.abs(expected),f.method+'/'+key);maxAbsoluteError=Math.max(maxAbsoluteError,difference);checks++;
  }
  if(!f.case){const raw=unscaledCoefficients(f.artifact);let value=raw.intercept;
  f.artifact.selected_columns.forEach((c,i)=>{value+=raw.coefficients[i]*(c.category===null?f.input[c.field]:String(f.input[c.field])===c.category?1:0);});
  if(f.artifact.target_transform==='log'&&f.artifact.method!=='dummy')value=Math.exp(value);
  assert.ok(Math.abs(value-f.expected.prediction)<=1e-7+1e-8*Math.abs(value));checks++;}
}
const result={status:'passed',models:new Set(fixtures.map(f=>f.artifact.dataset_id+'/'+f.method)).size,fixture_cases:fixtures.length,checks,max_absolute_error:maxAbsoluteError,tolerance:'1e-7 absolute + 1e-8 relative',
  method:'Actual browser-shared JavaScript module against Python reference for newly computed custom models; independent unscaled equation replay.',
  source_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'web/prediction.mjs'))).digest('hex')};
fs.writeFileSync(path.join(root,'artifacts/validation/stage6-prediction.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result));
