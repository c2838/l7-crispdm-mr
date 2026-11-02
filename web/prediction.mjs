// Portable frozen-model prediction. No training, eval, external dependency or clipping.
export function unscaledCoefficients(artifact) {
  const p=artifact.preprocessor,lookup=new Map(p.columns.map((c,i)=>[c.key,i]));
  let intercept=artifact.model.intercept;
  const coefficients=artifact.selected_keys.map((key,j)=>{
    const i=lookup.get(key),value=artifact.model.coefficients[j]/p.scale[i];
    intercept-=value*p.center[i];return value;
  });
  return {intercept,coefficients};
}
export function predict(artifact,inference,input,forms=[]) {
  const values=new Map(),warnings=[],p=artifact.preprocessor;
  for(const f of p.fields) {
    if(!Object.hasOwn(input,f.field))throw new Error(`Missing input: ${f.field}`);
    let v=input[f.field];const missing=v===null||v===undefined||String(v).trim()==='';
    if(f.kind==='numeric') {
      if(missing){v=f.fill;warnings.push(`${f.field}：缺值使用 training median ${f.fill}。`);}
      else {v=Number(v);if(!Number.isFinite(v))throw new Error(`${f.field} 必須是有限數值。`);}
      values.set(`n:${JSON.stringify(f.field)}`,v);
      const range=forms.find(x=>x.field===f.field);
      if(range&&artifact.selected_raw_fields.includes(f.field)) {
        if(v<range.min||v>range.max)warnings.push(`${f.field}=${v} 超出 training 範圍 [${range.min}, ${range.max}]，屬外推。`);
        if(range.allowed_values&&!range.allowed_values.includes(v))warnings.push(`${f.field}=${v} 不在 training 已觀察的離散設定中。`);
      }
    } else {
      v=missing?f.fill:String(v);
      if(missing)warnings.push(`${f.field}：缺值使用 training mode ${f.fill}。`);
      if(!f.categories.includes(v))warnings.push(`${f.field}=${v} 是未知類別，依凍結規則採 reference「${f.reference}」的效果。`);
      for(const category of f.categories.slice(1))values.set(`c:${JSON.stringify([f.field,category])}`,v===category?1:0);
    }
  }
  const lookup=new Map(p.columns.map((c,i)=>[c.key,i]));
  const z=artifact.selected_keys.map(key=>{const i=lookup.get(key);return (values.get(key)-p.center[i])/p.scale[i];});
  const regression=artifact.model.intercept+z.reduce((sum,x,i)=>sum+x*artifact.model.coefficients[i],0);
  const back=x=>artifact.target_transform==='log'?Math.exp(x):x;
  const result={prediction:artifact.method==='dummy'?artifact.model.intercept:back(regression),warnings};
  if(inference) {
    const x=[1,...z],quadratic=cov=>x.reduce((sum,a,i)=>sum+a*x.reduce((s,b,j)=>s+cov[i][j]*b,0),0);
    const variance=quadratic(inference.covariance_classical),vr=quadratic(inference.covariance_hc3);
    if(variance< -1e-8||vr< -1e-8)throw new Error('Invalid covariance variance.');
    const t=inference.critical_value_95;
    if(!(t>0)&&t!==0)throw new Error('Missing interval critical value.');
    const hm=t*Math.sqrt(Math.max(0,variance)),hp=t*Math.sqrt(Math.max(0,variance)+inference.mse_resid),hr=t*Math.sqrt(Math.max(0,vr));
    Object.assign(result,{location_ci_lower:back(regression-hm),location_ci_upper:back(regression+hm),
      observation_pi_lower:back(regression-hp),observation_pi_upper:back(regression+hp),
      location_ci_hc3_lower:back(regression-hr),location_ci_hc3_upper:back(regression+hr)});
  }
  for(const [key,value] of Object.entries(result))if(key!=='warnings'&&!Number.isFinite(value))throw new Error('數值超出可計算範圍；未裁切預測。');
  return result;
}
