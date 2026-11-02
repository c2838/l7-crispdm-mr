import {predict,unscaledCoefficients} from './prediction.mjs';
import {colors,esc,curves,scatter,intervals,learning,empty} from './charts.mjs?v=font-plus-2';

const $=id=>document.getElementById(id);
const names={dummy:'Mean baseline',ols:'All-feature OLS',kbest:'SelectKBest → OLS',sfs:'Forward SFS → OLS',rfe:'RFE → OLS',lasso_select:'Lasso selection → OLS',elasticnet_select:'ElasticNet selection → OLS',ridge:'Ridge prediction',lasso_reg:'Lasso prediction'};
const order=['dummy','ols','kbest','rfe','sfs','lasso_select','elasticnet_select','ridge','lasso_reg'];
const five=['kbest','sfs','rfe','lasso_select','elasticnet_select'];
const captions={sgemm:'Original runtime · 主分析',sgemm_log:'Log runtime · 補充',student:'With prior grades · 主分析',student_background:'Background only · 補充'};
const state={caseData:null,detail:null,card:null,compare:false,caseSequence:0,detailSequence:0};
const cache=new Map();
const fmt=(v,d=3)=>v===null||v===undefined||!Number.isFinite(v)?'—':Math.abs(v)!==0&&Math.abs(v)<10**(-d)?v.toExponential(2):v.toLocaleString('en-US',{maximumFractionDigits:d,minimumFractionDigits:d});
const pvalue=v=>v===0?'< floating-point resolution':v===null||v===undefined?'—':v<.001?v.toExponential(2):fmt(v,4);
const pct=v=>Number.isFinite(v)?(v*100).toFixed(2)+'%':'—';
const gpu=()=>state.caseData.id.startsWith('sgemm');
const shortUnit=()=>gpu()?'ms':'grade points';
async function json(path){if(!cache.has(path))cache.set(path,fetch(path).then(r=>{if(!r.ok)throw new Error(`無法載入分析資料 (${r.status})`);return r.json();}).catch(e=>{cache.delete(path);throw e;}));return cache.get(path);}
function report(error){$('load-error').hidden=false;$('load-error').textContent=error.message;console.error(error);$('main').removeAttribute('aria-busy');}
const action=fn=>(...args)=>Promise.resolve().then(()=>fn(...args)).catch(report);
function download(name,value,type='application/json'){const blob=new Blob([typeof value==='string'?value:JSON.stringify(value,null,2)],{type}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function candidateLabel(c){if(Object.hasOwn(c.parameters,'k'))return `k = ${c.parameters.k}${c.frozen_winner?' · frozen CV winner':''}`;if(c.method==='dummy'||c.method==='ols')return names[c.method];return `α = ${c.parameters.alpha}${c.parameters.l1_ratio!==undefined?' · L1 ratio = '+c.parameters.l1_ratio:''} · ${c.selected_count} fields${c.frozen_winner?' · frozen CV winner':''}`;}

async function selectScenario(id){
  const seq=++state.caseSequence;++state.detailSequence;$('main').setAttribute('aria-busy','true');
  const data=await json(`data/${id}.json`);if(seq!==state.caseSequence)return;
  state.caseData=data;state.compare=false;
  $('dataset').value=id.startsWith('sgemm')?'sgemm':'student';
  const options=id.startsWith('sgemm')?['sgemm','sgemm_log']:['student','student_background'];
  $('variant').innerHTML=options.map(v=>`<option value="${v}">${captions[v]}</option>`).join('');$('variant').value=id;
  $('load-error').hidden=true;renderContext();await selectCandidate(data.representative_id);
}
async function selectCandidate(id){
  const data=state.caseData,card=data.candidates.find(c=>c.id===id);if(!card)throw new Error('Candidate not found.');
  const seq=++state.detailSequence;$('main').setAttribute('aria-busy','true');
  const detail=await json(card.detail);if(seq!==state.detailSequence||data!==state.caseData)return;
  state.card=card;state.detail=detail;renderControls();renderResults();renderCoefficients();renderPredictor();renderDiagnostics();renderCharts();$('main').removeAttribute('aria-busy');
}
function renderContext(){
  const c=state.caseData,isGPU=gpu();
  $('explorer-title').textContent=(isGPU?'GPU Runtime':'Student Performance')+' Regression Explorer';
  document.title=(isGPU?'GPU Runtime':'Student Performance')+' · Regression Explorer';
  $('case-title').textContent=isGPU?'Can a linear model explain GPU runtime?':'What do prior grades tell us about final performance?';
  $('case-description').textContent=isGPU?'以 GPU 核心的分塊、workgroup、向量寬度與快取等設定，估計固定矩陣工作負載的四次平均執行時間。':'以葡萄牙語課程的學生資料估計 G3 期末成績。主分析包含 G1／G2；背景版本移除前期成績，兩者均屬回顧條件估計。';
  $('case-conclusion').textContent=isGPU?'Model limitation case · 原始特徵的加法線性模型只能解釋部分變異。忠實呈現方法、負時間預測與區間限制；不由此否定所有線性模型形式。':'Conditional prediction · 前期成績提供強烈預測訊息；高 R² 不代表因果關係、假設全部成立或能於開學時提前預警。';
  $('hero-badges').innerHTML=[`${c.development_rows.toLocaleString()} development / ${c.test_rows.toLocaleString()} test`,`${c.raw_fields} raw inputs`,`${c.encoded_fields} encoded fields`,`Target: ${c.target} (${c.unit})`,'Fixed 80 / 20 split'].map(v=>`<span>${esc(v)}</span>`).join('');
  const kaggle=isGPU?'https://www.kaggle.com/datasets/rupals/gpu-runtime':'https://www.kaggle.com/datasets/uciml/student-alcohol-consumption';
  const uci=isGPU?'https://archive.ics.uci.edu/dataset/440/sgemm+gpu+kernel+performance':'https://archive.ics.uci.edu/dataset/320/student+performance';
  $('source-note').innerHTML=`Sources: <a href="${kaggle}" target="_blank" rel="noopener">Kaggle ${isGPU?'GPU Runtime · v4':'Student Alcohol Consumption · v2'}</a> · <a href="${uci}" target="_blank" rel="noopener">UCI original dataset</a>. 原始來源 CC BY 4.0；${isGPU?'Kaggle 與 UCI 原檔指紋一致，四個 Run 不作輸入。':'保留 UCI 原始授權；僅使用 student-por，不混入跨科重複學生。'}`;
  const workflow=[
    ['Business Understanding','Define the prediction task',isGPU?'預測固定硬體／工作負載中未見設定的四次平均時間，分析線性模型是否足以支援效能估計。':'估計已知資料條件下的期末成績；主模型需有 G1／G2，不主張提前預警或因果效果。'],
    ['Data Understanding','Inspect quality and scope',`${isGPU?'241,600':'649'} 筆公開觀測；正式資料無缺值、無完全重複列。${c.raw_fields} 個本版本原始輸入、${c.encoded_fields} 個 development 編碼欄位。`],
    ['Data Preparation','Keep fitting within training folds','固定 80/20 development/test；填補、drop-first 類別編碼、標準化及選取均在相應 training fold 擬合。GPU 四次計時只用於定義 Target。'],
    ['Modeling','Compare five selection methods','SelectKBest、RFE、Forward SFS、Lasso 與 ElasticNet 選取後重新擬合 OLS；另比較 Dummy、全特徵 OLS、Ridge／Lasso 預測模型。'],
    ['Evaluation','Report evidence and limitations',isGPU?'原尺度凍結代表 Test R² 0.4099、RMSE 285.23 ms；18.40% 負點預測，殘差與條件區間有明顯限制。log 版本為事先規劃的補充。':'含前期成績代表 Test R² 0.9290；背景代表 0.3654。含前期成績 PI 在 130 筆 test 覆蓋 100%，平均寬 5.31 分，不能當作未來保證。'],
    ['Deployment','Explore a new sample','本機互動展示、單筆推論與自訂 CSV／網址分析已提供；公開部署與遠端驗收仍待後續完成。新學校／新 GPU 外部效能未驗證。']
  ];
  $('workflow-grid').innerHTML=workflow.map((w,i)=>`<article><span>0${i+1} / ${w[0]}</span><h3>${w[1]}</h3><p>${esc(w[2])}</p></article>`).join('');
}
function renderControls(){
  const card=state.card,c=state.caseData,method=card.method;
  document.querySelectorAll('[data-method]').forEach(b=>{const active=b.dataset.method===method;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
  $('compare-all').classList.toggle('active',state.compare);$('compare-all').setAttribute('aria-pressed',String(state.compare));
  const candidates=c.candidates.filter(e=>e.method===method);
  $('candidate-label').textContent=['kbest','rfe','sfs'].includes(method)?'NUMBER OF ENCODED FEATURES':method.includes('select')?'SPARSE SELECTOR PARAMETERS':'MODEL PARAMETERS';
  $('candidate').innerHTML=candidates.map(e=>`<option value="${esc(e.id)}">${esc(candidateLabel(e))}</option>`).join('');$('candidate').value=card.id;
  $('k-buttons').innerHTML=['kbest','rfe','sfs'].includes(method)?candidates.map(e=>`<button data-candidate-id="${esc(e.id)}" class="${e.id===card.id?'selected ':''}${e.frozen_winner?'cv-best':''}" aria-pressed="${e.id===card.id}">${e.parameters.k}${e.frozen_winner?'<small>CV best</small>':''}</button>`).join(''):'';
  $('selection-status').textContent=card.representative?'Frozen representative · 凍結主代表':card.frozen_winner?'Frozen method winner · 凍結方法勝出模型':'Development exploration · 開發候選探索';
  $('method-detail').textContent=`${names[method]} · ${candidateLabel(card)} · ${card.selected_count} selected encoded / ${state.detail.artifact.selected_raw_fields.length} selected raw fields`;
}
function renderResults(){
  const d=state.detail,c=state.caseData,card=state.card,test=d.frozen?.test_metrics,m=test||card.cv;
  $('metric-scope').textContent=test?'HELD-OUT EVALUATION · 此方法已在測試前凍結':'DEVELOPMENT TUNING CV · 此候選沒有額外評分 test';
  const adj=d.diagnostics?.development_ols_adjusted_r2;
  const items=[['MAE',m.mae,shortUnit(),test?'Held-out test':'Development CV'],['RMSE',m.rmse,shortUnit(),test?'Held-out test':'Development CV'],['R²',m.r2,'',test?'Held-out test':'Development CV'],['Adjusted R²',adj,'',c.target_transform==='log'?'Development OLS · log scale':'Development OLS'],['CV RMSE',card.cv.rmse,shortUnit(),'Selection score · 5 folds']];
  $('metrics').innerHTML=items.map(v=>`<article class="metric"><div class="metric-label">${v[0]}</div><div class="metric-value">${fmt(v[1],v[0].includes('R²')?4:2)}</div><div class="metric-note">${esc(v[2])}<small>${esc(v[3])}</small></div></article>`).join('');
  $('feature-chips').innerHTML=card.selected_labels.length?card.selected_labels.map(v=>`<span class="chip">${esc(v)}</span>`).join(''):'<span class="chip">Intercept only · 僅截距</span>';
  $('model-note').textContent=test?`此模型的 ${test.n.toLocaleString()} 筆 test 成績已固定；下方參數探索不改寫正式代表。選取與 CV 都使用 development。`:'此頁公式、係數、區間與診斷來自目前候選的真實 development 擬合；指標卡顯示既有 CV。正式 test 比較表保持原凍結模型的成績。';
  const winners=order.map(method=>c.candidates.find(x=>x.id===c.winner_ids[method]));
  $('comparison-body').innerHTML=winners.map(e=>`<tr class="${e.id===card.id?'selected-row':''}"><td><button data-candidate-id="${esc(e.id)}">${names[e.method]}</button>${e.representative?'<span class="cv-label">Frozen representative</span>':''}</td><td>${e.selected_count}</td><td>${fmt(e.cv.rmse)}</td><td>${fmt(e.test.rmse)}</td><td>${fmt(e.test.r2,4)}</td><td class="features-cell">${esc(e.selected_labels.join(', ')||'Intercept')}</td></tr>`).join('');
  const a=d.artifact,raw=unscaledCoefficients(a),parts=a.selected_columns.map((col,i)=>`${raw.coefficients[i]>=0?'+':'−'} ${fmt(Math.abs(raw.coefficients[i]),5)} × ${col.category===null?col.field:`I(${col.field} = ${JSON.stringify(col.category)})`}`);
  $('equation').textContent=`${a.target_transform==='log'&&a.method!=='dummy'?'ln('+a.target+')':a.target} = ${fmt(raw.intercept,5)} ${parts.join(' ')}`;
  $('equation-note').textContent=a.target_transform==='log'&&a.method!=='dummy'?'先預測 log，再取 exp：幾何位置，並非原尺度算術平均。顯示數字四捨五入；計算與下載使用完整精度。':'係數對應未標準化的 encoded 欄位；I(條件) 為 0/1，reference 類別的 dummy 為 0。計算使用完整精度。';
}
function renderCoefficients(){
  const d=state.detail,a=d.artifact,basis=$('coefficient-basis').value,cov=$('covariance').value;
  let rows=d.coefficient_intervals.filter(r=>r.basis===basis&&r.covariance===cov);
  if(!rows.length){const raw=basis==='unscaled_encoded'?unscaledCoefficients(a):a.model;rows=[{column:'Intercept',coefficient:raw.intercept},...a.selected_columns.map((c,i)=>({column:c.label,coefficient:raw.coefficients[i]}))];}
  const vif=new Map((d.diagnostics?.vif||[]).map(x=>[x.label,x.vif]));
  $('coefficient-body').innerHTML=rows.map(r=>`<tr><td>${esc(r.column)}</td><td>${fmt(r.coefficient,5)}</td><td>${fmt(r.standard_error,5)}</td><td>${r.ci_lower!==undefined?`[${fmt(r.ci_lower,4)}, ${fmt(r.ci_upper,4)}]`:'—'}</td><td>${esc(pvalue(r.p_value))}</td><td>${fmt(vif.get(r.column),2)}</td></tr>`).join('');
  $('coefficient-note').textContent=d.inference?`${cov} · ${basis==='unscaled_encoded'?'原尺度 encoded':'標準化 encoded'}。${a.target_transform==='log'?'反應係數為 log 單位。':''}VIF 使用選定標準化設計，與係數基底切換無關。`:`${d.inference_status}：此模型不提供傳統 OLS 推論，係數仍可用於點預測。`;
}
function renderPredictor(){
  const d=state.detail,c=state.caseData,fields=c.forms.filter(f=>d.artifact.selected_raw_fields.includes(f.field));
  $('prediction-inputs').innerHTML=fields.map((f,i)=>`<div class="input-item"><label for="input-${i}">${esc(f.field)}</label><input id="input-${i}" data-field="${esc(f.field)}" ${f.kind==='numeric'?'type="text" inputmode="decimal" autocomplete="off"':'type="text" list="options-'+i+'"'} value="${esc(c.defaults[f.field])}">${f.kind==='categorical'?`<datalist id="options-${i}">${f.categories.map(v=>`<option value="${esc(v)}"></option>`).join('')}</datalist>`:''}<small>${f.kind==='numeric'?`Training: ${esc(f.min)} – ${esc(f.max)}${f.allowed_values?' · '+esc(f.allowed_values.join(', ')):''}`:`${esc(f.categories.join(' / '))} · reference: ${esc(f.reference)}`}</small></div>`).join('')||'<p class="muted">This is an intercept-only model. 不需要輸入欄位。</p>';
  $('prediction-label').textContent=d.artifact.target_transform==='log'&&d.artifact.method!=='dummy'?'Geometric-location prediction':'Point prediction';
  $('prediction-unit').textContent=shortUnit();
  $('predictor-note').textContent=gpu()?'GPU Target 為新設定四次 Run 的平均時間。可計算不保證此參數組合能在硬體執行；未選欄位不影響此方程。':'只顯示此模型選中的原始欄位；未選欄位不影響方程。結果為回顧條件估計，不代表個人因果或開學預警。';
  calculatePrediction();
}
function calculatePrediction(){
  if(!state.detail)return;const input={...state.caseData.defaults};
  try{
    document.querySelectorAll('#prediction-inputs input').forEach(el=>{if(el.validity.badInput)throw new Error(`${el.dataset.field} 必須是有效數值。`);input[el.dataset.field]=el.value;el.removeAttribute('aria-invalid');});
    const d=state.detail,result=predict(d.artifact,d.inference,input,state.caseData.forms);$('predicted-value').textContent=fmt(result.prediction,3);
    const label=d.artifact.target_transform==='log'?'Geometric-location CI':'Mean-response CI';
    $('prediction-intervals').innerHTML=d.inference?[[label,'location_ci'],['Observation PI','observation_pi'],['HC3 location CI','location_ci_hc3']].map(([name,key])=>`<div><dt>95% ${name}</dt><dd>[${fmt(result[key+'_lower'],3)}, ${fmt(result[key+'_upper'],3)}]</dd></div>`).join(''):'<div><dt>OLS CI / PI</dt><dd>Not available · 不適用</dd></div>';
    if(gpu()&&result.prediction<0)result.warnings.push('負時間為線性模型的限制，已忠實呈現，未裁切為 0。');
    if(!gpu()&&(result.prediction<0||result.prediction>20))result.warnings.push('點預測超出成績 0–20 的文件範圍，未裁切。');
    if(result.observation_pi_lower!==undefined&&(result.observation_pi_lower<0||!gpu()&&result.observation_pi_upper>20))result.warnings.push('PI 超出目標的實際範圍，反映模型／誤差假設限制；未裁切。');
    $('prediction-warnings').classList.remove('error');$('prediction-warnings').innerHTML=result.warnings.length?'<ul>'+result.warnings.map(w=>`<li>${esc(w)}</li>`).join('')+'</ul>':'';
  }catch(error){$('predicted-value').textContent='—';$('prediction-intervals').innerHTML='';$('prediction-warnings').classList.add('error');$('prediction-warnings').textContent=error.message;document.querySelectorAll('#prediction-inputs input').forEach(el=>{const field=state.caseData.forms.find(f=>f.field===el.dataset.field);if(field?.kind==='numeric'&&el.value.trim()!==''&&!Number.isFinite(Number(el.value)))el.setAttribute('aria-invalid','true');});}
}
function renderDiagnostics(){
  const d=state.detail,diag=d.diagnostics,summary=d.frozen?.interval_summary;
  $('interval-source').textContent=d.frozen?'Held-out test · 凍結模型':'Development sample · 候選探索';
  $('interval-summary').innerHTML=summary?[
    ['Nominal PI level','95%'],['Held-out PI coverage',`${pct(summary.observation_pi_coverage)} (${summary.covered_count.toLocaleString()}/${summary.rows.toLocaleString()})`],
    ['Mean PI width',fmt(summary.observation_pi_mean_width,2)+' '+shortUnit()],['Negative point predictions',`${summary.negative_prediction_count.toLocaleString()} / ${summary.rows.toLocaleString()}`]
  ].map(([label,value])=>`<div>${esc(label)}<strong>${esc(value)}</strong></div>`).join(''):'';
  $('interval-note').textContent=(d.frozen?`完整 ${state.caseData.test_rows.toLocaleString()} 筆 test 計算指標與覆蓋；圖形最多 2,000 筆顯示點。`:'開發樣本圖，不計算或冒稱新的 held-out 覆蓋率。')+' 橫軸是依目前模型預測排序的樣本，不是單一自變數。95% 為名目水準；HC3 限位置 CI，log 位置不是算術平均。'+(!d.inference?' 此模型無 OLS CI／PI，僅顯示點預測與觀測。':'');
  if(!diag){$('diagnostic-summary').innerHTML='<div><strong>OLS diagnostics unavailable</strong><p>'+esc(d.inference_status)+'。下方全特徵 OLS 學習曲線仍屬獨立基準比較。</p></div>';$('influence-body').innerHTML='';return;}
  const entries=[
    ['Heteroskedasticity',`Koenker BP p = ${pvalue(diag.heteroskedasticity.p_value)}。${diag.heteroskedasticity.status==='computed'?'結合殘差圖判讀，不宣稱等變異成立。':'目前設計無法計算此檢定。'}`],
    ['Normality',`Jarque–Bera p = ${pvalue(diag.normality.p_value)}；skew = ${fmt(diag.normality.skewness,2)}。大樣本 p 值需搭配形狀與效果。`],
    ['Functional form',`Quadratic fitted-value / HC3 diagnostic p = ${pvalue(diag.functional_form.p_value)}。只作診斷，沒有加入正式模型。`],
    ['Collinearity',`Max VIF = ${fmt(Math.max(...diag.vif.map(v=>v.vif??Infinity)),2)}；condition number = ${fmt(diag.condition_number_standardized_design,2)}。`],
    ['Independence not established','只有兩所學校／一組 GPU benchmark 硬體，隨機列序不當作時間序。未證明跨學校或跨硬體泛化。'],
    ['Conditional inference','CI／PI 以選定欄位與前處理為條件，未修正特徵選擇不確定性。HC3 不會自動修復 PI、非線性或相依誤差。']
  ];
  $('diagnostic-summary').innerHTML=entries.map(([title,text])=>`<div><strong>${title}</strong><p>${esc(text)}</p></div>`).join('');
  $('influence-body').innerHTML=(diag.influence.top_rows||[]).map(r=>`<tr><td>${r.source_row_index_0_based}</td><td>${fmt(r.cooks_distance,5)}</td><td>${fmt(r.leverage,5)}</td><td>${fmt(r.studentized_internal,3)}</td></tr>`).join('');
}
function renderCharts(){
  if(!state.detail)return;const c=state.caseData,d=state.detail,method=state.card.method;
  const visible=state.compare?five:five.includes(method)?[method]:[method];
  const series=visible.map(m=>({label:names[m].replace(' → OLS',''),color:colors[m]||'#4b5e70',entries:c.candidates.filter(e=>e.method===m)}));
  const choose=action(id=>selectCandidate(id));curves($('rmse-chart'),series,'rmse',shortUnit(),state.card.id,choose);curves($('r2-chart'),series,'r2',shortUnit(),state.card.id,choose);
  const plot=d.heldout_plot||d.development_plot,rows=plot.rows,scope=d.frozen?'Held-out':'Development';
  intervals($('interval-chart'),rows,shortUnit(),scope);
  scatter($('actual-chart'),rows.actual,rows.prediction,`Actual (${shortUnit()})`,`Predicted (${shortUnit()})`,`${scope} actual versus predicted`,{diagonal:true});
  $('actual-note').textContent=`${scope} · ${rows.actual.length.toLocaleString()} display points; ${d.frozen?'完整 test 計分，圖形抽取顯示。':'此候選不提供額外 test 評分。'}`;
  const dp=d.diagnostic_plot;
  if(dp){
    const unit=c.target_transform==='log'?'log target':shortUnit();
    scatter($('residual-chart'),dp.fitted,dp.residual,`Development fitted (${unit})`,`Residual (${unit})`,'Development residuals versus fitted',{zero:true});
    scatter($('qq-chart'),dp.qq_theoretical,dp.qq_observed,'Standard normal quantile','Standardized residual quantile','Development normal Q-Q plot',{diagonal:true});
    const top=d.diagnostics.influence.top_rows||[];
    scatter($('influence-chart'),dp.leverage,dp.studentized_internal,'Leverage','Studentized residual','Development leverage and influence',{zero:true,highlight:top.map(v=>[v.leverage,v.studentized_internal])});
    $('residual-note').textContent=`Development diagnostics · ${unit}。散點為有界顯示樣本，診斷統計使用全部 development。`;
  }else{for(const id of ['residual-chart','qq-chart','influence-chart'])empty($(id),'No conditional OLS diagnostics for this estimator / 此模型不提供 OLS 診斷。');$('residual-note').textContent='';}
  learning($('learning-chart'),c.learning_curve,shortUnit());
  const rankLimited=c.learning_curve.flatMap(r=>r.records).filter(r=>r.rank_status==='unavailable_rank_or_df').length;
  if(rankLimited){const note=document.createElement('p');note.className='chart-caption';note.textContent=`${rankLimited}/15 個小樣本子集設計 rank／自由度不足，OLS 可作最小範數點預測，但係數不唯一或不具推論自由度；本曲線不提供 CI／PI。`; $('learning-chart').append(note);}
}

document.querySelectorAll('[data-method]').forEach(b=>b.addEventListener('click',action(()=>selectCandidate(state.caseData.winner_ids[b.dataset.method]))));
$('dataset').addEventListener('change',action(()=>selectScenario($('dataset').value)));
$('variant').addEventListener('change',action(()=>selectScenario($('variant').value)));
$('candidate').addEventListener('change',action(()=>selectCandidate($('candidate').value)));
document.addEventListener('click',action(event=>{const button=event.target.closest('[data-candidate-id]');if(button)return selectCandidate(button.dataset.candidateId);}));
$('restore-representative').addEventListener('click',action(()=>selectCandidate(state.caseData.representative_id)));
$('compare-all').addEventListener('click',()=>{state.compare=!state.compare;renderControls();renderCharts();});
$('coefficient-basis').addEventListener('change',renderCoefficients);$('covariance').addEventListener('change',renderCoefficients);
$('predict-form').addEventListener('submit',event=>{event.preventDefault();calculatePrediction();});$('prediction-inputs').addEventListener('input',calculatePrediction);$('reset-inputs').addEventListener('click',renderPredictor);
$('download-model').addEventListener('click',()=>download(`${state.caseData.id}-${state.card.method}-model.json`,{artifact:state.detail.artifact,inference:state.detail.inference,scope:state.detail.scope}));
$('download-comparison').addEventListener('click',()=>{const columns=['method','candidate','selected_fields','cv_rmse','test_rmse','test_r2'];const records=order.map(m=>{const c=state.caseData.candidates.find(x=>x.id===state.caseData.winner_ids[m]);return [names[m],c.id,c.selected_count,c.cv.rmse,c.test.rmse,c.test.r2];});download(state.caseData.id+'-frozen-comparison.csv',[columns,...records].map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(',')).join('\r\n'),'text/csv;charset=utf-8');});
let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(renderCharts,180);});
json('data/catalog.json').then(c=>{$('build-label').textContent=`Frozen analysis ${c.freeze_sha256.slice(0,12)} · Local preview`;return selectScenario('sgemm');}).catch(report);
