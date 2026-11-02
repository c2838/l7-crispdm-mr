export const colors={kbest:'#24778b',sfs:'#b57934',rfe:'#7964a4',lasso_select:'#258568',elasticnet_select:'#c06167',ols:'#4b5e70'};
export const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ns='http://www.w3.org/2000/svg';
const compact=x=>Math.abs(x)>=10000?(x/1000).toFixed(0)+'k':Math.abs(x)>=1000?(x/1000).toFixed(1)+'k':Math.abs(x)<.01&&x!==0?x.toExponential(1):Number(x.toPrecision(3)).toString();
function area(host,xvalues,yvalues,xlabel,ylabel,title,{nonnegativeX=false,nonnegativeY=false}={}) {
  const W=Math.max(310,Math.round(host.clientWidth||600)),H=320,L=70,R=18,T=15,B=60;
  const finite=a=>a.filter(Number.isFinite);
  const extent=a=>{a=finite(a);let lo=Math.min(...a),hi=Math.max(...a);if(!a.length)return [0,1];const pad=(hi-lo||Math.max(1,Math.abs(hi)))*.06;return [lo-pad,hi+pad];};
  const xd=extent(xvalues),yd=extent(yvalues);if(nonnegativeX)xd[0]=Math.max(0,xd[0]);if(nonnegativeY)yd[0]=Math.max(0,yd[0]);
  const x=v=>L+(v-xd[0])/(xd[1]-xd[0])*(W-L-R),y=v=>H-B-(v-yd[0])/(yd[1]-yd[0])*(H-T-B);
  host.innerHTML='';const svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox',`0 0 ${W} ${H}`);svg.setAttribute('role','img');svg.setAttribute('aria-label',title);
  let markup=`<title>${esc(title)}</title>`;
  for(let i=0;i<=4;i++) {
    const xv=xd[0]+i*(xd[1]-xd[0])/4,yv=yd[0]+i*(yd[1]-yd[0])/4;
    markup+=`<line class="grid" x1="${L}" y1="${y(yv)}" x2="${W-R}" y2="${y(yv)}"/><text class="tick" text-anchor="end" x="${L-8}" y="${y(yv)+4}">${esc(compact(yv))}</text><text class="tick" text-anchor="middle" x="${x(xv)}" y="${H-B+20}">${esc(compact(xv))}</text>`;
  }
  markup+=`<path class="axis" d="M${L} ${T}V${H-B}H${W-R}" fill="none"/><text class="axis-label" text-anchor="middle" x="${(W+L-R)/2}" y="${H-8}">${esc(xlabel)}</text><text class="axis-label" text-anchor="middle" transform="translate(14 ${(H+T-B)/2}) rotate(-90)">${esc(ylabel)}</text>`;
  svg.innerHTML=markup;host.append(svg);return {svg,x,y,xd,yd};
}
function add(svg,tag,attrs) {const e=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(attrs))e.setAttribute(k,v);svg.append(e);return e;}
function line(c,points,color,dash='') {add(c.svg,'path',{d:points.map((p,i)=>(i?'L':'M')+c.x(p[0])+','+c.y(p[1])).join(' '),fill:'none',stroke:color,'stroke-width':1.6,'stroke-dasharray':dash});}
function legend(host,items){const d=document.createElement('div');d.className='chart-legend';d.innerHTML=items.map(i=>`<span><i style="border-color:${i.color}"></i>${esc(i.label)}</span>`).join('');host.append(d);}
export function empty(host,message){host.innerHTML=`<div class="empty-chart">${esc(message)}</div>`;}
export function curves(host,series,key,unit,selected,onSelect) {
  const points=series.flatMap(s=>s.entries).filter(e=>Number.isFinite(e.cv[key]));if(!points.length)return empty(host,'No eligible CV candidates.');
  const c=area(host,points.map(e=>e.mean_cv_selected_count),points.map(e=>e.cv[key]),'Mean selected fields (CV)',key==='rmse'?`CV RMSE (${unit})`:'CV R-squared',`Development CV ${key} versus mean selected fields`,{nonnegativeX:true,nonnegativeY:key==='rmse'});
  for(const s of series) {
    const entries=s.entries.filter(e=>Number.isFinite(e.cv[key])).slice().sort((a,b)=>a.mean_cv_selected_count-b.mean_cv_selected_count||a.cv[key]-b.cv[key]);
    line(c,entries.map(e=>[e.mean_cv_selected_count,e.cv[key]]),s.color);
    for(const e of entries) {
      const dot=add(c.svg,'circle',{cx:c.x(e.mean_cv_selected_count),cy:c.y(e.cv[key]),r:e.id===selected?6:3.4,fill:s.color,stroke:e.id===selected?'#183c46':'white','stroke-width':e.id===selected?2:1,tabindex:0,role:'button','aria-label':`${e.id}, CV ${key} ${e.cv[key]}`,'data-candidate':e.id,class:'interactive'});
      const title=document.createElementNS(ns,'title');title.textContent=`${e.id} | ${key}=${e.cv[key].toPrecision(6)}`;dot.append(title);
      dot.addEventListener('click',()=>onSelect(e.id));dot.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();onSelect(e.id);}});
    }
  }
  legend(host,series.map(s=>({color:s.color,label:s.label})));
}
export function scatter(host,xs,ys,xlabel,ylabel,title,{diagonal=false,zero=false,highlight=[]}={}) {
  const c=area(host,[...xs,...highlight.map(p=>p[0])],[...ys,...highlight.map(p=>p[1])],xlabel,ylabel,title);
  if(diagonal){const lo=Math.max(c.xd[0],c.yd[0]),hi=Math.min(c.xd[1],c.yd[1]);line(c,[[lo,lo],[hi,hi]],'#9daab1','5 4');}
  if(zero)line(c,[[c.xd[0],0],[c.xd[1],0]],'#9daab1','5 4');
  xs.forEach((v,i)=>add(c.svg,'circle',{cx:c.x(v),cy:c.y(ys[i]),r:2.2,fill:'#2a7183',opacity:.38}));
  highlight.forEach(p=>{const x=c.x(p[0]),y=c.y(p[1]);add(c.svg,'path',{d:`M${x-4} ${y-4}L${x+4} ${y+4}M${x+4} ${y-4}L${x-4} ${y+4}`,stroke:'#b17835','stroke-width':1.5});});
}
export function intervals(host,rows,unit,scope) {
  const order=rows.prediction.map((_,i)=>i).sort((a,b)=>rows.prediction[a]-rows.prediction[b]);
  const xs=order.map((i,j)=>rows.prediction_rank?rows.prediction_rank[i]:j+1),values=[...rows.actual,...rows.prediction,...(rows.observation_pi_lower||[]),...(rows.observation_pi_upper||[])];
  const c=area(host,xs,values,'Prediction-sorted sample rank',`Target (${unit})`,`${scope} point predictions and conditional 95 percent intervals`,{nonnegativeX:true});
  const band=(lower,upper,color)=>{if(!rows[lower])return;const low=order.map((i,j)=>[xs[j],rows[lower][i]]),up=order.slice().reverse().map((i,j)=>[xs[xs.length-1-j],rows[upper][i]]);add(c.svg,'path',{d:[...low,...up].map((p,i)=>(i?'L':'M')+c.x(p[0])+','+c.y(p[1])).join(' ')+'Z',fill:color});};
  band('observation_pi_lower','observation_pi_upper','#d9e8ef');band('location_ci_lower','location_ci_upper','#83b3b9');
  order.forEach((i,j)=>add(c.svg,'circle',{cx:c.x(xs[j]),cy:c.y(rows.actual[i]),r:1.9,fill:'#b17835',opacity:.48}));
  line(c,order.map((i,j)=>[xs[j],rows.prediction[i]]),'#245566');
  legend(host,[{color:'#245566',label:'Point prediction'},{color:'#b17835',label:'Observed target'},...(rows.observation_pi_lower?[{color:'#b9cfdd',label:'95% observation PI'},{color:'#83b3b9',label:'95% location CI'}]:[])]);
}
export function learning(host,rows,unit){const valid=rows.filter(r=>r.mean_training_rows!==null);if(!valid.length)return empty(host,'Learning curve unavailable.');const c=area(host,valid.map(r=>r.mean_training_rows),valid.flatMap(r=>[r.training_rmse,r.validation_rmse]),'Training rows per fold',`RMSE (${unit})`,'Development learning curve, all-feature OLS',{nonnegativeX:true,nonnegativeY:true});for(const [key,color,label] of [['training_rmse','#24778b','Training'],['validation_rmse','#b57934','Validation']]){const pts=valid.map(r=>[r.mean_training_rows,r[key]]);line(c,pts,color);pts.forEach(p=>add(c.svg,'circle',{cx:c.x(p[0]),cy:c.y(p[1]),r:4,fill:color}));}legend(host,[{color:'#24778b',label:'Training RMSE'},{color:'#b57934',label:'Validation RMSE'}]);}
