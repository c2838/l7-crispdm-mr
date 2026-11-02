import {predict,unscaledCoefficients} from './prediction.mjs';
import {colors,esc,curves,intervals,scatter,empty} from './charts.mjs?v=font-plus-2';
const $=id=>document.getElementById(id);
const labels={baseline:'Baseline + regularized models',dummy:'Mean baseline',ols:'All-feature OLS',kbest:'SelectKBest → OLS',rfe:'RFE → OLS',sfs:'Forward SFS → OLS',lasso_select:'Lasso selection → OLS',elasticnet_select:'ElasticNet selection → OLS',ridge:'Ridge prediction',lasso_reg:'Lasso prediction'};
const requestMethods=['baseline','kbest','rfe','sfs','lasso_select','elasticnet_select'];
const modelOrder=['dummy','ols','kbest','rfe','sfs','lasso_select','elasticnet_select','ridge','lasso_reg'];
const S={file:null,profile:null,excluded:new Set(),categorical:new Set(),results:new Map(),progress:new Map(),generation:0,running:false,cancelled:false,controller:null,selected:null,userSelected:false,timer:null,started:0};
const number=(x,d=3)=>typeof x!=='number'||!Number.isFinite(x)?'—':x!==0&&Math.abs(x)<10**(-d)?x.toExponential(3):x.toLocaleString('en-US',{maximumFractionDigits:d,minimumFractionDigits:d});
const probability=x=>x===0?'< floating-point resolution':typeof x!=='number'?'—':x<.001?x.toExponential(2):number(x,4);
const percentage=x=>typeof x==='number'?(x*100).toFixed(2)+'%':'—';
const inferenceLabel=status=>({available:'OLS區間已計算（有條件假設）',not_applicable_to_baseline_or_regularized_model:'此類模型不套用OLS區間',unavailable_rank_or_df:'設計rank或自由度不足，僅保留點預測',unavailable_numerically_zero_residual_variance:'殘差變異接近0，不提供傳統區間',unavailable_nonfinite_HC3_covariance:'穩健共變異無法計算',unavailable_budget:'區間計算預算不足，其他結果保留'}[status]||'此模型的區間目前不可計算');
function message(text,error=false){$('custom-message').textContent=text;$('custom-message').classList.toggle('error',error);}
async function call(url,options={}){
  const response=await fetch(url,options);
  if(!response.ok){let body;try{body=await response.json();}catch{body=null;}const error=new Error(body?.error?.message||`分析服務回應HTTP ${response.status}。請確認已開啟完整分析預覽。`);error.status=response.status;error.code=body?.error?.code;throw error;}
  return response;
}
function safe(fn){return (...args)=>Promise.resolve().then(()=>fn(...args)).catch(error=>{if(error.name!=='AbortError')message(error.message,true);});}
function setRunning(value){S.running=value;$('custom-run').disabled=value||!S.profile;$('custom-cancel').disabled=!value;document.querySelectorAll('#custom-progress [data-retry]').forEach(b=>b.disabled=value);}
function clearResults(){S.controller?.abort();S.generation++;S.cancelled=false;S.results.clear();S.progress.clear();S.selected=null;S.userSelected=false;clearInterval(S.timer);setRunning(false);$('custom-results').hidden=true;$('custom-progress').innerHTML='';$('custom-download').disabled=true;}
function clearSource(text){clearResults();S.file=null;S.profile=null;S.excluded.clear();S.categorical.clear();$('custom-profile').hidden=true;$('custom-run').disabled=true;message(text);}
function form(file,options){const value=new FormData();value.append('file',file,file.name||'dataset.csv');if(options){value.append('options',JSON.stringify(options));value.append('sha256',S.profile.source.sha256);}return value;}
async function previewFile(file){
  clearSource('正在解析CSV並檢查欄位…');const generation=S.generation;
  if(!file)throw new Error('請先選擇CSV檔案。');if(file.size>3500000)throw new Error('CSV不得超過3,500,000 bytes。');
  const controller=new AbortController();S.controller=controller;
  const profile=await (await call('/api/data/preview',{method:'POST',body:form(file),signal:controller.signal})).json();
  if(generation!==S.generation)return;
  S.file=file;S.profile=profile;renderProfile();message(`已預覽 ${profile.source.rows.toLocaleString()} 筆資料。請確認Target、排除欄位與群組，再執行分析。`);
}
async function loadURL(){
  const url=$('custom-url').value.trim();clearSource('正在驗證並取得公開HTTPS CSV…');const generation=S.generation,controller=new AbortController();S.controller=controller;
  const response=await call('/api/data/url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url}),signal:controller.signal});
  const blob=await response.blob();if(generation!==S.generation)return;
  const file=new File([blob],'remote-dataset.csv',{type:'text/csv'});await previewFile(file);
}
function renderProfile(){
  const p=S.profile;$('custom-profile').hidden=false;
  $('custom-quality').textContent=`${p.source.rows.toLocaleString()} rows · ${p.source.source_columns} columns · ${p.missing_cells} missing cells · ${p.exact_duplicate_rows} exact duplicate rows · ${p.source.bytes.toLocaleString()} bytes · SHA-256 ${p.source.sha256.slice(0,16)}…`;
  const numeric=p.columns.filter(c=>c.kind==='numeric');
  $('custom-target').innerHTML=numeric.map(c=>`<option value="${esc(c.name)}">${esc(c.name)}${c.unique<=1?' · constant':''}</option>`).join('');
  if(numeric.length)$('custom-target').value=numeric.filter(c=>c.unique>1).at(-1)?.name||numeric.at(-1).name;
  $('custom-group').innerHTML='<option value="">None · 無指定群組</option>'+p.columns.map(c=>`<option value="${esc(c.name)}">${esc(c.name)}</option>`).join('');$('custom-transform').value='identity';
  $('custom-preview-table').innerHTML='<table><thead><tr>'+p.columns.map(c=>`<th>${esc(c.name)}</th>`).join('')+'</tr></thead><tbody>'+p.preview.map(row=>'<tr>'+p.columns.map(c=>`<td>${esc(row[c.name]??'∅')}</td>`).join('')+'</tr>').join('')+'</tbody></table>';
  renderColumns();setRunning(false);
  if(!numeric.length){$('custom-run').disabled=true;message('此資料沒有數值欄位可作Target；請換資料或修正格式。',true);}
}
function settings(){
  const target=$('custom-target').value,group=$('custom-group').value||null;
  return {target,exclude:[...S.excluded].filter(n=>n!==target&&n!==group).sort(),categorical:[...S.categorical].filter(n=>n!==target&&n!==group&&!S.excluded.has(n)).sort(),group,target_transform:$('custom-transform').value,seed:0};
}
function renderColumns(){
  if(!S.profile)return;const o=settings();
  $('custom-columns').innerHTML=S.profile.columns.map((c,i)=>{const role=c.name===o.target?'Target':c.name===o.group?'Group':c.kind;const special=role==='Target'||role==='Group';return `<tr><td class="field-name">${esc(c.name)}${c.possible_id?'<small>Possible identifier · 請確認用途</small>':''}</td><td>${esc(role)}</td><td>${c.missing}</td><td>${c.unique}</td><td><input type="checkbox" data-exclude="${esc(c.name)}" aria-label="Exclude ${esc(c.name)}" ${S.excluded.has(c.name)||role==='Group'?'checked':''} ${special?'disabled':''}></td><td>${c.kind==='numeric'?`<input type="checkbox" data-category="${esc(c.name)}" aria-label="Treat ${esc(c.name)} as categorical" ${S.categorical.has(c.name)?'checked':''} ${special||S.excluded.has(c.name)?'disabled':''}>`:'Categorical'}</td></tr>`;}).join('');
  const fields=S.profile.columns.filter(c=>c.name!==o.target&&c.name!==o.group&&!S.excluded.has(c.name));
  const encoded=fields.reduce((n,c)=>n+(c.kind==='categorical'||S.categorical.has(c.name)?Math.max(0,c.unique-1):Number(c.unique>1)),0);
  $('custom-input-summary').textContent=`${fields.length} raw inputs · ${encoded} schema-estimated encoded fields (not a fitted encoder)${fields.length<14?' · 教學示範：低於正式題目14欄下限':''}`;
}
function progressUI(){
  $('custom-progress').innerHTML=requestMethods.map(method=>{const p=S.progress.get(method)||{status:'queued'};const duration=p.status==='running'?` · ${Math.round((Date.now()-p.started)/1000)}s`:'';return `<li data-status="${esc(p.status)}"><strong>${labels[method]}</strong><span class="state-text">${esc(p.status+duration)}</span>${p.message?`<small>${esc(p.message)}</small>`:''}${['failed','cancelled','partial_timeout','unavailable','partial_unavailable'].includes(p.status)?`<button type="button" class="subtle-button" data-retry="${method}" ${S.running?'disabled':''}>Retry · 重試</button>`:''}</li>`;}).join('');
}
function allModels(){return [...S.results.values()].flatMap(r=>r.models.map(m=>({...m,request_method:r.request_method,analysis_id:r.analysis_id,split:r.split,request_warnings:r.warnings})));}
function selectedModel(){return allModels().find(m=>m.method===S.selected);}
function automaticRepresentative(){return allModels().filter(m=>!['dummy','ridge','lasso_reg'].includes(m.method)).sort((a,b)=>a.cv.rmse-b.cv.rmse||a.selected_count-b.selected_count||a.candidate_id.localeCompare(b.candidate_id))[0];}
async function executeMethod(method,generation,options){
  const controller=new AbortController();S.controller=controller;const timeout=setTimeout(()=>controller.abort(),240000);S.progress.set(method,{status:'running',started:Date.now()});progressUI();
  try{
    const data=await (await call('/api/analyze/'+method,{method:'POST',body:form(S.file,options),signal:controller.signal})).json();
    if(generation!==S.generation)throw new DOMException('Changed configuration','AbortError');
    if(data.data_sha256!==S.profile.source.sha256||JSON.stringify(data.options)!==JSON.stringify(options))throw new Error('資料或設定綁定不一致，拒絕混用結果。');
    const prior=[...S.results.values()][0];if(prior&&prior.analysis_id!==data.analysis_id)throw new Error('分析指紋不一致，請重新設定並執行。');
    S.results.set(method,data);S.progress.set(method,{status:data.status==='completed'?'succeeded':data.status,message:`${data.completed_model_count} model(s) · ${number(data.elapsed_s,1)}s${data.status==='completed'?'':' · 未完成全部分析'}`});
    renderResults();
  }catch(error){
    if(generation!==S.generation)return;
    const cancelled=error.name==='AbortError'&&S.cancelled;
    S.progress.set(method,{status:cancelled?'cancelled':'failed',message:cancelled?'已停止等待；伺服器可能仍在協作收尾。':error.name==='AbortError'?'等待超時；伺服器可能仍在收尾。':error.message});
    if(cancelled)throw error;
    if([400,403,409,413,415,422].includes(error.status)&&error.code!=='analysis_input')throw error;
  }finally{clearTimeout(timeout);if(generation===S.generation)progressUI();}
}
async function run(methods=requestMethods){
  if(S.running||!S.profile)return;
  const options=settings();if(!options.target)throw new Error('請選擇數值Target。');
  const generation=S.generation;S.cancelled=false;setRunning(true);
  if(methods===requestMethods){S.results.clear();S.selected=null;S.userSelected=false;S.progress.clear();$('custom-results').hidden=true;for(const m of requestMethods)S.progress.set(m,{status:'queued'});}
  S.timer=setInterval(progressUI,1000);progressUI();message('正在依序執行。進度依實際請求回應更新，test不參與特徵或參數選擇。');
  try{
    for(const method of methods){if(generation!==S.generation||S.cancelled)break;await executeMethod(method,generation,options);}
  }catch(error){if(error.name!=='AbortError')throw error;}
  finally{
    clearInterval(S.timer);
    if(generation===S.generation){
      for(const [method,p] of S.progress)if(p.status==='queued'||p.status==='running')S.progress.set(method,{status:'cancelled',message:'未繼續送出或已停止等待。'});
      setRunning(false);progressUI();renderResults();
      const completed=[...S.progress.values()].filter(p=>p.status==='succeeded').length;
      message(S.cancelled?`已取消。保留 ${allModels().length} 個已回應模型；伺服器的在途求解不保證立即停止。`:`${completed}/6 個方法請求成功，取得 ${allModels().length} 個模型。${completed===6?'完整比較已完成。':'未完成的項目有明確狀態，可重試；不視為全部成功。'}`);
    }
  }
}
function renderResults(){
  const models=allModels();$('custom-download').disabled=S.results.size===0;
  if(!models.length){$('custom-results').hidden=true;return;}$('custom-results').hidden=false;
  const representative=automaticRepresentative();if(!S.userSelected||!models.some(m=>m.method===S.selected))S.selected=representative?.method||models[0].method;
  const ordered=modelOrder.map(k=>models.find(m=>m.method===k)).filter(Boolean);
  $('custom-comparison').innerHTML=ordered.map(m=>`<tr class="${m.method===S.selected?'selected-row':''}"><td><button type="button" data-custom-model="${m.method}">${labels[m.method]}</button></td><td>${m.selected_count}</td><td>${number(m.cv.rmse)}</td><td>${number(m.test_metrics.rmse)}</td><td>${number(m.test_metrics.r2,4)}</td><td>${percentage(m.interval_summary?.observation_pi_coverage)}</td></tr>`).join('');
  $('custom-model').innerHTML=ordered.map(m=>`<option value="${m.method}">${labels[m.method]} · ${m.candidate_id}</option>`).join('');$('custom-model').value=S.selected;
  const complete=[...S.progress.values()].filter(v=>v.status==='succeeded').length;
  $('custom-selection-note').textContent=`${complete===6?'完整比較':'部分結果'} · CV代表：${representative?labels[representative.method]:'尚無OLS'}。代表只依development CV RMSE（同分優先較少特徵）決定，不依test挑選。test指標完整計分；切換目前模型只供比較。`;
  renderModel();
}
function renderModel(){
  const m=selectedModel();if(!m)return;const a=m.artifact,r=S.results.get(m.request_method),raw=unscaledCoefficients(a);
  $('custom-model-metrics').innerHTML=[['Test MAE',number(m.test_metrics.mae)],['Test RMSE',number(m.test_metrics.rmse)],['Test R²',number(m.test_metrics.r2,4)],['PI coverage / width',percentage(m.interval_summary?.observation_pi_coverage)+' / '+number(m.interval_summary?.observation_pi_mean_width)]].map(([label,value])=>`<div>${label}<strong>${value}</strong></div>`).join('');
  $('custom-equation').textContent=`${a.target_transform==='log'&&a.method!=='dummy'?'ln('+a.target+')':a.target} = ${number(raw.intercept,5)} `+a.selected_columns.map((c,i)=>`${raw.coefficients[i]>=0?'+':'−'} ${number(Math.abs(raw.coefficients[i]),5)} × ${c.category===null?c.field:`I(${c.field}=${JSON.stringify(c.category)})`}`).join(' ');
  $('custom-model-warnings').textContent=`${m.split.development_rows} development / ${m.split.test_rows} test · ${a.raw_input_fields.length} raw / ${a.preprocessor.columns.length} encoded / ${m.selected_count} selected · ${inferenceLabel(m.inference_status)}。${m.request_warnings.join(' ')}${a.target_transform==='log'&&a.method!=='dummy'?' exp回轉換為幾何位置，不是原尺度算術平均。':''} 公式顯示四捨五入，計算與下載保留完整精度。`;
  renderCoefficients();renderPredictor();renderCharts();renderDiagnostics();
}
function renderCoefficients(){
  const m=selectedModel();if(!m)return;const basis=$('custom-basis').value,cov=$('custom-covariance').value;
  let rows=m.coefficient_intervals.filter(r=>r.basis===basis&&r.covariance===cov);
  if(!rows.length){const b=basis==='unscaled_encoded'?unscaledCoefficients(m.artifact):m.artifact.model;rows=[{column:'Intercept',coefficient:b.intercept},...m.artifact.selected_columns.map((c,i)=>({column:c.label,coefficient:b.coefficients[i]}))];}
  const vif=new Map((m.diagnostics?.vif||[]).map(v=>[v.label,v.vif]));
  $('custom-coefficients').innerHTML=rows.map(r=>`<tr><td class="field-name">${esc(r.column)}</td><td>${number(r.coefficient,5)}</td><td>${r.ci_lower!==undefined?'['+number(r.ci_lower,4)+', '+number(r.ci_upper,4)+']':'—'}</td><td>${esc(probability(r.p_value))}</td><td>${number(vif.get(r.column),2)}</td></tr>`).join('');
}
function renderPredictor(){
  const m=selectedModel(),a=m.artifact;const fields=m.forms.filter(f=>a.selected_raw_fields.includes(f.field));
  $('custom-predict-inputs').innerHTML=fields.map((f,i)=>`<div class="input-item"><label for="custom-input-${i}">${esc(f.field)}</label><input id="custom-input-${i}" data-custom-field="${esc(f.field)}" type="text" ${f.kind==='numeric'?'inputmode="decimal"':`list="custom-options-${i}"`} value="${esc(m.defaults[f.field]??'')}">${f.kind==='categorical'?`<datalist id="custom-options-${i}">${f.categories.map(v=>`<option value="${esc(v)}"></option>`).join('')}</datalist>`:''}<small>${f.kind==='numeric'?`Training: ${number(f.min,2)} – ${number(f.max,2)}`:esc(f.categories.join(' / '))}</small></div>`).join('')||'<p class="muted">Intercept only · 此模型無需輸入。</p>';
  $('custom-predict-label').textContent=a.target_transform==='log'&&a.method!=='dummy'?'Geometric-location prediction':'Point prediction';calculate();
}
function calculate(){
  const m=selectedModel();if(!m)return;const input={...m.defaults};
  try{
    document.querySelectorAll('#custom-predict-inputs input').forEach(e=>{input[e.dataset.customField]=e.value;e.removeAttribute('aria-invalid');});
    const p=predict(m.artifact,m.inference,input,m.forms);$('custom-prediction').textContent=number(p.prediction,4);
    $('custom-predict-intervals').innerHTML=m.inference?[[m.artifact.target_transform==='log'?'Geometric-location CI':'Mean-response CI','location_ci'],['Observation PI','observation_pi'],['HC3 location CI','location_ci_hc3']].map(([label,key])=>`<div><dt>95% ${label}</dt><dd>[${number(p[key+'_lower'])}, ${number(p[key+'_upper'])}]</dd></div>`).join(''):'<div><dt>OLS CI / PI</dt><dd>Not available</dd></div>';
    $('custom-predict-warning').textContent=p.warnings.join('\n');
  }catch(error){$('custom-prediction').textContent='—';$('custom-predict-intervals').innerHTML='';$('custom-predict-warning').textContent=error.message;document.querySelectorAll('#custom-predict-inputs input').forEach(e=>{const f=m.forms.find(x=>x.field===e.dataset.customField);if(f.kind==='numeric'&&e.value.trim()&&!Number.isFinite(Number(e.value)))e.setAttribute('aria-invalid','true');});}
}
function renderCharts(){
  const m=selectedModel();if(!m)return;const r=S.results.get(m.request_method);
  const candidates=r.cv_candidates.filter(c=>c.method===m.method&&c.cv).map(c=>({...c,mean_cv_selected_count:c.mean_selected_count}));
  curves($('custom-cv-chart'),[{label:labels[m.method],color:colors[m.method]||'#4b5e70',entries:candidates}],'rmse','source units',m.candidate_id,id=>message(`CV候選 ${id}。此曲線只比較既定CV；詳細方程與test仍為目前方法依CV選定的 ${m.candidate_id}，未對其他候選額外評分test。`));
  intervals($('custom-interval-chart'),m.heldout_plot.rows,'source units','Held-out');
  if(m.diagnostic_plot){const p=m.diagnostic_plot;scatter($('custom-residual-chart'),p.fitted,p.residual,m.artifact.target_transform==='log'?'Fitted log target':'Fitted target','Residual','Custom development residuals',{zero:true});scatter($('custom-qq-chart'),p.qq_theoretical,p.qq_observed,'Normal quantile','Standardized residual','Custom development normal Q-Q',{diagonal:true});}
  else{empty($('custom-residual-chart'),'OLS diagnostics unavailable / 此模型無適用的OLS推論。');empty($('custom-qq-chart'),'No valid residual inference / 不硬算退化設計的推論。');}
}
function renderDiagnostics(){
  const m=selectedModel(),d=m.diagnostics;
  const entries=d?[
    ['Heteroskedasticity',`Koenker BP p=${probability(d.heteroskedasticity.p_value)}。不以單一p值宣稱假設成立。`],
    ['Normality',`Jarque–Bera p=${probability(d.normality.p_value)}；skew=${number(d.normality.skewness,2)}。`],
    ['Functional form',`HC3 quadratic fitted-value diagnostic p=${probability(d.functional_form.p_value)}；僅作診斷。`],
    ['Collinearity',`Max VIF=${number(Math.max(...d.vif.map(v=>v.vif??Infinity)),2)}；condition number=${number(d.condition_number_standardized_design,2)}。`],
    ['Influence',`Max Cook's D=${number(d.influence.max_cooks_distance,4)}。最大Cook點單列刪除敏感度：擬合值最大差 ${number(d.sensitivity.development_fitted_change_max_abs,4)}；正式模型未刪點。`],
    ['Independence / interval scope',`${m.split.grouped?'已依群組／重複X隔離切分，但未修正群內相關。':'沒有已確認的時間／群組設計，獨立性仍未建立。'} 所有區間都條件於已選模型，不作臨床或因果判斷。`]
  ]:[['Inference unavailable',inferenceLabel(m.inference_status)+'。點預測與可計算指標仍如實呈現。']];
  $('custom-diagnostics').innerHTML=entries.map(([title,text])=>`<div><strong>${title}</strong><p>${esc(text)}</p></div>`).join('');
}
function download(){const value={schema_version:'1.0',source:S.profile.source,options:settings(),request_statuses:Object.fromEntries(S.progress),results:[...S.results.values()],note:'Only received results. Partial/cancelled is not complete; data/model provenance is preserved.'};const blob=new Blob([JSON.stringify(value,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='custom-analysis-'+S.profile.source.sha256.slice(0,12)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('custom-file').addEventListener('change',()=>clearSource('檔案已變更，請按Preview file重新預覽。'));
$('custom-url').addEventListener('input',()=>{if(S.profile)clearSource('網址已變更，請重新取得CSV。');});
$('custom-preview-file').addEventListener('click',safe(()=>previewFile($('custom-file').files[0])));$('custom-load-url').addEventListener('click',safe(loadURL));
for(const id of ['custom-target','custom-group','custom-transform'])$(id).addEventListener('change',()=>{clearResults();renderColumns();message('設定已變更，舊結果已隔離；請重新執行分析。');});
$('custom-columns').addEventListener('change',event=>{const e=event.target;if(e.hasAttribute('data-exclude'))e.checked?S.excluded.add(e.dataset.exclude):S.excluded.delete(e.dataset.exclude);else if(e.hasAttribute('data-category'))e.checked?S.categorical.add(e.dataset.category):S.categorical.delete(e.dataset.category);else return;clearResults();renderColumns();message('X設定已變更，請重新執行。');});
$('custom-exclude-id').addEventListener('click',()=>{S.profile.columns.filter(c=>c.possible_id).forEach(c=>S.excluded.add(c.name));clearResults();renderColumns();message('已排除建議識別欄位；請確認沒有誤排其他有效輸入。');});
$('custom-run').addEventListener('click',safe(()=>run()));$('custom-cancel').addEventListener('click',()=>{S.cancelled=true;S.controller?.abort();$('custom-cancel').disabled=true;message('正在停止後續請求；已在伺服器求解的部分由檢查點收尾，不保證立即停止。');});
$('custom-progress').addEventListener('click',safe(event=>{const b=event.target.closest('[data-retry]');if(b)return run([b.dataset.retry]);}));
$('custom-model').addEventListener('change',()=>{S.selected=$('custom-model').value;S.userSelected=true;renderResults();});
$('custom-comparison').addEventListener('click',event=>{const b=event.target.closest('[data-custom-model]');if(b){S.selected=b.dataset.customModel;S.userSelected=true;renderResults();}});
for(const id of ['custom-basis','custom-covariance'])$(id).addEventListener('change',renderCoefficients);
$('custom-predict-form').addEventListener('submit',e=>{e.preventDefault();calculate();});$('custom-predict-inputs').addEventListener('input',calculate);$('custom-download').addEventListener('click',download);
let resize;window.addEventListener('resize',()=>{clearTimeout(resize);resize=setTimeout(renderCharts,180);});
call('/api/health').then(r=>r.json()).then(()=>{$('custom-service').textContent='Analysis service ready · 可分析';}).catch(()=>{$('custom-service').textContent='Analysis service unavailable';message('分析服務目前無法連線；正式兩題仍可操作。請開啟完整分析預覽後再使用自訂資料。',true);});
