const $ = id => document.getElementById(id);
const state = {data:null, view:'overview', page:0, rows:[], busy:false};
const labels = {overview:'Overview',text:'Text & attributes',entities:'Entity explorer',layers:'Layers',warnings:'Diagnostics'};
const units = {0:'Unitless',1:'Inches',2:'Feet',3:'Miles',4:'Millimeters',5:'Centimeters',6:'Meters',7:'Kilometers',8:'Microinches',9:'Mils',10:'Yards',11:'Angstroms',12:'Nanometers',13:'Microns',14:'Decimeters',15:'Decameters',16:'Hectometers',17:'Gigameters',18:'Astronomical units',19:'Light years',20:'Parsecs',21:'US survey feet',22:'US survey inches',23:'US survey yards',24:'US survey miles'};
const node = (tag, text, cls) => {const e=document.createElement(tag); if(text!==undefined)e.textContent=text; if(cls)e.className=cls; return e;};
const entityText = e => e.text || (e.attributes||[]).map(a=>`${a.tag}: ${a.text}`).join(' · ') || (e.measurement!==undefined ? `Measurement: ${Array.isArray(e.measurement)?e.measurement.join(', '):e.measurement}` : e.block_name || '—');
const allEntities = () => [...state.data.entities,...state.data.blocks.flatMap(b=>b.entities)];
function textRecords(){
  const rows=[]; const seen=new Set();
  for(const e of allEntities()){
    if(e.text!==undefined && !seen.has(`${e.layout}:${e.handle}`)){rows.push(e);seen.add(`${e.layout}:${e.handle}`);}
    for(const a of e.attributes||[]){const key=`${e.layout}:${a.handle}`;if(!seen.has(key)){rows.push({...a,type:'ATTRIB',layer:e.layer,layout:e.layout,block_name:e.block_name,properties:a});seen.add(key);}}
  }
  return rows;
}
async function requestData(url,options){
  if(state.busy)return;
  state.busy=true;$('loading').hidden=false;$('error').hidden=true;$('demo').disabled=true;$('dropzone').setAttribute('aria-busy','true');
  try{const res=await fetch(url,options);const data=await res.json();if(!res.ok)throw new Error(data.error||'Could not process the drawing.');state.data=data;state.page=0;render();}
  catch(error){$('error').textContent=error.message;$('error').hidden=false;}
  finally{state.busy=false;$('loading').hidden=true;$('demo').disabled=false;$('dropzone').setAttribute('aria-busy','false');$('file').value='';}
}
function upload(file){if(!file||state.busy)return;if(!/\.(dwg|dxf)$/i.test(file.name)){showError('Choose a DWG or DXF drawing.');return;}if(file.size>50*1024*1024){showError('This drawing exceeds the 50 MB upload limit.');return;}const body=new FormData();body.append('drawing',file);requestData('/api/extract',{method:'POST',body});}
function showError(message){$('error').textContent=message;$('error').hidden=false;}
function selectView(view){state.view=view;state.page=0;document.querySelectorAll('.nav').forEach(b=>{b.classList.toggle('active',b.dataset.view===view);b.setAttribute('aria-current',b.dataset.view===view?'page':'false');});$('breadcrumb').textContent=labels[view];if(state.data)renderView();}
function fillOptions(id, values, title){const select=$(id);select.replaceChildren(new Option(title,''));for(const value of [...new Set(values)].sort())select.add(new Option(value,value));}
function render(){
  const d=state.data;$('empty').hidden=true;$('results').hidden=false;$('filename').textContent=d.source.filename;$('filemeta').textContent=`${d.source.format.toUpperCase()} / ${units[d.drawing.units_code]||'Unit code '+d.drawing.units_code}`;
  $('upload-title').textContent='Load another drawing';$('upload-description').replaceChildren(node('span','Drop a DWG or DXF here, or browse files'));
  $('stat-entities').textContent=d.summary.entity_count.toLocaleString();$('stat-text').textContent=textRecords().length.toLocaleString();$('stat-layers').textContent=d.layers.length;$('stat-blocks').textContent=d.blocks.length;$('warning-count').textContent=d.warnings.length;
  const entities=[...allEntities(),...textRecords()];fillOptions('layer-filter',[...entities.map(e=>e.layer),...d.layers.map(l=>l.name)],'All layers');fillOptions('layout-filter',entities.map(e=>e.layout),'All layouts');fillOptions('type-filter',entities.map(e=>e.type),'All types');$('search').value='';
  $('breakdown').replaceChildren();const types=Object.entries(d.summary.by_type).sort((a,b)=>b[1]-a[1]);const max=types[0]?.[1]||1;
  for(const [type,count]of types.slice(0,7)){const row=node('div',undefined,'break-row');const title=node('div');title.append(node('span',type),node('b',count.toLocaleString()));const track=node('div',undefined,'bar-track'),bar=node('div',undefined,'bar-fill');bar.style.width=`${count/max*100}%`;track.append(bar);row.append(title,track);$('breakdown').append(row);}
  $('highlights').replaceChildren();const attributes=d.entities.flatMap(e=>(e.attributes||[]).map(a=>({...a,block:e.block_name})));
  for(const a of attributes.slice(0,12)){const card=node('div',undefined,'attribute');card.append(node('small',a.tag),node('b',a.text||'Empty value'),node('p',a.block));$('highlights').append(card);}
  if(!attributes.length)$('highlights').append(node('p','No attached block attributes found. Open Text & attributes to explore drawing text.'));
  $('diagnostics').replaceChildren();for(const warning of d.warnings)$('diagnostics').append(node('div',warning,'diagnostic'));if(!d.warnings.length)$('diagnostics').append(node('p','No extraction warnings were reported.','plain-message'));
  buildScene();renderView();
}
function renderView(){
  $('overview-panel').hidden=state.view!=='overview';$('data-panel').hidden=!['text','entities','layers'].includes(state.view);$('diagnostics-panel').hidden=state.view!=='warnings';
  if(state.view==='overview'){requestAnimationFrame(fitScene);return;}
  if(state.view==='warnings')return;
  $('table-title').textContent=labels[state.view];$('table-description').textContent=state.view==='layers'?'Layer definitions and counts of layout entities.':'Select a row to inspect its properties. Block definitions retain their own local coordinates.';
  for(const id of ['layout-filter','type-filter'])$(id).hidden=state.view==='layers';renderTable();
}
function filteredRows(){
  let rows=state.view==='text'?textRecords():state.view==='layers'?state.data.layers.map(l=>({...l,entity_count:state.data.summary.by_layer[l.name]||0})):allEntities();
  const query=$('search').value.toLowerCase(),layer=$('layer-filter').value,layout=$('layout-filter').value,type=$('type-filter').value;
  return rows.filter(e=>(!layer||(e.layer||e.name)===layer)&&(state.view==='layers'||((!layout||e.layout===layout)&&(!type||e.type===type)))&&(!query||JSON.stringify(e).toLowerCase().includes(query)));
}
function renderTable(){
  const rows=filteredRows();state.rows=rows;state.page=Math.max(0,Math.min(state.page,Math.ceil(rows.length/50)-1));const start=state.page*50,shown=rows.slice(start,start+50);$('row-count').textContent=`${rows.length.toLocaleString()} RESULTS`;
  const columns=state.view==='layers'?['Layer','Entities','Color index','Linetype','Status']:['Type','Text / value','Layer','Layout','Handle'];const header=node('tr');for(const column of columns)header.append(node('th',column));$('table-head').replaceChildren(header);$('table-body').replaceChildren();
  for(const row of shown){const tr=node('tr',undefined,'inspectable');const values=state.view==='layers'?[row.name,row.entity_count,Math.abs(row.color),row.linetype,[row.off?'Off':'On',row.frozen?'Frozen':''].filter(Boolean).join(' · ')]:[row.type,entityText(row),row.layer,row.layout,row.handle];
    values.forEach((value,index)=>{const cell=node('td');cell.append(node(index===0&&state.view!=='layers'?'span':'span',value,index===0&&state.view!=='layers'?'type-badge':undefined));tr.append(cell);});tr.tabIndex=0;tr.addEventListener('click',()=>inspect(row));tr.addEventListener('keydown',event=>{if(event.key==='Enter')inspect(row);});$('table-body').append(tr);
  }
  if(!shown.length){const tr=node('tr'),cell=node('td','No matching results. Try changing your search or filters.','no-data');cell.colSpan=columns.length;tr.append(cell);$('table-body').append(tr);}
  $('page-info').textContent=rows.length?`${start+1}–${Math.min(start+50,rows.length)} of ${rows.length.toLocaleString()}`:'0 results';$('prev').disabled=state.page===0;$('next').disabled=start+50>=rows.length;
}
function inspect(row){$('inspector-title').textContent=row.type?`${row.type} · ${row.handle||'No handle'}`:row.name;$('inspector-body').textContent=JSON.stringify(row,null,2);$('inspector').showModal();}
function download(content,type,extension){const url=URL.createObjectURL(new Blob([content],{type}));const a=node('a');a.href=url;a.download=state.data.source.filename.replace(/\.(dwg|dxf)$/i,'')+extension;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function csvCell(value){let text=String(value??'');if(/^[\s]*[=+@-]/.test(text))text="'"+text;return '"'+text.replaceAll('"','""')+'"';}
function exportCSV(){
  if(!state.data)return;const rows=['text','entities','layers'].includes(state.view)?filteredRows():allEntities();const layerView=state.view==='layers';const headers=layerView?['layer','entity_count','color','linetype','off','frozen']:['type','handle','layer','layout','text','block','attributes','measurement','properties'];
  const records=rows.map(e=>layerView?[e.name,e.entity_count,e.color,e.linetype,e.off,e.frozen]:[e.type,e.handle,e.layer,e.layout,e.text||'',e.block_name||'',JSON.stringify(e.attributes||[]),JSON.stringify(e.measurement??null),JSON.stringify(e.properties||{})]);download('\uFEFF'+[headers,...records].map(r=>r.map(csvCell).join(',')).join('\r\n'),'text/csv;charset=utf-8','.csv');
}
// An explicitly limited 2D overview. No full CAD rendering or block expansion.
const canvas=$('preview'),ctx=canvas.getContext('2d');let shapes=[],bounds=[0,0,1,1],scale=1,offset=[0,0],drag=null;
const finitePoint=p=>Array.isArray(p)&&p.length>=2&&Number.isFinite(p[0])&&Number.isFinite(p[1]);
function buildScene(){
  shapes=[];const points=[];let omitted=0;
  for(const e of state.data.entities.filter(e=>e.layout==='Model')){
    if(shapes.length>=20000){omitted++;continue;}const p=e.properties;let shape;
    const extrusion=p.extrusion||[0,0,1];if(extrusion.some((v,i)=>Math.abs(v-[0,0,1][i])>1e-8)){omitted++;continue;}
    if(e.type==='LINE'&&finitePoint(p.start)&&finitePoint(p.end))shape={kind:'line',points:[p.start,p.end]};
    else if(e.type==='CIRCLE'&&finitePoint(p.center)&&Number.isFinite(p.radius)&&p.radius>0)shape={kind:'circle',center:p.center,r:p.radius};
    else if(e.type==='LWPOLYLINE'&&e.vertices.every(finitePoint)&&e.vertices.every(v=>!v[4]))shape={kind:'poly',points:e.vertices,closed:e.closed};
    if(!shape){omitted++;continue;}shape.layer=e.layer;shapes.push(shape);if(shape.kind==='circle'){points.push([shape.center[0]-shape.r,shape.center[1]-shape.r],[shape.center[0]+shape.r,shape.center[1]+shape.r]);}else for(const point of shape.points)points.push(point);
  }
  let minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;for(const [x,y]of points){minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x);maxY=Math.max(maxY,y);}bounds=points.length?[minX,minY,maxX,maxY]:[0,0,1,1];$('preview-count').textContent=`${shapes.length.toLocaleString()} shapes · ${omitted.toLocaleString()} other entities omitted`;
}
function resizeCanvas(){const rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;canvas.width=Math.max(1,Math.round(rect.width*dpr));canvas.height=Math.max(1,Math.round(rect.height*dpr));ctx.setTransform(dpr,0,0,dpr,0,0);return rect;}
function fitScene(){if(!state.data||state.view!=='overview')return;const rect=resizeCanvas(),[x1,y1,x2,y2]=bounds;scale=Math.min((rect.width-60)/Math.max(x2-x1,1),(rect.height-60)/Math.max(y2-y1,1));offset=[rect.width/2-(x1+x2)/2*scale,rect.height/2+(y1+y2)/2*scale];drawScene();}
function drawScene(){
  const {width,height}=canvas.getBoundingClientRect();ctx.clearRect(0,0,width,height);ctx.strokeStyle='#24424b';ctx.lineWidth=.5;ctx.beginPath();for(let x=0;x<width;x+=22){ctx.moveTo(x,0);ctx.lineTo(x,height);}for(let y=0;y<height;y+=22){ctx.moveTo(0,y);ctx.lineTo(width,y);}ctx.stroke();
  const xy=p=>[p[0]*scale+offset[0],-p[1]*scale+offset[1]];const colors=['#83d7c7','#afc3c5','#edc17c','#8dbbdd'];const layers=[...new Set(shapes.map(s=>s.layer))];ctx.lineWidth=1.6;
  for(const shape of shapes){ctx.strokeStyle=colors[layers.indexOf(shape.layer)%colors.length];ctx.beginPath();if(shape.kind==='circle'){const [x,y]=xy(shape.center);ctx.arc(x,y,shape.r*scale,0,2*Math.PI);}else{shape.points.forEach((p,i)=>{const [x,y]=xy(p);i?ctx.lineTo(x,y):ctx.moveTo(x,y);});if(shape.closed)ctx.closePath();}ctx.stroke();}
  if(!shapes.length){ctx.fillStyle='#a6bdc1';ctx.font='13px Segoe UI';ctx.textAlign='center';ctx.fillText('No supported model-space geometry to preview',width/2,height/2);}
}
canvas.addEventListener('wheel',e=>{e.preventDefault();if(!state.data)return;const rect=canvas.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;const factor=Math.exp(-Math.max(-100,Math.min(100,e.deltaY))*.002);const next=Math.max(1e-9,Math.min(1e9,scale*factor));offset=[x-(x-offset[0])*next/scale,y-(y-offset[1])*next/scale];scale=next;drawScene();},{passive:false});
canvas.addEventListener('pointerdown',e=>{drag=[e.clientX,e.clientY,...offset];canvas.setPointerCapture(e.pointerId);});canvas.addEventListener('pointermove',e=>{if(!drag)return;offset=[drag[2]+e.clientX-drag[0],drag[3]+e.clientY-drag[1]];drawScene();});canvas.addEventListener('pointerup',()=>drag=null);canvas.addEventListener('pointercancel',()=>drag=null);
new ResizeObserver(()=>{if(state.data&&state.view==='overview')fitScene();}).observe(canvas);
$('fit').addEventListener('click',fitScene);document.querySelectorAll('.nav').forEach(b=>b.addEventListener('click',()=>selectView(b.dataset.view)));
$('demo').addEventListener('click',()=>requestData('/api/demo'));$('dropzone').addEventListener('click',()=>{if(!state.busy)$('file').click();});$('dropzone').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();if(!state.busy)$('file').click();}});$('file').addEventListener('change',()=>upload($('file').files[0]));
for(const name of ['dragenter','dragover'])$('dropzone').addEventListener(name,e=>{e.preventDefault();$('dropzone').classList.add('dragover');});for(const name of ['dragleave','drop'])$('dropzone').addEventListener(name,e=>{e.preventDefault();$('dropzone').classList.remove('dragover');});$('dropzone').addEventListener('drop',e=>upload(e.dataTransfer.files[0]));
for(const id of ['search','layer-filter','layout-filter','type-filter'])$(id).addEventListener(id==='search'?'input':'change',()=>{state.page=0;renderTable();});$('prev').addEventListener('click',()=>{state.page--;renderTable();});$('next').addEventListener('click',()=>{state.page++;renderTable();});$('close-inspector').addEventListener('click',()=>$('inspector').close());$('inspector').addEventListener('click',e=>{if(e.target===$('inspector')){const r=$('inspector').getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)$('inspector').close();}});$('json').addEventListener('click',()=>{if(state.data)download(JSON.stringify(state.data,null,2),'application/json','.json');});$('csv').addEventListener('click',exportCSV);
fetch('/api/status').then(r=>r.json()).then(status=>$('converter-status').textContent=status.dwg_available?'DWG + DXF reader ready':'DXF ready · DWG converter needed').catch(()=>$('converter-status').textContent='Server unavailable · restart CAD Studio');
