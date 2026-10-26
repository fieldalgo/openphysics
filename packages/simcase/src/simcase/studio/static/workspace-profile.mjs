// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Intersect a line with the piecewise-constant painted field, without interpolation.
export function lineProfile(field,values,axis,coordinate){
 if(!['x','y'].includes(axis)||!Number.isFinite(coordinate))throw new Error('Invalid profile line.');
 if(!Array.isArray(values)||values.length!==field.triangles.length||!values.every(Number.isFinite))throw new Error('Invalid profile values.');
 const along=axis==='x'?0:1,fixed=1-along,events=[],slices=new Map();
 field.triangles.forEach((triangle,index)=>{
  const points=triangle.map(n=>field.nodes[n]),[a,b,c]=points;
  if((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])===0)return;
  const hits=[];
  for(let edge=0;edge<3;edge++){
   const p=points[edge],q=points[(edge+1)%3];
   if(p[fixed]===coordinate)hits.push(p[along]);
   if((p[fixed]<coordinate&&q[fixed]>coordinate)||(p[fixed]>coordinate&&q[fixed]<coordinate))hits.push(p[along]+(q[along]-p[along])*(coordinate-p[fixed])/(q[fixed]-p[fixed]));
  }
  if(hits.length<2)return;
  const start=Math.min(...hits),end=Math.max(...hits);if(end-start<=1e-12)return;
  slices.set(index,{index,value:values[index],centroid:[(a[0]+b[0]+c[0])/3,(a[1]+b[1]+c[1])/3]});
  events.push({at:start,index,add:true},{at:end,index,add:false});
 });
 events.sort((a,b)=>a.at-b.at);
 const heap=[],active=new Set(),segments=[];
 function push(index){let i=heap.length;heap.push(index);while(i){const p=(i-1)>>1;if(heap[p]>=heap[i])break;[heap[p],heap[i]]=[heap[i],heap[p]];i=p;}}
 function top(){while(heap.length&&!active.has(heap[0])){const tail=heap.pop();if(!heap.length)break;heap[0]=tail;let i=0;for(;;){let child=i*2+1;if(child>=heap.length)break;if(child+1<heap.length&&heap[child+1]>heap[child])child++;if(heap[i]>=heap[child])break;[heap[i],heap[child]]=[heap[child],heap[i]];i=child;}}return heap[0];}
 for(let i=0;i<events.length;){
  const start=events[i].at;let j=i;while(j<events.length&&Math.abs(events[j].at-start)<=1e-12){const e=events[j++];if(e.add){active.add(e.index);push(e.index);}else active.delete(e.index);}
  const index=top(),end=events[j]?.at;
  if(index!==undefined&&end!==undefined&&end-start>1e-12)segments.push({start,end,...slices.get(index)});
  i=j;
 }
 return segments;
}

export function profileCsv(series,axis,coordinate,mode,component){
 const rows=['job,origin,candidate,component,axis,fixed_coordinate_um,start_um,end_um,triangle,centroid_x_um,centroid_y_um,relative_amplitude'];
 for(const item of series)for(const s of item.segments)rows.push([item.run.job,item.run.origin,mode+1,component,axis,coordinate,s.start,s.end,s.index+1,...s.centroid,s.value].join(','));
 return rows.join('\n')+'\n';
}

export function drawProfile(canvas,series,axis,coordinate){
 const box=canvas.getBoundingClientRect(),w=box.width,h=260;if(w<1)return;
 const dpr=Math.min(globalThis.devicePixelRatio||1,2);canvas.width=Math.round(w*dpr);canvas.height=h*dpr;const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.fillStyle='#12202a';ctx.fillRect(0,0,w,h);
 const left=54,top=18,pw=w-left-22,ph=h-top-48,extent=axis==='x'?1.5:1.2;
 const X=x=>left+(x+extent)/(2*extent)*pw,Y=y=>top+(1-y)*ph;
 ctx.strokeStyle='#34414b';ctx.fillStyle='#cfdae0';ctx.font='12px Segoe UI';ctx.textAlign='right';
 for(const value of [0,.5,1]){ctx.beginPath();ctx.moveTo(left,Y(value));ctx.lineTo(left+pw,Y(value));ctx.stroke();ctx.fillText(String(value),left-8,Y(value)+4);}
 ctx.textAlign='center';for(const value of [-extent,0,extent])ctx.fillText(value.toFixed(2),X(value),top+ph+19);ctx.fillText(axis+' [µm]',left+pw/2,h-7);
 ctx.save();ctx.beginPath();ctx.rect(left,top,pw,ph);ctx.clip();
 series.forEach((item,i)=>{ctx.strokeStyle=i?'#e7bc73':'#80d7c0';ctx.lineWidth=2;ctx.beginPath();let previous=null;
  for(const s of item.segments){if(previous&&Math.abs(previous.end-s.start)<1e-11){ctx.lineTo(X(s.start),Y(s.value));}else ctx.moveTo(X(s.start),Y(s.value));ctx.lineTo(X(s.end),Y(s.value));previous=s;}ctx.stroke();
 });ctx.restore();
 canvas.setAttribute('aria-label',`Piecewise-constant line profile along ${axis}, ${axis==='x'?'y':'x'} = ${coordinate} µm. Relative amplitude 0 to 1, no interpolation.`);
}
