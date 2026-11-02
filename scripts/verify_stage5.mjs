import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath,pathToFileURL} from 'node:url';
import crypto from 'node:crypto';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const read=p=>JSON.parse(fs.readFileSync(path.join(root,p),'utf8'));
const {predict,unscaledCoefficients}=await import(pathToFileURL(path.join(root,'web/prediction.mjs')));
const fixtures=read('artifacts/validation/stage5-prediction-fixtures.json');
let comparisons=0,maxAbsoluteError=0,unscaledComparisons=0;
const cache=new Map(),scenarios=new Map();
const close=(a,b,name)=>{assert.ok(Number.isFinite(a)&&Math.abs(a-b)<=1e-7+1e-8*Math.abs(b),`${name}: ${a} vs ${b}`);maxAbsoluteError=Math.max(maxAbsoluteError,Math.abs(a-b));comparisons++;};
for(const f of fixtures){
  if(!cache.has(f.detail))cache.set(f.detail,read('web/'+f.detail));
  if(!scenarios.has(f.scenario))scenarios.set(f.scenario,read('web/data/'+f.scenario+'.json'));
  const d=cache.get(f.detail),c=scenarios.get(f.scenario),actual=predict(d.artifact,d.inference,f.input,c.forms);
  for(const [key,value] of Object.entries(f.expected))close(actual[key],value,f.scenario+'/'+f.candidate_id+'/'+key);
  if(!f.case){
    const a=d.artifact,raw=unscaledCoefficients(a);
    const encoded=a.selected_columns.map(col=>col.category===null?f.input[col.field]:String(f.input[col.field])===col.category?1:0);
    let result=raw.intercept+encoded.reduce((sum,x,i)=>sum+x*raw.coefficients[i],0);
    if(a.target_transform==='log'&&a.method!=='dummy')result=Math.exp(result);
    close(result,f.expected.prediction,'independent unscaled equation');unscaledComparisons++;
  }
  if(f.case==='unknown_category')assert.ok(actual.warnings.some(w=>w.includes('未知類別')));
  if(f.case==='missing_value')assert.ok(actual.warnings.some(w=>w.includes('缺值')));
  if(f.case==='outside_range'){
    const changed=Object.keys(f.input).find(k=>f.input[k]!==c.defaults[k]);
    if(d.artifact.selected_raw_fields.includes(changed))assert.ok(actual.warnings.some(w=>w.includes('外推')));
  }
}
assert.equal(cache.size,488);assert.equal(unscaledComparisons,488);
let invalidInputChecks=0;
let activeExtrapolationChecks=0;
for(const scenario of ['sgemm','sgemm_log','student','student_background']){
  const c=scenarios.get(scenario),d=cache.get(c.candidates.find(x=>x.id===c.representative_id).detail);
  const numeric=c.forms.find(f=>f.kind==='numeric').field;
  for(const invalid of ['not-a-number',Infinity,-Infinity]){assert.throws(()=>predict(d.artifact,d.inference,{...c.defaults,[numeric]:invalid},c.forms));invalidInputChecks++;}
  const missing={...c.defaults};delete missing[numeric];assert.throws(()=>predict(d.artifact,d.inference,missing,c.forms));invalidInputChecks++;
  const active=c.forms.find(f=>f.kind==='numeric'&&d.artifact.selected_raw_fields.includes(f.field));
  assert.ok(predict(d.artifact,d.inference,{...c.defaults,[active.field]:active.max+5},c.forms).warnings.some(w=>w.includes('外推')));activeExtrapolationChecks++;
}
const manifest=read('artifacts/analysis/website/export-manifest.json');
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex');
for(const [p,h] of Object.entries(manifest.protected_sha256))assert.equal(sha(p),h,`protected ${p}`);
for(const [p,h] of Object.entries(manifest.export_sha256))assert.equal(sha(p),h,`export ${p}`);
const result={status:'passed',executed_with:process.version,fixture_cases:fixtures.length,candidate_models:cache.size,
  scalar_comparisons:comparisons,unscaled_equation_comparisons:unscaledComparisons,invalid_input_checks:invalidInputChecks,active_extrapolation_checks:activeExtrapolationChecks,
  max_absolute_error:maxAbsoluteError,tolerance:'1e-7 absolute + 1e-8 relative',
  method:'Executed browser prediction module in Node.js; independently generated Python point/CI/PI reference fixtures; additional unscaled equation replay.',
  protected_files_unchanged:Object.keys(manifest.protected_sha256).length,source_sha256:sha('web/prediction.mjs'),
  limitations:['Node module execution does not replace DOM/browser interaction tests.','No public API or Vercel execution tested.']};
fs.writeFileSync(path.join(root,'artifacts/validation/stage5-prediction.json'),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify(result));
