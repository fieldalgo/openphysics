// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
export function readMesh(data){
 if(data?.units?.length!=='um')throw new Error('Mesh coordinates must be in micrometres.');
 const {nodes,triangles,regions,region_names:names,stats}=data;
 if(!Array.isArray(nodes)||nodes.length<3||nodes.length>250000||!nodes.every(p=>Array.isArray(p)&&p.length===2&&p.every(Number.isFinite)))throw new Error('Invalid mesh coordinates.');
 if(!Array.isArray(triangles)||!triangles.length||triangles.length>500000||!triangles.every(t=>Array.isArray(t)&&t.length===3&&new Set(t).size===3&&t.every(i=>Number.isInteger(i)&&i>=0&&i<nodes.length)))throw new Error('Invalid mesh triangles.');
 if(!Array.isArray(names)||!names.length||names.length>512||!names.every(n=>typeof n==='string'&&n.length>0&&n.length<=80)||new Set(names).size!==names.length)throw new Error('Invalid mesh regions.');
 const ids=new Set(names.map((_,i)=>i));
 if(!Array.isArray(regions)||regions.length!==triangles.length||!regions.every(r=>ids.has(r)))throw new Error('Invalid mesh region assignments.');
 if(!Number.isFinite(stats?.min_angle)||stats.min_angle<0||stats.min_angle>180||!Number.isFinite(stats?.quality_mean)||stats.quality_mean<0||stats.quality_mean>1)throw new Error('Invalid mesh quality summary.');
 return {nodes:nodes.map(p=>[...p]),triangles:triangles.map(t=>[...t]),regions:[...regions],names:Object.fromEntries(names.map((name,i)=>[name,i])),stats:{nodes:nodes.length,triangles:triangles.length,minAngle:stats.min_angle,meanQuality:stats.quality_mean}};
}
export class MeshPreview {
 constructor(api,onChange=()=>{}){this.api=api;this.onChange=onChange;this.busy=false;this.record=null;this.error='';}
 async generate(input,doc){
  if(this.busy)return;
  const captured=JSON.parse(JSON.stringify(input));this.busy=true;this.error='';this.onChange();
  try{const data=readMesh(await this.api('/api/mesh',{doc}));this.record={input:captured,signature:JSON.stringify(captured),data};}
  catch(error){this.error=error.message;}
  finally{this.busy=false;this.onChange();}
 }
}
export function drawMesh(canvas,mesh,view='Full window',region=[-.65,.65,-.25,.75]){
 const box=canvas.getBoundingClientRect(),w=box.width,h=360;if(w<1)return;
 const ratio=Math.min(globalThis.devicePixelRatio||1,2);canvas.width=Math.round(w*ratio);canvas.height=h*ratio;const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);ctx.fillStyle='#12202a';ctx.fillRect(0,0,w,h);
 const [xmin,xmax,ymin,ymax]=view==='Core region'?region:[-1.5,1.5,-1.2,1.2];
 const scale=Math.min((w-74)/(xmax-xmin),(h-65)/(ymax-ymin)),pw=(xmax-xmin)*scale,ph=(ymax-ymin)*scale,left=54+(w-74-pw)/2,top=20;
 const X=x=>left+(x-xmin)*scale,Y=y=>top+(ymax-y)*scale;
 ctx.save();ctx.beginPath();ctx.rect(left,top,pw,ph);ctx.clip();
 mesh.triangles.forEach((triangle,i)=>{ctx.beginPath();triangle.forEach((n,j)=>{const p=mesh.nodes[n];if(j)ctx.lineTo(X(p[0]),Y(p[1]));else ctx.moveTo(X(p[0]),Y(p[1]));});ctx.closePath();ctx.fillStyle=mesh.regions[i]===mesh.names.background?'#203744':'#3c887d';ctx.fill();ctx.strokeStyle='#8aa6b5';ctx.lineWidth=.4;ctx.stroke();});ctx.restore();
 ctx.strokeStyle='#91a8b7';ctx.strokeRect(left,top,pw,ph);ctx.fillStyle='#cfdae0';ctx.font='12px Segoe UI';ctx.textAlign='center';
 for(let i=0;i<3;i++){const x=xmin+(xmax-xmin)*i/2;ctx.fillText(x.toFixed(2),X(x),top+ph+18);}ctx.fillText('x [µm]',left+pw/2,top+ph+38);ctx.textAlign='right';for(let i=0;i<3;i++){const y=ymin+(ymax-ymin)*i/2;ctx.fillText(y.toFixed(2),left-8,Y(y)+4);}
 ctx.save();ctx.translate(13,top+ph/2);ctx.rotate(-Math.PI/2);ctx.textAlign='center';ctx.fillText('y [µm]',0,0);ctx.restore();
 canvas.setAttribute('aria-label',`Generated mesh: ${mesh.stats.nodes} nodes, ${mesh.stats.triangles} triangles; ${view}, coordinates in micrometres.`);
}
