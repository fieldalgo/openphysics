import {renderConnectionGraph,installConnectionGraph} from './workspace-graph.mjs';
import {LatestWorkspaceLoad} from './workspace-load.mjs';
import {treeOpen,groupHeading,itemAttributes,treeState,bindTree,treeFocus,restoreTreeFocus,resultsGroup} from './workspace-tree.mjs';
import {NotebookAutosave,indexedNotebookStore,readNotebookRecovery,distinctRecords,restorePage} from './workspace-notebook-recovery.mjs';
import {lineProfile,profileCsv,drawProfile} from './workspace-profile.mjs';
import {OpticalPreflight} from './workspace-preflight.mjs';
import {opticalWorkflow,opticalFreshness,opticalSequenceHeading,opticalReadyStatus,inputsDifferText,runInputsLine,opticalInputParts,studyInputParts,runTitle,SAME_INPUTS,nextRunText,numberRuns,droppedRunText,runPlanText,lastComparableRun,groupIndexEstimate,nextDropped,dropWarningText,matchingRunMessage,importNumbersText,inNumberOrder,droppedBy,dropWhileRunningText,droppedAfterText,keepInsteadLabel,keptInsteadText,swapCandidate,swapDropped,pinnedDropText,droppedNoSwapText} from './workspace-workflow.mjs';
import {MeshPreview,drawMesh} from './workspace-mesh.mjs';
import {probeField} from './workspace-probe.mjs';
import {OpticalJobMonitor,readPending,storePending,validatePending} from './workspace-job.mjs';
import {readRecovery,writeRecovery} from './workspace-recovery.mjs';
import {installShapeEditor,SNAP_STEPS} from './workspace-shape-editor.mjs';
import {sectionSvg,MATERIAL_FILL,WINDOW_VIEW,shapesView} from './workspace-section.mjs';
import {SHAPE_MATERIALS,MAX_SHAPES,designSummary,designBounds,newShape,duplicateShape,validateShape,editShapeProperty,fitShapeEdit,validateShapes,validatePolygon,overlappingPairs,shapesBlock,shapeCorners,alignShape,ALIGN_ACTIONS,geometryWords} from './workspace-shapes.mjs';
import {SchematicCamera,installViewport} from './workspace-viewport.mjs';
import {checkWorkspaceCapabilities,connectionFailure,RESTARTED_MESSAGE,UNREACHABLE_MESSAGE,RECONNECTED_MESSAGE,requestFailedText} from './workspace-connection.mjs';
// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

import {INPUT_FIELDS,NumericDrafts,editNoticeText,inputChanges,retryShapeDrafts} from './workspace-inputs.mjs';
import {installLayout,installStatusPanels} from './workspace-layout.mjs';
import {MAX_BYTES,DRAFT_KEY,validateProject,parseProject,snapshot,withStudy,withoutStudy,projectStudy,projectBoundary,STUDY_PROJECT_VERSION,OPEN_PROJECT_VERSION} from './workspace-project.mjs';
import {checkResultRecord,checkDocuments,checkLabel,openChoice,targetText,effectiveTarget,openSettings,isOpenRun,runChoice,signaturePml,parseTarget,openResultValues,pairCheck,checkVerdict,openLoss,openIndexText,openTableTitle,builderBoundary,openEdges,sectionWords,CLOSED_POINTER,OPEN_POLARIZATION_HELP,OPEN_AREA_HELP,keptValues,CHECK_HEADER,CHECK_HELP,CHECK_STRENGTH,DEPENDS_HELP,OPEN_LOSS_HELP,COMPARE_LOSS_NOTE,COMPARE_LOSS_NOTE_BA} from './workspace-open-run.mjs';
import {hasOpenEdge,lowerTarget,defaultTarget} from './workspace-open-boundary.mjs';
import {CLOSED_TARGET_QUERY,checkClosedTarget,closedResultValues,shortcutText,SHORTCUT_MODE_COUNT,closedFoundText,leftOutText,CLOSED_SEARCH_HELP,CLOSED_SEARCH_LEGEND,HIGHEST_LABEL,SHORTCUT_RUN_TEXT,NEAREST_LABEL,NEAR_FIELD_LABEL,closedSearchNotice,shortTarget} from './workspace-closed-target.mjs';
import {boundaryFieldHtml,studyOpenHtml,edgePanel,foundLine,candidatesDisclosure} from './workspace-open-view.mjs';
import {WorkspaceStore} from './workspace-store.mjs';
import {readOpticalField,fieldScalars,nmTicks,formatNm} from './workspace-field.mjs';
import {MAX_SESSION_BYTES,sessionSizeText,fieldsNotKeptText,MODE_COUNT_RANGE,RUN_LIMIT,RUNS_KEPT_TEXT,runsNodeLabel,DEFAULT_MODE_COUNT,opticalSettings,closedTargetSettings,isClosedTargetRun,runSearchTarget,validateRunLabel,runTableCsv,validateRun,appendRun,mergeRuns,createSession,captureSession,parseSession,studySignature,runModeCount,runStampEntry,sessionStudyInput,withPmlCheck,engineRunValues,engineGroupIndex,engineGroupIndexReasons,foundText,writeOpticalSession,opticalOverflowQuestion,sessionText} from './workspace-notebook.mjs';
import {runHeading,fieldHeading,formatIndex,formatPercent,defaultComparison,compareSide,runDesign,comparisonAfterRun,pairChosen,newerThanPair,newestPairOffer} from './workspace-compare.mjs';
import {markPageTabs,installPageTabs} from './workspace-tabs.mjs';
import {RANKING_TEXT,POLARIZATION_HELP,SOURCE_TEXT,AREA_HELP,LOSS_HEADER,ABSORPTION_HELP,modeTableRows,edgeNotes,coreNotes,modeOptionLabel,opticalModes,groupIndexCell,groupIndexHelp,GROUP_INDEX_NOTE,GROUP_INDEX_HINT,OPTICAL_MATERIAL_DATA,GROUP_INDEX_OFF_HELP,groupIndexNotice,hasGroupIndex,edgeSlabRisk,edgeSlabWarningText,edgeSlabShortText,firstModeEdgeShape,noMatchEdgeText} from './workspace-modes.mjs';
import {MATCH_NOTE,COMPARE_MATCH_TEXT,opticalMatch,compareMatchRows,fieldChoices,unitPolarization,unitArea,unitLoss,unitGroupIndex,unitName,formatOverlap,formatDelta,bestOverlapText,MATCH_THRESHOLD,MATCH_MARGIN} from './workspace-match.mjs';
import {sessionFileName,recoveryOffText,modelInProjectTitle,persistenceTitle,persistenceHint,physicsList,untouchedWorkspace,sessionLoadText,leaveConfirmText,opticalRunsStayText,projectTitle,projectHint,projectLeaveText,recoveredProjectName} from './workspace-persistence.mjs';
import {opticalBlock as opticalSupport,opticalDocument as buildOpticalDocument} from './workspace-optical.mjs';
import {solverApi} from './workspace-api.mjs';
import {installProviderList} from './workspace-providers.mjs';
import {renderApplications,templatePhysics,sessionRunNames,sessionLine,cardResumeChoice,cardRecords,APPLICATIONS,pairLine} from './workspace-applications.mjs';
import {SIDES,SIDE_TYPES,DEFAULT_THERMAL,validateThermal,thermalBlock,heatDocument,sideText,thermalSummary} from './workspace-heat.mjs';
import {DEFAULT_JOULE,validateJoule} from './workspace-joule.mjs';
import {createJouleView,JOULE_NODES} from './workspace-joule-view.mjs';
import {createMultiphysicsView} from './workspace-multiphysics-view.mjs';
import {ENVELOPE,matchesAgainText} from './workspace-multiphysics.mjs';
import {checkSessionModels,isModelDocument,multiphysicsLoadText,sizeText} from './workspace-multiphysics-session.mjs';
import {readProject,writeProject,projectEntry,projectFileName,nameFromFile,nameSource,savedProjectName,validateProjectName,isProjectDocument,projectSavedNotice,modelsText,modelParts,MAX_PROJECT_BYTES,PROJECT_FORMAT} from './workspace-project-file.mjs';
import {saveToFile,sanitizeFileName,modelFileName,notWrittenNotice,rememberFile,currentFileFor,suggestedSaveName,downloadAgainNote,fileHoldsText,PROJECT_PICKER_DESCRIPTION} from './workspace-files.mjs';
import {setupMenus} from './workspace-file-menu.mjs';

(()=>{'use strict';const $=id=>document.getElementById(id);
// A reload always opens the start page, so a restored scroll position would hide its top.
if('scrollRestoration' in history)history.scrollRestoration='manual';
const ui={page:'Applications',selection:'Geometry',view:'Perspective',body:'Core',shape:0,snap:5,reference:null};const state={height:220,width:500,wavelength:1550,coreMesh:30,modeCount:DEFAULT_MODE_COUNT,groupIndex:false,openBoundary:null,searchTarget:null,shapes:[{name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220}],thermal:validateThermal(DEFAULT_THERMAL),joule:validateJoule(DEFAULT_JOULE),voltage:1,heat:true,structure:true,optics:true};const setup={materials:{Core:'Silicon',Oxide:'Silica',Heater:''},cooling:'',temperature:293.15,fixed:'',terminal:''};const pick={mode:'Bodies',boundary:null};const names=['Geometry','Materials','Electric currents','Heat transfer','Solid mechanics','Optical modes','Couplings','Mesh','Study'];
const cameras={Perspective:new SchematicCamera(),Section:new SchematicCamera(),Optical:new SchematicCamera()};cameras.Optical.fitTo(WINDOW_VIEW);
let refreshViewport=null;let disposeWidthEditor=()=>{};
const numericDrafts=new NumericDrafts();
const connection={ready:false,message:'Checking Studio compatibility…',version:null,instance:null};
const pair=(a,b)=>`<div class="pair"><span>${a}</span><strong>${b}</strong></div>`;
function select(name){pick.boundary=null;ui.selection=name;ui.page=name==='Couplings'||(ui.page==='Connections'&&['Electric currents','Heat transfer','Solid mechanics','Optical modes'].includes(name))?'Connections':'Model';render();}

const isOptical=()=>state.electric===false&&!state.heat&&!state.structure&&state.optics;
const isHeat=()=>state.electric===false&&state.heat&&!state.structure&&!state.optics;
// Electric currents and heat alone: the Joule heating application (workspace-joule-view.mjs).
const isJoule=()=>state.electric!==false&&state.heat&&!state.structure&&!state.optics;
function setShape(index,shape){state.shapes=state.shapes.map((s,i)=>i===index?shape:s);}
// Physics › Optical modes on the Model page, with its wavelength field focused (Study and the step bar).
function editWavelengthField(){ui.page='Model';select('Optical modes');const field=$('wavelength-number');if(field){field.focus({preventScroll:true});(field.closest('label')||field).scrollIntoView({block:'nearest'});field.select();}}
function selectedShape(){ui.shape=Math.min(Math.max(0,ui.shape|0),state.shapes.length-1);return state.shapes[ui.shape];}
function bindWidthEditor(){disposeWidthEditor();disposeWidthEditor=()=>{};if(ui.page==='Model'&&ui.selection==='Geometry'&&isOptical()&&pick.mode==='Bodies')disposeWidthEditor=installShapeEditor($('canvas'),{shape:selectedShape(),index:ui.shape,snap:ui.snap,blocked:()=>numericDrafts.invalid,commit:(shape,label)=>{edits.endGroup();setShape(ui.shape,shape);trackEdit();edits.endGroup();render();notice(label+'. Run explicitly to compute new results.');}});}
function geom(){
if(isHeat())return heatSvg();
if(isJoule())return jouleView.svg();
if(isOptical())return sectionSvg(state.shapes,{selected:ui.shape,selectedEdge:pick.boundary,mode:pick.mode,openEdges:openEdges(state.openBoundary)});
const w=state.width/500;
const attrs=body=>`data-pick-body="${body}" role="button" tabindex="0" aria-label="Select ${body} body" stroke="${ui.body===body?'#2860bd':'#7a939f'}" stroke-width="${ui.body===body?3:1}"`;
const edge=(id,path,label)=>`<g data-pick-edge="${id}" role="button" tabindex="0" aria-label="Select ${label}">${path==='M65 260 H535'?'<rect x="65" y="250" width="470" height="20" fill="transparent"/>':''}<path d="${path}" fill="none" stroke="transparent" stroke-width="20"/><path d="${path}" fill="none" stroke="${pick.boundary===id?'#2860bd':'#b5c9d3'}" stroke-width="${pick.boundary===id?5:2}" pointer-events="none"/></g>`;
const section=ui.view==='Section';
const shapes=section?`<rect x="65" y="80" width="470" height="180" fill="#dde7f1" ${attrs('Oxide')}/><rect x="${300-65*w}" y="150" width="${130*w}" height="55" fill="#6d9fe0" ${attrs('Core')}/><rect x="220" y="100" width="160" height="16" fill="#a66a28" ${attrs('Heater')}/><text x="300" y="50" text-anchor="middle" fill="#34445b">Cross section · ${pick.mode==='Bodies'?'select a body':'select a boundary'}</text><text x="300" y="300" text-anchor="middle" fill="#5b6d82">Core width ${state.width} nm · schematic</text>`:`<polygon points="65,160 365,65 550,165 250,275" fill="#dce5ee" ${attrs('Oxide')}/><polygon points="65,160 250,275 250,300 65,185" fill="#a3b4c9" ${attrs('Oxide')}/><polygon points="250,275 550,165 550,190 250,300" fill="#bdcbdc" ${attrs('Oxide')}/><path d="M135 163 L421 77 L446 92 L160 180 Z" fill="#6d9fe0" ${attrs('Core')}/><path d="M155 143 L410 68 L425 76 L170 152 Z" fill="#a66a28" ${attrs('Heater')}/><text x="390" y="45" fill="#a66a28">Heater end</text><text x="65" y="135" fill="#a66a28">Heater start</text><text x="67" y="325" fill="#5b6d82">Named boundaries · schematic, not CAD faces</text>`;
let edges='';if(pick.mode==='Boundaries')edges=section?edge('oxide-bottom','M65 260 H535','oxide bottom boundary'):edge('heater-start','M155 143 L170 152','heater start terminal')+edge('heater-end','M410 68 L425 76','heater end ground')+edge('left-end','M65 160 L250 275','left end support')+edge('right-end','M365 65 L550 165','right end support')+edge('oxide-bottom','M65 185 L250 300 L550 190','oxide bottom boundary');
return `<svg viewBox="0 0 600 350" role="group" aria-label="Selectable schematic geometry">${shapes}${edges}</svg>`;
}
function bindPicking(){
const bind=(el,fn)=>{el.onclick=fn;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();fn();}};};
$('canvas').querySelectorAll('[data-pick-body]').forEach(el=>{if(pick.mode!=='Bodies'){el.removeAttribute('tabindex');el.setAttribute('role','img');el.onclick=null;return;}bind(el,()=>{ui.body=el.dataset.pickBody;pick.boundary=null;ui.selection='Materials';render();});});
$('canvas').querySelectorAll('[data-pick-shape]').forEach(el=>{if(pick.mode!=='Bodies')return;bind(el,()=>chooseShape(+el.dataset.pickShape));});
$('canvas').querySelectorAll('[data-pick-edge]').forEach(el=>bind(el,()=>{pick.boundary=el.dataset.pickEdge;ui.selection=pick.boundary.startsWith('optical-')?'Optical modes':pick.boundary.startsWith('heater')?'Electric currents':pick.boundary==='oxide-bottom'?'Heat transfer':'Solid mechanics';render();}));
}
function chooseShape(index){if(index!==ui.shape&&numericDrafts.shapeInvalid){notice('Correct or restore the selected shape values before choosing another shape.');return;}ui.shape=index;pick.boundary=null;ui.selection='Geometry';ui.page='Model';render();}
function pickingPanel(){
if(ui.page!=='Model'||!$('canvas').querySelector('svg'))return;
const bar=document.createElement('div');bar.className='toolbar';bar.innerHTML=['Bodies','Boundaries'].map(v=>`<button data-pick-mode="${v}" aria-pressed="${pick.mode===v}">${v}</button>`).join('')+'<span>Click geometry or use Tab + Enter</span>';$('canvas').prepend(bar);
bar.querySelectorAll('[data-pick-mode]').forEach(el=>el.onclick=()=>{pick.mode=el.dataset.pickMode;pick.boundary=null;render();});
const hint=document.createElement('p');hint.className='muted';hint.textContent=pick.mode==='Bodies'?(isOptical()?`Selected shape: ${selectedShape().name}`:`Selected body: ${ui.body}`):isOptical()?(state.openBoundary?'Optical window: select an edge to close or open it (Open boundary is chosen in Physics › Optical modes).':'Optical window: select one of four fixed PEC edges.'):ui.view==='Section'?'Cross section: oxide bottom. Switch to Perspective for longitudinal ends.':'Select a highlighted boundary to assign its condition.';$('canvas').append(hint);
bindPicking();
if(pick.mode==='Boundaries'&&pick.boundary){
const info=document.createElement('section');info.className='boundary-selection';
if(pick.boundary.startsWith('optical-')&&state.openBoundary){const side=pick.boundary.slice(8),panel=edgePanel(side,state.openBoundary);panel.querySelector('#close-edge').onchange=e=>{const closed=e.target.checked;state.openBoundary={...state.openBoundary,edges:{...state.openBoundary.edges,[side]:closed?'closed':'open'}};render();notice(`Optical ${side} edge ${closed?'closed (PEC)':'open (PML 1 µm)'}. Run explicitly to compute new results.`);};$('inspector').prepend(panel);return;}
if(pick.boundary.startsWith('optical-')){const heading=document.createElement('h3');heading.textContent='Optical '+pick.boundary.slice(8)+' boundary';const note=document.createElement('p');note.textContent='PEC · fixed by the optical adapter. This edge is not a thermal boundary or a mechanical support.';info.append(heading,note);$('inspector').prepend(info);return;}
const id=pick.boundary;const labels={'heater-start':'Heater start','heater-end':'Heater end','oxide-bottom':'Oxide bottom','left-end':'Left end','right-end':'Right end'};
info.innerHTML=`<h3>Selected boundary: ${labels[id]}</h3>`;
let text,action;
if(id.startsWith('heater')){text='Assign start = terminal / end = ground';action=()=>setup.terminal='Heater start / heater end';}
else if(id==='oxide-bottom'){text='Assign fixed temperature to bottom';action=()=>setup.cooling='Oxide bottom: fixed temperature';}
else if(id==='left-end'){text='Fix left end';action=()=>setup.fixed='Left end fixed';}
else {text='Fix both ends (left + right)';action=()=>setup.fixed='Both ends fixed';}
const button=document.createElement('button');button.textContent=text;button.id='assign-boundary';button.onclick=()=>{action();render();refreshPersistence();notice('Boundary assignment updated. Named regions only; CAD mapping pending.');};info.append(button);$('inspector').prepend(info);
}
}
function active(){return ['Electric currents',...(state.heat?['Heat transfer']:[]),...(state.heat&&state.structure?['Solid mechanics']:[]),...(state.optics?['Optical modes']:[])];}

// ---- Steady heat plate: a form over the public thermal.steady2d routes (thermal.js controller). ----
const HEAT_NODES=['Geometry','Materials','Heat transfer','Mesh','Study'];
const heatDrafts=new Map();let heatSide='left',heatField='temperature',heatArrows=true,heatRun=null,heatState={supported:false,busy:false,error:null,result:null},heatProbe=null,heatResize=null;
async function studioRequest(method,url,body){const response=await fetch(url,method==='GET'?undefined:{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let reply;try{reply=await response.json();}catch{throw new Error('Use the Studio server for heat and Joule calculations. Response is not JSON.');}if(!response.ok)throw new Error(reply.error?.message||reply.detail||('HTTP '+response.status));return reply;}
const heatController=globalThis.ThermalStudio?.createController({
 request:studioRequest,
 onState:next=>{heatState=next;refreshHeatControls();jouleView.refreshControls();},
 onResult:payload=>{heatRun={input:JSON.parse(JSON.stringify(heatCapture)),signature:JSON.stringify(heatCapture),payload,completedAt:new Date().toISOString()};heatProbe=null;ui.page='Results';render();announceResult('Heat calculation complete. The result keeps the inputs it was run with; it is kept in this tab only.');}
})||null;
let heatCapture=null;
const heatLimits=()=>heatController?.state().cap?.limits||null;
const heatSignature=()=>JSON.stringify(state.thermal);
function heatBlock(){if(!heatController)return 'Heat calculation needs the Studio page script; reload the workspace.';if(jouleView.busy())return 'A Joule heating job holds the server job slot; wait for it to finish.';if(!heatController.state().cap)return 'Heat calculation is unavailable from this server.';if(heatController.state().cap.run_enabled!==true)return 'This server does not enable heat runs.';if(heatDrafts.size)return 'Correct or restore the highlighted heat inputs before running.';return thermalBlock(state.thermal,heatLimits());}
function setThermal(next,message){
 let checked;try{checked=validateThermal(next);}catch(error){notice(error.message);return false;}
 state.thermal=checked;heatController?.invalidate();edits.endGroup();trackEdit();edits.endGroup();render();notice(message+' Run explicitly to compute new results.');return true;
}
const heatValue=path=>path.split('.').reduce((o,k)=>o?.[k],state.thermal);
function heatInput(path,label,attrs=''){const draft=heatDrafts.get(path);return `<label>${label}<input data-heat="${path}" type="number" step="any" ${attrs} value="${escapeHtml(draft?draft.raw:heatValue(path))}" aria-invalid="${!!draft}"></label>${draft?`<p class="input-hint" role="alert">${escapeHtml(draft.message)} Last valid value is retained.</p>`:''}`;}
function heatSideForm(side){
 const c=state.thermal.sides[side];
 const fields=c.type==='temperature'?heatInput(`sides.${side}.temperature`,'Temperature [K]','min="0"'):c.type==='flux'?heatInput(`sides.${side}.inward_heat_flux`,'Inward heat flux [W/m²] (positive enters the plate)'):c.type==='convection'?heatInput(`sides.${side}.h`,'Heat transfer coefficient h [W/(m²·K)]','min="0"')+heatInput(`sides.${side}.ambient`,'Ambient temperature [K]','min="0"'):'';
 return `<fieldset class="heat-side" data-side-box="${side}"><legend>${side[0].toUpperCase()+side.slice(1)} side</legend><label>Condition<select data-heat-type="${side}">${Object.entries(SIDE_TYPES).map(([k,v])=>`<option value="${k}" ${k===c.type?'selected':''}>${v}</option>`).join('')}</select></label>${fields}</fieldset>`;
}
function heatInspector(){
 const t=state.thermal,limits=heatLimits(),block=thermalBlock(t,limits);let html='<span class="muted">SELECTION</span><h2>'+ui.selection+'</h2>';
 if(ui.selection==='Geometry')html+=heatInput('width','Plate width [mm]','min="0.001"')+heatInput('height','Plate height [mm]','min="0.001"')+pair('Origin','Lower-left corner at (0, 0)')+'<p>One homogeneous rectangle. Select a side in the drawing to edit its condition.</p>';
 else if(ui.selection==='Materials')html+=heatInput('conductivity','Thermal conductivity k [W/(m·K)]','min="0"')+heatInput('source','Uniform heat source Q [W/m³]')+'<p>Constant isotropic k and source over the whole plate. Temperature-dependent or region-wise properties are not available in this application.</p>';
 else if(ui.selection==='Heat transfer')html+=SIDES.map(heatSideForm).join('')+'<p>At least one fixed temperature or convection with h > 0 sets the temperature level. Adjacent fixed sides must agree at their corner.</p>';
 else if(ui.selection==='Mesh')html+=heatInput('nx','Divisions along x','min="1" step="1"')+heatInput('ny','Divisions along y','min="1" step="1"')+pair('Nodes',`${(t.nx+1)*(t.ny+1)}${limits?' of '+limits.max_nodes:''}`)+pair('Triangles',`${2*t.nx*t.ny}${limits?' of '+limits.max_triangles:''}`)+'<p>Structured P1 triangles. The actual mesh is shown with the result; there is no separate preview.</p>';
 else html+=pair('Plate',escapeHtml(thermalSummary(t)))+SIDES.map(side=>pair(side,escapeHtml(sideText(t.sides[side])))).join('')+pair('Mesh',`${t.nx} × ${t.ny} divisions`);
 if(block)html+=`<p class="validation-warning">${escapeHtml(block)}</p>`;
 if(heatDrafts.size)html+='<button id="discard-heat-drafts">Restore last valid values</button>';
 return html+'<p class="muted">Editing this design does not run a simulation.</p>';
}
function bindHeatPanel(){
 document.querySelectorAll('[data-heat]').forEach(el=>el.onchange=()=>{
  const path=el.dataset.heat,raw=el.value.trim(),value=Number(raw),keys=path.split('.');
  const next=JSON.parse(JSON.stringify(state.thermal));let target=next;for(const k of keys.slice(0,-1))target=target[k];target[keys.at(-1)]=raw===''?NaN:value;
  try{validateThermal(next);}catch(error){heatDrafts.set(path,{raw:el.value,message:error.message});render();return;}
  heatDrafts.delete(path);setThermal(next,'Heat input updated.');
 });
 document.querySelectorAll('[data-heat-type]').forEach(el=>el.onchange=()=>{
  const side=el.dataset.heatType,type=el.value,defaults={insulated:{type},temperature:{type,temperature:300},flux:{type,inward_heat_flux:0},convection:{type,h:10,ambient:295}};
  for(const key of [...heatDrafts.keys()])if(key.startsWith(`sides.${side}.`))heatDrafts.delete(key);
  setThermal({...state.thermal,sides:{...state.thermal.sides,[side]:defaults[type]}},`${side[0].toUpperCase()+side.slice(1)} side: ${SIDE_TYPES[type].toLowerCase()}.`);
 });
 const discard=$('discard-heat-drafts');if(discard)discard.onclick=()=>{heatDrafts.clear();render();notice('Invalid heat drafts discarded. Last valid inputs retained.');};
}
function heatSvg(){
 const t=state.thermal,scale=Math.min(440/t.width,230/t.height),w=t.width*scale,h=t.height*scale,x0=300-w/2,y0=175-h/2;
 const edges={left:[x0,y0+h,x0,y0],right:[x0+w,y0+h,x0+w,y0],bottom:[x0,y0+h,x0+w,y0+h],top:[x0,y0,x0+w,y0]};
 const labels={left:[x0-8,175,'end'],right:[x0+w+8,175,'start'],bottom:[300,y0+h+16,'middle'],top:[300,y0-8,'middle']};
 let grid='';if(ui.selection==='Mesh'){const sx=Math.max(1,Math.ceil(t.nx/60)),sy=Math.max(1,Math.ceil(t.ny/60));for(let i=1;i<t.nx;i+=sx)grid+=`<path d="M${x0+w*i/t.nx} ${y0} V${y0+h}"/>`;for(let j=1;j<t.ny;j+=sy)grid+=`<path d="M${x0} ${y0+h*j/t.ny} H${x0+w}"/>`;}
 const sides=SIDES.map(side=>{const [a,b,c,d]=edges[side],on=ui.selection==='Heat transfer'&&heatSide===side,[lx,ly,anchor]=labels[side];return `<g data-heat-side="${side}" role="button" tabindex="0" aria-label="Select ${side} side: ${escapeHtml(sideText(t.sides[side]))}"><path d="M${a} ${b} L${c} ${d}" stroke="transparent" stroke-width="14"/><path d="M${a} ${b} L${c} ${d}" stroke="${on?'#2860bd':t.sides[side].type==='insulated'?'#7a939f':'#b9772c'}" stroke-width="${on?4:2.5}" ${t.sides[side].type==='insulated'?'stroke-dasharray="5 4"':''} pointer-events="none"/><text x="${lx}" y="${ly}" text-anchor="${anchor}" fill="#34445b" font-size="10" pointer-events="none">${escapeHtml(sideText(t.sides[side]))}</text></g>`;}).join('');
 return `<svg data-geometry-view="heat" viewBox="0 0 600 350" role="group" aria-label="Heat plate, ${escapeHtml(thermalSummary(t))}"><rect x="${x0}" y="${y0}" width="${w}" height="${h}" fill="#f1d5b5" stroke="none"/><g stroke="#e2c9a6" stroke-opacity=".35" stroke-width=".6">${grid}</g>${sides}<text x="300" y="22" text-anchor="middle" fill="#34445b" font-size="11">${escapeHtml(thermalSummary(t))} · ${t.nx} × ${t.ny} divisions</text><text x="${x0}" y="${y0+h+30}" fill="#5b6d82" font-size="10">(0, 0)</text><text x="${x0+w}" y="${y0-20}" text-anchor="end" fill="#5b6d82" font-size="10">(${t.width}, ${t.height}) mm</text></svg>`;
}
function bindHeatSides(){document.querySelectorAll('[data-heat-side]').forEach(el=>{const choose=()=>{heatSide=el.dataset.heatSide;ui.selection='Heat transfer';render();document.querySelector(`[data-side-box="${heatSide}"] select`)?.focus();};el.onclick=choose;el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();choose();}};});}
// Joule heating: names used before their declaration are wrapped, so creating the view reads none of them.
function setJoule(next,message){
 let checked;try{checked=validateJoule(next);}catch(error){notice(error.message);return false;}
 state.joule=checked;edits.endGroup();trackEdit();edits.endGroup();render();notice(message+' Run explicitly to compute new results.');return true;
}
const jouleView=createJouleView({$,pair,ui,escapeHtml:text=>escapeHtml(text),notice:text=>notice(text),announceResult:text=>announceResult(text),getJoule:()=>state.joule,commit:setJoule,render:()=>render(),
 request:studioRequest,active:()=>isJoule(),otherBusy:()=>heatState.busy,onIdle:()=>refreshHeatControls(),beforeRun:()=>edits.record(inputsFile())});
// A multiphysics model (contract D2) keeps its document in its own view; the other applications
// do not see it. Names used before their declaration are wrapped.
const multiView=createMultiphysicsView({$,ui,notice:(text,more,action)=>notice(text,more,action),announceResult:(text,action)=>announceResult(text,action),request:studioRequest,render:()=>render(),
 // a raw body: the server's reader sees a file's text as written (duplicate keys, digits)
 requestRaw:async(url,body)=>{const response=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body});try{return await response.json();}catch{throw new Error('Use the Studio server to open model files. Response is not JSON.');}},
 // physics selections no application claims, so no single-physics view acts while it is open
 // the workspace's own physics selection is kept while the multiphysics model is shown, so its
 // project entry and its return keep it (P3)
 onOpen:()=>{fileScope++;if(!mpFlags){workspacePhysics=applicationChosen()?physicsOf(state):null;mpFlags=true;}Object.assign(state,{electric:true,heat:true,structure:true,optics:true});projectId('multiphysics');},
 onHistory:()=>{updateHistory();refreshPersistence();},download:(blob,name)=>downloadFile(blob,name),deliverSession:(text,name,options)=>deliverSession(text,name,options),serverVersion:()=>connection.version,validateRunLabel,
 // the optical runs this tab holds beside the multiphysics model (the save message names them)
 opticalRunCount:()=>runs.length,
 // the Library's view title row names the project (P3)
 projectLine:()=>projectLine(),
 // the model's current file name (File › Save downloads under it again), which the header names
 currentFileName:()=>currentFileNow()?.name||null,currentFileHow:()=>currentFileNow()?.how||null,
 // the browser copy, in the indicator's words: kept:N when recovery left out the maps of N runs
 recoveryState:()=>recoveryState==='kept'&&multiView.recoveryDropped()?'kept:'+multiView.recoveryDropped():recoveryState,applications:host=>{renderApplications(host,resumeOffer(),cardResumeOffers(),libraryOptions());host.querySelectorAll('[data-template]').forEach(b=>b.onclick=()=>chooseTemplate(b.dataset.template));}});
// Leaving a multiphysics model for a single-physics one (a card, an opened file, recovery,
// Reset): refused while its run is going; false when refused.
function leaveMultiphysics(){
 if(!multiView.active())return true;
 if(multiView.busy()){notice('Wait for the multiphysics run to finish, or stop it under Study.');return false;}
 fileScope++;multiView.close();multiView.leave();restoreWorkspacePhysics();return true;
}
// ---- The project (P3, workspace-project-file.mjs): every model of this tab in one file ----
// The workspace (optical, heat or Joule heating inputs with the optical runs) is in the project once
// one of its cards was chosen or a workspace file opened; the multiphysics model once one was opened.
// While the multiphysics model is shown, state holds the all-physics placeholder (mpFlags) and
// workspacePhysics the workspace's own selection (null: none chosen).
const PHYSICS_KEYS=['electric','heat','structure','optics'];
const physicsOf=from=>Object.fromEntries(PHYSICS_KEYS.map(k=>[k,from[k]]));
const INITIAL_PHYSICS=physicsOf(state);
let workspacePhysics=null,mpFlags=false;
function restoreWorkspacePhysics(){if(!mpFlags)return;mpFlags=false;Object.assign(state,workspacePhysics||INITIAL_PHYSICS);workspacePhysics=null;}
const workspaceInProject=()=>mpFlags?workspacePhysics!==null:applicationChosen();
const workspacePhysicsNow=()=>mpFlags?workspacePhysics||INITIAL_PHYSICS:physicsOf(state);
// the workspace's inputs file (with its study settings), whichever model is shown
const workspaceInputs=()=>mpFlags&&workspacePhysics?withStudy(snapshot({...state,...workspacePhysics},setup),{modeCount:state.modeCount,groupIndex:state.groupIndex,openBoundary:state.openBoundary}):inputsFile();
const workspaceCard=()=>{const p=workspacePhysicsNow();return APPLICATIONS.find(a=>PHYSICS_KEYS.every(k=>a.physics[k]===!!p[k]))?.id||null;};
const workspaceTitle=()=>({optical:'Optical waveguide',heat:'Steady heat conduction',joule:'Joule heating'})[workspaceCard()]||'Multiphysics workspace';
// name: null for an untitled project; ids: the id of each model (m1, m2, ... in the order they
// joined, kept from an opened project); file: the project file (workspace-files.mjs rememberFile,
// with savedAt); stamp: what the project held when it was saved or opened (projectStamp); scope:
// moves on when a file replaces the project, so a save under way never names the new one
// nameFrom: 'file' for a name taken from a file name, which follows Save As; 'user' for a name
// set with Rename, which stays (round 16); null for an untitled project
// copyOf (round 19, Y3): the file a browser-restored record was opened from, when the record names
// no project file; the header names it instead of a guessed project name
// recovered: the project name came back from a browser-recovery record's `project` (no project
// file): {opened: the file the record still matched, or null; savedAt: that record's time; stamp:
// the project then}. The header says so until the next change (projectStamp differs).
const project={name:null,nameFrom:null,ids:{},next:1,file:null,stamp:null,scope:0,copyOf:null,recovered:null,fromFile:null};
// the page and run the workspace was last shown on (round 16, S9; rememberReturn)
let workspaceReturn=null;
function projectId(kind){if(!project.ids[kind])project.ids[kind]='m'+project.next++;return project.ids[kind];}
// a file replaced the project: an untitled project of the models now in the tab
function resetProject({name=null,ids=null,nameFrom=null}={}){
 Object.assign(project,{name,nameFrom:name?nameFrom||'user':null,ids:{},next:1,file:null,fromFile:null,stamp:null,scope:project.scope+1,copyOf:null,recovered:null});
 if(ids){project.ids={...ids};project.next=Math.max(0,...Object.values(ids).map(id=>+id.slice(1)))+1;}
}
// The models a project file holds, as Save compares them (round 17, U8): [{key, title}], keyed by the
// model's id in the project (m1, m2, …), which an edit or Reset design does not change
const modelList=()=>projectModels().map(m=>({key:m.id,title:m.title}));
const modelsChanged=file=>Array.isArray(file?.models)&&JSON.stringify(file.models.map(m=>m.key))!==JSON.stringify(modelList().map(m=>m.key));
// The models a project file will hold, each with its runs (round 18, X5): optical and multiphysics
// runs are written; heat and Joule heating results are not, so those models read "(no runs)".
const projectHoldsText=()=>fileHoldsText(projectModels().map(m=>({title:m.title,runs:m.kind==='multiphysics'?multiView.projectRuns():workspaceCard()==='optical'?runs.length:0})));
function modelsChangedText(file,name){
 const titles=list=>list.length?list.map(m=>m.title).join(' and '):'no model';
 return `This project now holds ${titles(modelList())}; ${name} holds ${titles(file.models)}. Save under this name or another.`;
}
// The models of the project, in Library order: {id, kind, title, card}
function projectModels(){
 const list=[];
 if(workspaceInProject())list.push({id:projectId('workspace'),kind:'workspace',title:workspaceTitle(),card:workspaceCard()});
 if(multiView.inProject())list.push({id:projectId('multiphysics'),kind:'multiphysics',title:multiView.projectTitle(),card:multiView.card()});
 return list;
}
// What "changed" counts: the project name and every model's inputs, study settings, runs, names,
// pins and comparison (multiphysics: its document, runs and without-heater results); not the view
// or the selected run.
const projectContent=()=>JSON.stringify([workspaceInProject()?{input:workspaceInputs(),runs:runs.map(r=>[r.job,r.completedAt,r.label||'',r.pinned===true]),comparison:compareIds}:null,multiView.inProject()?multiView.contentStamp():null]);
const projectStamp=(name=project.name,content=projectContent())=>JSON.stringify([name,content]);
// The models whose runs no file holds (the leave question names them)
function unsavedModels(){
 const list=[];
 if(workspaceInProject()&&runs.length&&savedRunsState!==runsStamp())list.push({title:workspaceTitle(),runs:runs.length});
 if(multiView.projectUnsavedRuns())list.push({title:multiView.projectTitle(),runs:multiView.projectUnsavedRuns()});
 return list;
}
function projectLine(){
 const file=project.file&&project.file.scope===project.scope?project.file:null;
 const recovered=!file&&project.recovered&&project.recovered.stamp===projectStamp()?{opened:project.recovered.opened,changed:project.recovered.changed??null}:null;
 return projectTitle({name:project.name,fromFile:project.fromFile,models:projectModels().length,file,current:!!file&&project.stamp===projectStamp(),recovery:opticalRecoveryShown(),copyOf:project.copyOf,recovered});
}
// The workspace leaves the project (a multiphysics file replaced it): no runs, the inputs a new tab
// starts with and no application chosen.
function clearWorkspace(){
 runs=[];runNumbersUsed=0;solverRun=null;compareIds=[null,null];comparePicked=false;workspaceReturn=null;lastSavedFile=null;loadedSession=null;savedRunsState=null;savedNotebookState=null;openedFile=null;openedStamp=null;newModelInputs=null;heatRun=null;
 const shown=multiView.active(),page=ui.page;
 applyProject(DEFAULT_INPUTS,{saved:true,resetHistory:true,quiet:true});
 if(shown){workspacePhysics=null;ui.page=page;}else Object.assign(state,INITIAL_PHYSICS);
}
// Before leaving a model whose runs only this tab holds (another model, an opened file, a
// recovered session): a confirmation that names what is lost and offers the save that fits.
// toMultiphysics: the target is a multiphysics model (optical runs then go out of sight).
const leaveDialog=document.createElement('dialog');leaveDialog.id='leave-confirm';leaveDialog.setAttribute('aria-labelledby','leave-confirm-title');leaveDialog.setAttribute('aria-describedby','leave-confirm-description');
leaveDialog.innerHTML='<h2 id="leave-confirm-title"></h2><p id="leave-confirm-description"></p><div class="leave-actions"><button id="leave-stay"></button> <button id="leave-save"></button> <button id="leave-go"></button></div>';
document.body.append(leaveDialog);
let pendingLeave=null;
// A file replaces the project (P3): the question names the models whose runs no file holds.
// model: a browser restore replaces one model only, the multiphysics one: its own question.
function leaveText(target,model=false){
 if(model==='multiphysics')return multiView.inProject()?leaveConfirmText({from:'multiphysics',runs:multiView.projectUnsavedRuns(),target}):null;
 return projectLeaveText({name:project.name,models:unsavedModels()});
}
// a model file being read after its confirmation: no second open starts until it is done
let openingModel=false;
function guardLeave(target,model,proceed){
 if(openingModel){notice('Wait until the model file has been opened.');return;}
 const text=leaveText(target,model);if(!text){proceed();return;}
 // Save cannot run over an invalid input draft: then only Keep and Continue are offered
 if(['session','project'].includes(text.save?.kind)&&$('save-session').disabled)text.save=null;
 pendingLeave={proceed,kind:text.save?.kind||null,opener:document.activeElement};
 $('leave-confirm-title').textContent=text.title;$('leave-confirm-description').textContent=text.description;
 $('leave-stay').textContent=text.stay;$('leave-go').textContent=text.leave;$('leave-save').hidden=!text.save;$('leave-save').textContent=text.save?.label||'';
 if(!leaveDialog.open)leaveDialog.showModal();
}
function endLeave(go){
 const pending=pendingLeave;pendingLeave=null;leaveDialog.close();if(!pending)return;
 if(go===false){restoreDialogFocus(pending.opener);notice(pending.kind==='project'?'Kept the current project and its runs.':'Kept the current model and its runs.');return;}
 if(go==='save'){
  (pending.kind==='project'?saveProjectFile({saveAs:false}):saveSessionFile({saveAs:false})).then(()=>{
   // the file was not written (the 16 MiB question, a cancel or a refusal): stay, and say so
   if(pending.kind==='project'?unsavedModels().length>0:multiView.projectUnsavedRuns()>0){if(overflowDialog.open)notice('Answer the 16 MiB question to save the project; nothing was opened. Open the file again once the project is saved.');return;}
   pending.proceed();
  });
  return;
 }
 pending.proceed();
}
$('leave-stay').onclick=()=>endLeave(false);$('leave-go').onclick=()=>endLeave(true);$('leave-save').onclick=()=>endLeave('save');
leaveDialog.oncancel=event=>{event.preventDefault();endLeave(false);};
const TEMPLATE_NAMES={'heated-waveguide':'Heated silicon waveguide',optical:'Optical waveguide',heat:'Heat conduction',joule:'Joule heating'};
// The Library page (P3): headed by the project line and its name, which Rename sets; a card whose
// model is in the project but not shown reads "In this project · N runs".
function libraryOptions(){
 const inProject={};
 if(workspaceInProject()&&multiView.active()&&workspaceCard())inProject[workspaceCard()]=runs.length;
 if(multiView.inProject()&&!multiView.active())inProject['heated-waveguide']=multiView.projectRuns();
 // round 18 (X10): every model of the project, shown or not, with its runs: its card reads "Return to model"
 const returnTo={};if(workspaceInProject()&&workspaceCard())returnTo[workspaceCard()]=workspaceCard()==='optical'?runs.length:0;if(multiView.inProject())returnTo['heated-waveguide']=multiView.projectRuns();
 return {onOpenFile:()=>$('open-session').click(),inProject,returnTo,project:{line:projectLine(),name:project.name,onRename:renameProject}};
}
// A browser restore of a record saved to a project file (S4, round 16): the project names that file
// and its name again, so the header and Save name it. The project reads as saved when the record
// still matched the file and the restored model is its only model; else as changed since (round 19,
// Y3: a record changed since its file brings back the name and file too).
// opened: the file the record was opened from, when it names no project file (Y3): the header says
// the project was recovered from a copy of it; the record holds no project name, so none is guessed.
// matched (round 20, Z2): the second restore of a pair whose first record also still matched this
// file: with both models back the project reads as saved.
function restoreProjectFile(file,opened=null,{matched=false}={}){
 if(!file?.projectName){if(!file&&opened&&!project.file&&!project.name)project.copyOf=opened;return;}
 project.name=file.projectName;project.nameFrom=nameSource(file.projectName,file.name);
 const kept=rememberFile({name:file.name,how:'recovered',scope:project.scope});if(!kept)return;
 project.copyOf=null;project.file={...kept,savedAt:file.savedAt,models:modelList()};project.stamp=file.current===true&&(projectModels().length===1||matched)?projectStamp():null;
}
// The project name of a browser-recovery record (its `project`), when no savedFile.projectName named
// it (restoreProjectFile): the name and where it came from, and no project file, so File › Save
// suggests projectFileName(name) and asks. A pair restore keeps the name of the newer record.
// openedFile, openedCurrent: the file the record was opened from and whether it still matched it.
function restoreProjectName(record,options={}){
 const next=recoveredProjectName(project,record,options);if(!next)return;
 if(next.name!==project.name||next.nameFrom!==project.nameFrom)project.copyOf=null;
 Object.assign(project,next);project.recovered={...next.recovered,stamp:projectStamp()};
 // round 24 (B2): the file the record came from, named by the header after the next change too
 project.fromFile=next.recovered.opened||next.recovered.changed||null;
}
// the project of a recovery record this tab writes: its name when it has one
const recordProjectNow=()=>project.name?{name:project.name,from:project.nameFrom||'user'}:null;
function renameProject(value){
 let name;try{name=validateProjectName(value);}catch(e){notice(e.message+' The project name is unchanged.');return false;}
 if(name===project.name)return true;
 project.name=name;project.nameFrom='user';refreshPersistence();notice(`Project renamed to “${name}”. File › Save writes the new name.`);return true;
}
// The start page's cards: the coupled template opens the multiphysics model, the others the
// application of their physics selection.
// Switching models inside a project asks nothing (P3): a card whose model is in the project shows
// it as it was left; the other cards add their model.
function chooseTemplate(id){
 if(multiView.busy()){notice('Wait for the multiphysics run to finish, or stop it under Study.');return;}
 if(openingModel){notice('Wait until the model file has been opened.');return;}
 if(id==='heated-waveguide'&&multiView.inProject()){if(multiView.active()){ui.page=multiView.returnPage();render();}else multiView.show();topOfPage();return;}
 // the workspace's card while the multiphysics model is shown: the workspace as it was left (its
 // card shown again from the workspace itself chooses that model again, as before)
 if(id!=='heated-waveguide'&&multiView.active()&&workspaceInProject()&&workspaceCard()===id){
  const from=multiView.projectTitle();if(!leaveMultiphysics())return;
  // round 17 (U7; round 16 S9 returned to Compare too): a model with runs lands on Results with the
  // run last viewed, whatever page it was left on; a model without runs on Model
  const back=workspaceReturn,run=back&&runs.find(r=>r.job===back.run);if(run)solverRun=run;
  ui.page='Model';select(ui.selection&&names.includes(ui.selection)?ui.selection:'Geometry');
  if(runs.length){if(!solverRun)solverRun=runs.at(-1);ui.page='Results';if(ui.selection==='Study')ui.selection='Geometry';render();}
  topOfPage();notice(`${workspaceTitle()} shown with ${runs.length===0?'no runs':runs.length===1?'its run':`its ${runs.length} runs`}; ${from} stays in this project. Nothing was computed.`);return;
 }
 openTemplateCard(id);
}
// round 17 (U7): a model switched to starts at the top of its page (the heated model's Results table
// was left scrolled out of view by the other model's page)
function topOfPage(){for(const id of ['canvas','inspector']){const el=$(id);if(el)el.scrollTop=0;}}
function openTemplateCard(id){
 fileScope++;
 if(id==='heated-waveguide'){multiView.openTemplate({note:multiView.active()?null:opticalRunsNote()});return;}
 if(!leaveMultiphysics())return;projectId('workspace');
 Object.assign(state,templatePhysics(id));state.modeCount=DEFAULT_MODE_COUNT;state.groupIndex=false;state.openBoundary=null;state.searchTarget=null;ui.closedNear=null;ui.pmlCheck=false;newModelInputs=signature();select('Geometry');notice(isHeat()||isOptical()||isJoule()?'Model ready. Edit settings, review the study, then run explicitly.':'Setup preview ready. Coupled calculation is unavailable.');
}
// Where the optical runs of this tab are while another model is open (Messages, on switching).
// file: the session file that holds these runs (as the leave question decides it), by name;
// recovery: browser recovery holds them, unless another tab has replaced the record.
function opticalRunsNote(){
 const file=runs.length&&savedRunsState===runsStamp()?(lastSavedFile?.name||(loadedSession?.kind==='opened'?loadedSession.name:null)):null;
 // 'updating': the record of these runs is being written (or an earlier one of them is stored)
 const recovery=['kept','updating'].includes(recoveryState)||(recoveryState!=='conflict'&&loadedFrom()?.kind==='recovered'&&loadedFrom().current);
 return opticalRunsStayText({runs:runs.length,file,recovery});
}
function refreshHeatControls(){
 const button=$('run-heat');if(!button)return;button.hidden=!isHeat();$('run-optical').hidden=isHeat()||isJoule()||multiView.active();if(!isHeat())return;
 const block=heatBlock();button.disabled=!!block||heatState.busy;button.textContent=heatState.busy?'Computing…':'Run study';
 if(numericDrafts.invalid||heatDrafts.size)$('status').textContent='Input errors · correct or restore the last valid values';
 else $('status').textContent=heatState.busy?'Heat calculation running':block?'Heat input not ready · '+block:'Heat solver ready · explicit Run required';
 const message=$('heat-message');if(message)message.textContent=heatState.error?requestFailedText('Heat',heatState.error):heatState.busy?'Validating and solving the current inputs…':'';
}
async function runHeat(){
 if(!heatController||heatState.busy||heatBlock())return;
 const doc=heatDocument(state.thermal);heatCapture=JSON.parse(JSON.stringify(state.thermal));edits.record(inputsFile());
 notice('Validating heat input…');
 if(!await heatController.validate(doc)){notice('Heat input rejected: '+(heatController.state().error||'validation failed')+' Inputs unchanged.');refreshHeatControls();return;}
 if(heatSignature()!==JSON.stringify(heatCapture)){notice('Inputs changed during validation; run again.');return;}
 notice('Solving heat conduction…');await heatController.run();
}
function heatStudy(){
 const host=$('canvas');host.innerHTML='<h2>Steady heat study</h2><p>Review the plate, then run. Run validates the current inputs through the public thermal API and then solves them.</p>'+pair('Plate',escapeHtml(thermalSummary(state.thermal)))+SIDES.map(side=>pair(side[0].toUpperCase()+side.slice(1),escapeHtml(sideText(state.thermal.sides[side])))).join('')+pair('Mesh',`${state.thermal.nx} × ${state.thermal.ny} divisions, ${(state.thermal.nx+1)*(state.thermal.ny+1)} nodes`);
 const block=heatBlock();if(block)host.insertAdjacentHTML('beforeend',`<p class="validation-warning">${escapeHtml(block)}</p>`);
 host.insertAdjacentHTML('beforeend','<p id="heat-message" role="status"></p>');
 const details=document.createElement('details');details.className='solver-document';const title=document.createElement('summary');title.textContent='Solver document · lengths in mm, temperatures in K';const body=document.createElement('pre');try{body.textContent=JSON.stringify(heatDocument(state.thermal),null,2);}catch(error){body.textContent=error.message;}details.append(title,body);host.append(details);
}
function heatResults(){
 const host=$('canvas');if(!heatRun){host.innerHTML='<h2>No heat result in this tab</h2><p>Edit the plate and run a heat study. Heat results are not stored in session files.</p>';$('inspector').innerHTML='<h2>Heat results</h2><p>No completed heat run.</p>';return;}
 const same=heatRun.signature===heatSignature(),run=heatRun,s=run.payload.summary||{};
 host.innerHTML='<h2>Steady temperature and heat flux</h2>';
 const desc=document.createElement('p');const heatParts=t=>[thermalSummary(t),SIDES.map(side=>side+': '+sideText(t.sides[side])).join(' · '),`${t.nx} × ${t.ny} divisions`];
 desc.textContent=runInputsLine(heatParts(run.input),heatParts(state.thermal));host.append(desc);
 const bar=document.createElement('div');bar.className='toolbar';bar.innerHTML=`<label>Field <select id="heat-field">${[['temperature','Temperature T [K]'],['magnitude','Heat flux |q| [W/m²]'],['qx','Heat flux qx [W/m²]'],['qy','Heat flux qy [W/m²]']].map(([v,l])=>`<option value="${v}" ${v===heatField?'selected':''}>${l}</option>`).join('')}</select></label><label><input id="heat-arrows" type="checkbox" ${heatArrows?'checked':''}> Flux arrows</label>`;host.append(bar);
 const card=document.createElement('div');card.className='heat-plot';const canvas=document.createElement('canvas');canvas.id='heat-field-canvas';canvas.style.cssText='display:block;width:100%;height:var(--plot-height,360px);cursor:crosshair';canvas.setAttribute('role','img');card.append(canvas);host.append(card);
 const probe=document.createElement('p');probe.id='heat-probe';probe.setAttribute('role','status');host.append(probe);
 const note=document.createElement('p');note.textContent='Temperature is interpolated linearly inside each triangle (P1); heat flux is constant per triangle. Colours span this result\'s own minimum to maximum. Click the plot to read a value. Heat results are kept in this tab only; save the input file to keep the design.';host.append(note);
 const T=globalThis.ThermalStudio;
 const draw=()=>{if(!canvas.isConnected)return;try{const model=T.viewModel(run.payload,heatField);T.draw(canvas,model,{arrows:heatArrows});canvas.setAttribute('aria-label',`${model.field} ${model.min} to ${model.max} ${model.unit}`);
  if(heatProbe){const v=T.sample(model,heatProbe);probe.textContent=v===null?'No triangle contains this point.':`At (${heatProbe[0].toFixed(4)}, ${heatProbe[1].toFixed(4)}) ${model.lengthLabel}: ${heatField==='temperature'?'T':heatField==='magnitude'?'|q|':heatField} = ${v.toPrecision(6)} ${model.unit}${model.nodal?' (P1 interpolation)':' (triangle value)'}`;}else probe.textContent='No point selected.';
  canvas.onclick=event=>{const r=canvas.getBoundingClientRect(),tr=T.transform(model,Math.round(r.width),Math.round(r.height));heatProbe=tr.inverse(event.clientX-r.left,event.clientY-r.top);draw();};
 }catch(error){probe.textContent='Plot unavailable: '+error.message;}};
 $('heat-field').onchange=()=>{heatField=$('heat-field').value;draw();};$('heat-arrows').onchange=()=>{heatArrows=$('heat-arrows').checked;draw();};
 heatResize=new ResizeObserver(draw);heatResize.observe(canvas);draw();
 const named=globalThis.ThermalStudio.named(run.payload.arrays),t=named.temperature;let lo=Infinity,hi=-Infinity;for(const v of t){lo=Math.min(lo,v);hi=Math.max(hi,v);}
 $('inspector').innerHTML='<h2>Heat result</h2>'+pair('Inputs',same?'Same as the current inputs':'Current inputs differ from this run')+pair('Minimum T',lo.toPrecision(7)+' K')+pair('Maximum T',hi.toPrecision(7)+' K')+pair('Nodes',named.nodes.length)+pair('Triangles',run.payload.arrays.triangles.length)+pair('Result format',escapeHtml(run.payload.result_format))+pair('Completed',new Date(run.completedAt).toLocaleTimeString())+'<p>Public steady heat solver output. Not stored in sessions or browser recovery.</p>';
 const restore=document.createElement('button');restore.textContent='Restore run inputs';restore.disabled=same;restore.onclick=()=>setThermal(run.input,'Heat inputs restored from the run.');$('inspector').append(restore);
}
function renderHeat(){
 document.querySelector('main').classList.remove('comparing');document.querySelector('main').classList.toggle('choosing',ui.page==='Applications');
 $('sequence').innerHTML='<span>Steady heat · thermal.steady2d</span><span>Run validates the current inputs, then solves</span><span>Mesh convergence not certified</span>';
 document.querySelector('.workspace > .toolbar').style.display=ui.page==='Model'?'flex':'none';
 document.querySelector('.workspace > .note').textContent=ui.page==='Results'?'Heat results belong to the inputs captured at Run.':'Plate dimensions in mm, temperatures in K, other quantities in SI. Select a side to edit its condition.';
 if(ui.page==='Model'&&ui.selection==='Study')heatStudy();
 if(ui.page==='Results')heatResults();
 if(ui.page==='Compare'){$('canvas').innerHTML='<h2>Compare</h2><p>Comparison is available for optical runs. Heat results are shown one at a time in Results.</p>';}
 if(ui.page==='Connections'){$('canvas').innerHTML='<h2>Heat-only model</h2><p>This application solves steady heat conduction only. No electric, mechanical or optical coupling is configured.</p>';}
 bindHeatSides();refreshHeatControls();
}
// These views describe the existing model; they do not add solver capabilities.
const modelTree=treeState();
// the tree drawn again with the focus kept on its item (a group opened or closed, a node chosen)
function drawModelTree(){const had=treeFocus($('tree'),modelTree);$('tree').innerHTML=renderModelTree();$('tree').querySelectorAll('[data-node]').forEach(b=>b.onclick=()=>b.dataset.node.startsWith('results:')?openResultsNode(b.dataset.node):select(b.dataset.node));bindTree($('tree'),modelTree,drawModelTree);restoreTreeFocus($('tree'),modelTree,had);}
// The Results group's nodes open their page, as the page tabs do; the shown run stays.
function openResultsNode(node){ui.page=node==='results:compare'?'Compare':'Results';render();}
function renderModelTree(){
 const model=isHeat()?'Heat conduction':isJoule()?'Joule heating':isOptical()?'Optical waveguide':'Heated waveguide';
 const groups=[['Component 1',['Geometry','Materials']],['Physics',isHeat()?['Heat transfer']:isJoule()?['Electric currents','Heat transfer']:isOptical()?['Optical modes']:names.slice(2,6)],['Analysis',['Couplings','Mesh','Study'].filter(n=>n!=='Couplings'||(!isHeat()&&!isJoule()&&!isOptical()))]];
 const marks={'Geometry':'◇','Materials':'▱','Electric currents':'ϟ','Heat transfer':'∿','Solid mechanics':'↔','Optical modes':'λ','Couplings':'⇄','Mesh':'▦','Study':'▷'};
 // an ARIA tree (workspace-tree.mjs): a node is selected only while its settings are shown; on
 // Results and Compare no model node is, and the optical tree's Results group marks that page (round 14)
 const shown=n=>(ui.page==='Model'||ui.page==='Connections')&&ui.selection===n;
 return '<div class="pane-title"><span>Model builder</span><span class="pane-detail">Model 1</span></div><div class="model-root"><span aria-hidden="true">▾ ◇</span><strong>'+model+'</strong></div>'+treeOpen()+groups.map(([title,nodes])=>'<section class="tree-group" role="none">'+groupHeading(title,!modelTree.collapsed.has(title))+nodes.map(n=>`<button type="button" data-node="${n}" ${itemAttributes(2,shown(n))}><span class="tree-node-mark" aria-hidden="true">${marks[n]}</span>${n}</button>`).join('')+'</section>').join('')+(isOptical()?resultsGroup({runs:runs.length,shownRun:runNumber(solverRun),page:ui.page,expanded:!modelTree.collapsed.has('Results'),runsLabel:runsNodeLabel(runs.length)}):'')+'</div><div class="capability-card"><span class="capability-dot" aria-hidden="true"></span><strong>'+(isHeat()||isOptical()||isJoule()?'Solver available':'Setup only')+'</strong><p>'+(isHeat()?'Steady heat conduction':isJoule()?'Joule heating on named regions':isOptical()?'Optical mode analysis':'Coupled calculation unavailable')+'</p></div>';
}
let disposeConnectionGraph=()=>{};
function renderConnectionOverview(){return renderConnectionGraph(state,ui.selection,active(),ui.graphOptionsOpen);}

// The inspector is rebuilt in stages with layout reads in between, which can clamp its scroll;
// a redraw of the same panel keeps its scroll position and the focused field in view.
let panelKey=null;
// Round 16 (S9): the page each model was last shown on (not the Library), so its Library card returns there
function rememberReturn(){if(ui.page==='Applications')return;if(multiView.active())multiView.rememberPage(ui.page);else if(workspaceInProject())workspaceReturn={page:ui.page,run:solverRun?.job||null};}
function render(){rememberReturn();if(ui.page!=='Compare')compareOpen=false;const key=ui.page+'/'+ui.selection,inspectorScroll=key===panelKey?$('inspector').scrollTop:0,before=document.activeElement;panelKey=key;renderPanels();$('inspector').scrollTop=inspectorScroll;
 // only a field whose focus was restored onto a new element is brought into view; a background redraw does not move a panel the user scrolled
 const focused=document.activeElement;if(focused&&focused!==before&&$('inspector').contains(focused)&&focused!==$('inspector'))focused.scrollIntoView({block:'nearest'});}
function renderPanels(){if(multiView.active()){disposeConnectionGraph();disposeConnectionGraph=()=>{};profileResize?.disconnect();heatResize?.disconnect();jouleView.disconnect();disposeWidthEditor();disposeWidthEditor=()=>{};if(typeof fieldResize!=='undefined'&&fieldResize)fieldResize.disconnect();$('run-optical').hidden=true;$('run-heat').hidden=true;$('run-joule').hidden=true;$('input-problems').hidden=true;multiView.renderPage();return;}document.querySelector('main').dataset.page=ui.page;$('view-title').textContent=({Model:'Graphics',Connections:'Physics connections',Results:'Results',Compare:'Comparison',Applications:'Model library'})[ui.page];$('view-detail').textContent=ui.page==='Model'?'Interactive model view':ui.page==='Connections'?(isJoule()?'Solved together':isHeat()||isOptical()?'Single physics':'One-way setup'):ui.page==='Applications'?projectLine():'';document.querySelectorAll('[data-command-node]').forEach(b=>b.disabled=ui.page==='Applications');disposeConnectionGraph();disposeConnectionGraph=()=>{};if(!isJoule())$('solver-log').hidden=true;document.querySelector('main').classList.toggle('connecting',ui.page==='Connections'&&!isOptical()&&!isHeat());const focused=document.activeElement,focusId=focused?.id;const focusData=['port','joule-node','select','toggle','node','body','pick-mode','pick-body','pick-shape','shape','handle','pick-edge','run'].map(key=>[key,focused?.getAttribute('data-'+key)]).find(([,value])=>value!==null&&value!==undefined);profileResize?.disconnect();heatResize?.disconnect();jouleView.disconnect();profileRedraw=()=>{};disposeWidthEditor();disposeWidthEditor=()=>{};if(isHeat()){if(!HEAT_NODES.includes(ui.selection))ui.selection='Geometry';ui.view='Section';pick.mode='Bodies';pick.boundary=null;}if(isJoule()){if(!JOULE_NODES.includes(ui.selection))ui.selection='Geometry';ui.view='Section';pick.mode='Bodies';pick.boundary=null;}if(isOptical()){if(ui.page==='Model'&&['Electric currents','Heat transfer','Solid mechanics','Couplings'].includes(ui.selection))ui.selection='Geometry';ui.view='Section';if(ui.body==='Heater')ui.body='Core';if(pick.boundary&&!pick.boundary.startsWith('optical-'))pick.boundary=null;}else if(pick.boundary?.startsWith('optical-'))pick.boundary=null;document.querySelector('[data-view=Perspective]').disabled=isOptical()||isHeat();if(typeof fieldResize!=='undefined'&&fieldResize)fieldResize.disconnect();document.querySelectorAll('[data-command-node]').forEach(b=>b.onclick=()=>select(b.dataset.commandNode));markPageTabs(document.querySelector('.page-tabs'),ui.page);document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.view===ui.view));$('breadcrumb').textContent=ui.page+' / '+ui.selection;document.querySelectorAll('[data-view]').forEach(b=>b.hidden=ui.page!=='Model');drawModelTree();
let inspector='<span class="muted">SELECTION</span><h2>'+ui.selection+'</h2>';
if(ui.selection==='Geometry'&&isOptical())inspector+=shapeInspector();
else if(ui.selection==='Geometry')inspector+=`<label for="width">Core width <output>${state.width} nm</output><input id="width" aria-label="Core width slider [nm]" type="range" min="300" max="900" step="any" value="${state.width}"></label><label>Core width [nm]<input id="width-number" type="number" min="300" max="900" step="any" value="${state.width}"></label>`+pair('Bodies','Core / oxide / heater')+pair('Representation','Concept preview');
else if(ui.selection==='Electric currents')inspector+=`<label>Applied voltage [V]<input id="voltage" type="number" min="0" max="10" step="0.1" value="${state.voltage}"></label>`+pair('Terminal','Heater input')+pair('Ground','Heater output')+pair('Output','Joule heat [W/m³]');
else if(ui.selection==='Couplings')inspector+='<div class=setup-badge>Setup only</div><p>One-way physics configuration. Select a node or port to edit its properties.</p>'+pair('Direction','One-way')+pair('Field transfer','Not implemented')+pair('Coupled execution','Unavailable');
else if(ui.selection==='Materials')inspector+=pair('Core',setup.materials.Core||'Unassigned')+pair('Cladding',setup.materials.Oxide||'Unassigned')+pair('Heater',setup.materials.Heater||'Unassigned')+'<p>Conductivity, thermal expansion, elasticity and optical material laws require validated assignments.</p>';
else if(ui.selection==='Solid mechanics')inspector+=pair('Load','Thermal strain')+pair('Constraints','Not assigned')+pair('Output','Displacement [m]');
else if(ui.selection==='Heat transfer')inspector+=pair('Source','Joule heat')+pair('Heat loss','Not assigned')+pair('Output','Temperature [K]');
else if(ui.selection==='Optical modes')inspector+=pair('Wavelength',state.wavelength+' nm')+pair('Inputs',isOptical()?'Material at '+state.wavelength+' nm, geometry':'n(T), geometry')+pair('Output','Modes / effective index');
else inspector+=pair('Status','Not executed')+'<p>Settings and validation will be implemented behind package APIs.</p>';
if(isHeat())inspector=heatInspector();else if(isJoule())inspector=jouleView.inspector();else inspector+='<p class="muted">Editing this design does not run a simulation.</p>';$('inspector').innerHTML=inspector;if(ui.selection==='Geometry'&&isOptical())bindShapePanel();if(isHeat())bindHeatPanel();if(isJoule())jouleView.bindInspector();
if(ui.page==='Connections'&&isOptical()){$('canvas').innerHTML='<h2>Optical-only model</h2><p>This model has one optical interface and no coupled physics. Choose the heated-waveguide template to configure a multiphysics preview; coupled computation remains unavailable.</p><button id=choose-multiphysics>Choose another application</button>';$('choose-multiphysics').onclick=()=>{ui.page='Applications';render();};}
else if(ui.page==='Connections')$('canvas').innerHTML=renderConnectionOverview();
else if(ui.page==='Applications')renderApplications($('canvas'),resumeOffer(),cardResumeOffers(),libraryOptions());
else if(ui.page==='Results')$('canvas').innerHTML='<h2>Results workspace</h2><p>Temperature · displacement · optical fields</p><div class="empty">No computed results<br>Run adapters are not connected.</div><p>Planned: common coordinates, time playback, probes and explicit deformation magnification.</p>';
else $('canvas').innerHTML='<h2>'+ui.selection+'</h2>'+geom();
$('sequence').innerHTML=applicationChosen()?active().map((n,i)=>`<span><b>${i+1}</b>${n}</span>`).join('')+'<span>Preflight pending</span>':'<span class="sequence-empty">Study steps appear once you choose an application.</span>';
const width=$('width');if(width)width.oninput=()=>{state.width=+width.value;numericDrafts.clear('width');if($('width-number'))$('width-number').value=width.value;refreshInputIssues();width.previousElementSibling.textContent=state.width+' nm';if(ui.page==='Model'){const svg=$('canvas').querySelector('svg');if(svg){svg.outerHTML=geom();bindPicking();refreshViewport?.();bindWidthEditor();}}};const v=$('voltage');if(v)v.onchange=()=>{if(!v.checkValidity()||v.value===''){v.value=state.voltage;return;}state.voltage=+v.value;};
document.querySelectorAll('[data-toggle]').forEach(b=>b.onchange=()=>{const prior=state[b.dataset.toggle];state[b.dataset.toggle]=b.checked;if(b.dataset.toggle==='heat'&&b.checked)state.electric=true;
 if(isJoule()){state[b.dataset.toggle]=prior;notice('The multiphysics preview keeps mechanics or optics. For electric currents with heat alone, choose Library → Joule heating.');}render();});document.querySelectorAll('[data-select]').forEach(b=>b.onclick=()=>{if(ui.page==='Connections'){ui.selection=b.dataset.select;render();}else select(b.dataset.select);});document.querySelectorAll('[data-template]').forEach(b=>b.onclick=()=>chooseTemplate(b.dataset.template));if(isHeat()){bindNumericInputs();refreshInputIssues();refreshViewport=ui.page==='Model'&&$('canvas').querySelector('svg')?installViewport($('canvas'),cameras.Section):null;renderHeat();}else if(isJoule()){bindNumericInputs();refreshInputIssues();refreshViewport=ui.page==='Model'&&$('canvas').querySelector('svg')?installViewport($('canvas'),cameras.Section):null;jouleView.page();}else{decorate();solverPanel();pickingPanel();bindNumericInputs();refreshInputIssues();refreshViewport=ui.page==='Model'?(isOptical()?installViewport($('canvas'),cameras.Optical,{fit:()=>cameras.Optical.fitTo(WINDOW_VIEW),fitShapes:()=>cameras.Optical.fitTo(shapesView(state.shapes)),onChange:()=>{if(refreshViewport)bindWidthEditor();}}):installViewport($('canvas'),cameras[ui.view])):null;bindWidthEditor();refreshHeatControls();}if(ui.page==='Connections'&&!isOptical()&&!isHeat())disposeConnectionGraph=installConnectionGraph($('canvas'),open=>{ui.graphOptionsOpen=open;});if(document.activeElement===document.body){const target=focusId?$(focusId):focusData?document.querySelector('[data-'+focusData[0]+'="'+CSS.escape(focusData[1])+'"]'):null;target?.focus({preventScroll:true});}}

// What stops an optical Run now (input errors, a computation or job in progress, an unsupported
// input, no free run slot), in the footer's words; null when Run is ready.
function opticalHold(){
 if(numericDrafts.invalid)return 'Input errors · correct or restore the last valid values';
 return solverBusy?'Optical computation running':pendingJob?(jobResumeBlocked?'Unavailable job · detach before starting another calculation':'Pending job · resume or detach'):retentionBlock()||(opticalBlock()?'Optical input unsupported · review Study':null);
}
// The dock heading says what the last optical run computed, with the same run as the footer;
// while Run is held it repeats the footer's words, so the two never disagree. The multiphysics
// model sets its own heading, and the other models keep the default words.
function refreshSequenceHeading(){
 if(multiView.active())return;const heading=document.querySelector('.dock-title>span');if(!heading)return;
 const text=applicationChosen()&&isOptical()?opticalHold()||opticalSequenceHeading(opticalFreshness(current(),runs,viewedRun(),state.modeCount,state.groupIndex,pmlNow(),closedTargetNow())):opticalSequenceHeading({state:'none'});
 if(heading.textContent!==text)heading.textContent=text;
}
function refreshInputIssues(){
 const host=$('input-problems');host.replaceChildren();host.hidden=!numericDrafts.invalid;
 for(const issue of numericDrafts.issues){
  const row=document.createElement('div'),message=document.createElement('span'),fix=document.createElement('button');
  message.textContent=issue.message+' Last valid value is retained.';fix.textContent='Edit '+INPUT_FIELDS[issue.key].label;fix.dataset.fixInput=issue.key;
  fix.onclick=()=>{select(INPUT_FIELDS[issue.key].node);$(INPUT_FIELDS[issue.key].id)?.focus();};row.append(message,fix);host.append(row);
 }
 if(numericDrafts.invalid){const discard=document.createElement('button');discard.id='discard-invalid';discard.textContent='Restore last valid values';discard.onclick=()=>{numericDrafts.clear();render();notice('Invalid drafts discarded. Last valid model inputs retained.');};host.append(discard);}
 for(const [key,field] of Object.entries(INPUT_FIELDS)){
  const el=$(field.id);if(!el)continue;const issue=numericDrafts.get(key);el.setAttribute('aria-invalid',String(!!issue));
  const hint=$(field.id+'-hint');if(hint)hint.textContent=issue?issue.message:`Allowed: ${field.min}–${field.max}${field.unit?' '+field.unit:''}.`;
 }
 for(const id of ['save-project','save-draft','save-session','open-session','restore-draft','menu-open','menu-save','menu-save-as','menu-export-session'])$(id).disabled=numericDrafts.invalid||(multiView.active()&&id==='save-draft');
 $('run-optical').disabled=solverBusy||!!pendingJob||!!opticalBlock()||!!retentionBlock()||numericDrafts.invalid;refreshRunOptions();
 if(!applicationChosen()&&!numericDrafts.invalid)$('status').textContent='Choose a model to start';
 else $('status').textContent=opticalHold()||opticalReadyStatus(opticalFreshness(current(),runs,viewedRun(),state.modeCount,state.groupIndex,pmlNow(),closedTargetNow()));
 refreshSequenceHeading();refreshPersistence();jouleView.refreshControls();
 // the Study panel's next-run line follows every accepted edit (a numeric edit does not redraw the panel)
 const next=$('next-run-inputs');if(next&&isOptical()){const text=numericDrafts.invalid?'Next run: correct the highlighted inputs first':nextRunText(current(),state.modeCount,state.groupIndex,pmlNow(),closedTargetNow());if(next.textContent!==text)next.textContent=text;}
}
// widthBase: the selected shape when its Width field took focus (round 16); lastKept: what the last
// Width entry kept ('centre', 'left'); alsoApplied: refused values applied since the field took focus
let widthBase=null,lastKept=null,alsoApplied=[];
function bindNumericInputs(){
 for(const [key,field] of Object.entries(INPUT_FIELDS)){
  const el=$(field.id);if(!el)continue;el.step=field.integer?'1':'any';const issue=numericDrafts.get(key);if(issue)el.value=issue.raw;
  const hint=document.createElement('p');hint.id=field.id+'-hint';hint.className='input-hint';el.closest('label').after(hint);el.setAttribute('aria-describedby',hint.id);
  el.oninput=()=>{const parsed=numericDrafts.update(key,el.value);if(parsed.ok){if(key==='temperature')setup.temperature=parsed.value;
   else if(field.prop){
    // round 16 (S2): a Width keeps the centre, else the left edge, of the shape at focus; then the
    // refused values of the same shape are tried again on the shape as it now is
    let fit;try{fit=fitShapeEdit(selectedShape(),field.prop,parsed.value,{base:field.prop==='w'&&widthBase||selectedShape(),index:ui.shape});}catch(error){numericDrafts.reject(key,el.value,error.message);refreshInputIssues();return;}
    lastKept=fit.kept;const retried=retryShapeDrafts(numericDrafts,fit.shape,key,{index:ui.shape});setShape(ui.shape,retried.shape);
    for(const a of retried.applied)if(!alsoApplied.some(b=>b.key===a.key))alsoApplied.push(a);else alsoApplied.find(b=>b.key===a.key).value=a.value;
    for(const [k,f] of Object.entries(INPUT_FIELDS))if(f.prop&&k!==key&&!numericDrafts.get(k)&&$(f.id))$(f.id).value=selectedShape()[f.prop];}
   else state[key]=parsed.value;
   if(key==='width'||key==='height'||field.prop){const slider=$('width');if(slider&&key==='width'){slider.value=parsed.value;slider.previousElementSibling.textContent=parsed.value+' nm';}const svg=$('canvas').querySelector('svg');if(svg){svg.outerHTML=geom();bindPicking();refreshViewport?.();bindWidthEditor();}}
  }refreshInputIssues();};
  // a committed value is said in Messages, with the Left x a Width edit moved (the value at focus)
  // resultNotice is read at focus: the first keystroke already replaces the result's notice
  let leftBefore=null,afterResult=false;el.onfocus=()=>{leftBefore=field.prop?selectedShape()?.x??null:null;widthBase=field.prop==='w'?{...selectedShape()}:null;lastKept=null;alsoApplied=[];afterResult=resultNotice;};
  el.onchange=()=>{if(numericDrafts.get(key))return;const shape=field.prop?selectedShape():null,value=key==='temperature'?setup.temperature:shape?shape[field.prop]:state[key];
   const kept=field.prop==='w'?lastKept:null,leftX=field.prop==='w'&&leftBefore!==null&&(shape.x!==leftBefore||kept==='left')?shape.x:null;if(shape)leftBefore=shape.x;
   // the base of the next Width entry is the shape as committed now
   if(field.prop==='w')widthBase={...shape};
   if(value!==undefined)notice(editNoticeText(key,value,{leftX,afterResult,kept,also:alsoApplied}));afterResult=false;lastKept=null;alsoApplied=[];};
  el.onkeydown=e=>{if(e.key==='Escape'){numericDrafts.clear(key);el.value=key==='temperature'?setup.temperature:field.prop?selectedShape()[field.prop]:state[key];refreshInputIssues();}};
 }
}

const escapeHtml=text=>String(text).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
const SHAPE_MATERIAL_CHOICES=['',...Object.keys(SHAPE_MATERIALS)];
function shapeInspector(){
 const shape=selectedShape(),n=state.shapes.length;
 const list=state.shapes.map((s,i)=>`<button type="button" class="shape-item" data-shape="${i}" aria-pressed="${i===ui.shape}"><span class="swatch" style="background:${MATERIAL_FILL[s.material]}"></span>${i+1}. ${escapeHtml(s.name)} · ${s.type==='rect'?'rectangle':s.type} · ${s.material||'unassigned'}</button>`).join('');
 const add=['rect','circle','polygon'].map(t=>`<button type="button" data-add-shape="${t}" ${n>=MAX_SHAPES?'disabled':''}>Add ${t==='rect'?'rectangle':t}</button>`).join('');
 const field=key=>{const f=INPUT_FIELDS[key];return `<label>${f.label} [nm]<input id="${f.id}" type="number" min="${f.min}" max="${f.max}" step="any" value="${shape[f.prop]}"></label>`;};
 const props=shape.type==='rect'?['shapeX','shapeY','shapeW','shapeH']:shape.type==='circle'?['shapeCx','shapeCy','shapeR']:[];
 const vertices=shape.type==='polygon'?`<label>Vertices [nm] · one "x, y" per line, 3–12 points<textarea id="shape-points" rows="${Math.min(12,shape.points.length+1)}" spellcheck="false">${shape.points.map(p=>p.join(', ')).join('\n')}</textarea></label><p class="input-hint" id="shape-points-hint">Applied when the field loses focus. Edges may not cross.</p>`:'';
 const overlaps=overlappingPairs(state.shapes).map(([a,b])=>`<li>${escapeHtml(state.shapes[a].name)} and ${escapeHtml(state.shapes[b].name)} may overlap; ${escapeHtml(state.shapes[b].name)} (drawn later) wins there.</li>`).join('');
 const block=shapesBlock(state.shapes);
 return `<div class="shape-list" role="group" aria-label="Shapes in draw order">${list}</div>`+
  `<h3 class="property-heading">${escapeHtml(shape.name)} · ${shape.type==='rect'?'rectangle':shape.type}</h3><div class="property-grid"><div><label for="shape-name">Name</label><input id="shape-name" type="text" maxlength="40" value="${escapeHtml(shape.name)}"></div><div><label for="shape-material">Material</label><select id="shape-material">${options(SHAPE_MATERIAL_CHOICES,shape.material)}</select></div>${props.map(key=>'<div>'+field(key)+'</div>').join('')}</div>${shape.type==='rect'?'<p class="input-hint" id="shape-size-hint">Width keeps the shape centred (or its left edge, where centred it would leave the window); Height keeps its bottom edge.</p><details class="input-hint shape-size-more"><summary>More about width and height</summary><p>A Width change moves Left x by half the change, so an odd change gives a half-nanometre Left x (the centre is exact; typed values are not snapped to the drag step). Where the centred shape would leave the window, Left x stays and the right edge moves. A value refused because the shape would leave the window is tried again when you change another value of the shape. A core resting on y = 0 stays there when its height changes. Left x and Bottom y move the shape.</p></details>':''}${vertices}`+
  `<h3>Geometry tools</h3><div class="toolbar shape-actions">${add}<button type="button" id="duplicate-shape" ${n>=MAX_SHAPES?'disabled':''}>Duplicate</button><button type="button" id="delete-shape" ${n<=1?'disabled':''}>Delete</button><button type="button" id="shape-earlier" ${ui.shape===0?'disabled':''}>Draw earlier</button><button type="button" id="shape-later" ${ui.shape===n-1?'disabled':''}>Draw later</button></div>`+
  alignControls(shape)+pair('Draw order',`${ui.shape+1} of ${n} · later shapes win where they overlap`)+(block?`<p class="validation-warning">${escapeHtml(block)}</p>`:'')+(overlaps?`<ul class="shape-notes">${overlaps}</ul>`:'')+pair('Background','Silica · fills the rest of the window')+pair('Up to',`${MAX_SHAPES} shapes inside x ±1500 nm, y ±1200 nm`);
}
function referenceShape(){const others=state.shapes.map((s,i)=>i).filter(i=>i!==ui.shape);if(!others.length)return null;if(!others.includes(ui.reference))ui.reference=others.includes(ui.shape-1)?ui.shape-1:others[0];return ui.reference;}
function alignControls(shape){
 const ref=referenceShape(),others=state.shapes.map((s,i)=>[s,i]).filter(([,i])=>i!==ui.shape);
 const own=['centre-x','rest-y'].map(a=>`<button type="button" data-align="${a}">${ALIGN_ACTIONS[a]}</button>`).join('');
 const relative=ref===null?'<p class="muted">Add another shape to align against it.</p>':`<label>Reference shape<select id="shape-reference">${others.map(([s,i])=>`<option value="${i}" ${i===ref?'selected':''}>${i+1}. ${escapeHtml(s.name)}</option>`).join('')}</select></label><div class="toolbar shape-actions">${['left-of','right-of','on-top','below','centre-on'].map(a=>`<button type="button" data-align="${a}">${ALIGN_ACTIONS[a]}</button>`).join('')}</div>`;
 return `<h3>Align ${escapeHtml(shape.name)}</h3><div class="toolbar shape-actions">${own}</div>${relative}<label>Drag step<select id="snap-step">${SNAP_STEPS.map(v=>`<option value="${v}" ${v===ui.snap?'selected':''}>${v} nm</option>`).join('')}</select></label><p class="input-hint">Alignment moves the shape so its bounding edges meet exactly; it is refused if the shape would leave the window.</p>`;
}
function clearShapeDrafts(){for(const [key,field] of Object.entries(INPUT_FIELDS))if(field.prop)numericDrafts.clear(key);}
function commitShapes(next,selected,message){
 try{state.shapes=validateShapes(next);}catch(error){notice(error.message);return false;}
 ui.shape=selected;edits.endGroup();trackEdit();edits.endGroup();render();notice(message+' Run explicitly to compute new results.');return true;
}
function bindShapePanel(){
 const guard=()=>{if(numericDrafts.shapeInvalid){notice('Correct or restore the selected shape values first.');return false;}return true;};
 document.querySelectorAll('[data-shape]').forEach(b=>b.onclick=()=>chooseShape(+b.dataset.shape));
 document.querySelectorAll('[data-add-shape]').forEach(b=>b.onclick=()=>{if(!guard())return;const shape=newShape(b.dataset.addShape,state.shapes);commitShapes([...state.shapes,shape],state.shapes.length,shape.name+' added on top.');});
 $('duplicate-shape').onclick=()=>{if(!guard())return;const copy=duplicateShape(selectedShape(),state.shapes);commitShapes([...state.shapes,copy],state.shapes.length,copy.name+' added on top.');};
 $('delete-shape').onclick=()=>{if(state.shapes.length<=1)return;const name=selectedShape().name;clearShapeDrafts();commitShapes(state.shapes.filter((_,i)=>i!==ui.shape),Math.max(0,ui.shape-1),name+' deleted; Undo restores it.');};
 const reorder=delta=>{if(!guard())return;const i=ui.shape,j=i+delta;if(j<0||j>=state.shapes.length)return;const next=[...state.shapes];[next[i],next[j]]=[next[j],next[i]];commitShapes(next,j,`${next[j].name} moved ${delta<0?'earlier':'later'} in draw order.`);};
 $('shape-earlier').onclick=()=>reorder(-1);$('shape-later').onclick=()=>reorder(1);
 $('shape-name').onchange=()=>{const el=$('shape-name');if(!commitShapes(state.shapes.map((s,i)=>i===ui.shape?{...s,name:el.value.trim()}:s),ui.shape,'Shape renamed.'))el.value=selectedShape().name;};
 $('shape-material').onchange=()=>commitShapes(state.shapes.map((s,i)=>i===ui.shape?{...s,material:$('shape-material').value}:s),ui.shape,'Material updated.');
 document.querySelectorAll('[data-align]').forEach(b=>b.onclick=()=>{if(!guard())return;const ref=['centre-x','rest-y'].includes(b.dataset.align)?null:state.shapes[referenceShape()];try{const moved=alignShape(selectedShape(),b.dataset.align,ref);commitShapes(state.shapes.map((s,i)=>i===ui.shape?moved:s),ui.shape,`${moved.name}: ${ALIGN_ACTIONS[b.dataset.align].toLowerCase()}${ref?' '+ref.name:''}.`);}catch(error){notice(error.message+' Shape unchanged.');}});
 const reference=$('shape-reference');if(reference)reference.onchange=()=>{ui.reference=+reference.value;};
 $('snap-step').onchange=()=>{ui.snap=+$('snap-step').value;render();notice(`Dragging now moves in ${ui.snap} nm steps. The model is unchanged.`);};
 const points=$('shape-points');if(points)points.onchange=()=>{try{
  const parsed=points.value.trim().split(/\n+/).map((line,i)=>{const parts=line.split(/[\s,;]+/).filter(Boolean);if(parts.length!==2)throw new Error(`Vertex line ${i+1} needs x and y.`);return parts.map(v=>{const n=Number(v);if(!Number.isFinite(n))throw new Error(`Vertex line ${i+1} must contain numbers.`);return n;});});
  const next=state.shapes.map((s,i)=>i===ui.shape?{...s,points:validatePolygon(parsed)}:s);validateShapes(next);commitShapes(next,ui.shape,'Vertices updated.');
 }catch(error){$('shape-points-hint').textContent=error.message+' Vertices unchanged.';points.setAttribute('aria-invalid','true');notice(error.message+' Vertices unchanged.');}};
}
function options(values,current){return values.map(v=>`<option value="${v}" ${v===current?'selected':''}>${v||'Not assigned'}</option>`).join('');}
function issues(){const out=[];for(const b of ['Core','Oxide',...(state.electric===false?[]:['Heater'])])if(!setup.materials[b])out.push(['Materials',b+' material missing']);if(state.electric!==false&&!setup.terminal)out.push(['Electric currents','Terminal / ground pair missing']);if(state.heat&&!setup.cooling)out.push(['Heat transfer','Thermal boundary missing']);if(state.heat&&state.structure&&!setup.fixed)out.push(['Solid mechanics','Mechanical constraint missing']);return out;}
function decorate(){
if(ui.page==='Model'&&pick.mode==='Bodies'&&['Geometry','Materials'].includes(ui.selection)&&!isOptical()){
 const controls=document.createElement('div');controls.className='toolbar';controls.innerHTML=(isOptical()?['Core','Oxide']:['Core','Oxide','Heater']).map(b=>`<button data-body="${b}" aria-pressed="${ui.body===b}">${b}</button>`).join('');$('canvas').prepend(controls);
 controls.querySelectorAll('[data-body]').forEach(b=>b.onclick=()=>{ui.body=b.dataset.body;ui.selection='Materials';render();});
}
let form='';
if(ui.selection==='Materials'&&isOptical()){
 form='<h2>Shape materials</h2>'+state.shapes.map((s,i)=>`<label>${i+1}. ${escapeHtml(s.name)}<select data-shape-material="${i}">${options(SHAPE_MATERIAL_CHOICES,s.material)}</select></label>`).join('')+pair('Background','Silica (SiO2) · fixed')+`<p${shapesBlock(state.shapes)?' class="validation-warning"':''}>${escapeHtml(shapesBlock(state.shapes)||'Indices are evaluated at '+state.wavelength+' nm by the server.')}</p><p>Silicon, silicon nitride, sapphire, lithium niobate, indium phosphide and gallium arsenide lie above the silica index and can guide light; silica, air, calcium fluoride and magnesium fluoride cannot on their own. Sapphire, lithium niobate and magnesium fluoride use their ordinary index as an isotropic material. Thermal and mechanical laws are not assigned here.</p>`;
}else if(ui.selection==='Materials'){
 const allowed=isOptical()?(ui.body==='Core'?['Silicon','Silicon nitride']:['Silica']):['','Silicon','Silica','Silicon nitride','Platinum'];
 const assigned=setup.materials[ui.body];
 const values=allowed.includes(assigned)?allowed:[assigned,...allowed];
 form=`<h2>${ui.body} material</h2><label>Selected body<select id="body-choice">${options(isOptical()?['Core','Oxide']:['Core','Oxide','Heater'],ui.body)}</select></label><label>${isOptical()?'Optical material':'Material label'}<select id="material-choice">${options(values,assigned)}</select></label>`;
 form+=isOptical()?`<p>${allowed.includes(assigned)?'Used by the optical solver at '+state.wavelength+' nm.':'Current assignment is unsupported. Choose a supported material before running.'}</p><p>Core: Silicon (Si) or Silicon nitride (Si3N4). Background: Silica (SiO2). Optical material properties are resolved by the server; thermal and mechanical laws are not assigned here.</p>`:'<p>Setup labels only. Coupled property values, temperature laws and compatibility are not validated.</p>';
}
if(ui.selection==='Electric currents')form=`<h2>Electric currents</h2><label>Applied voltage [V]<input id="setup-voltage" type="number" min="0" max="10" step="0.1" value="${state.voltage}"></label><label>Terminal / ground<select id="terminal">${options(['','Heater start / heater end'],setup.terminal)}</select></label><p>Named end faces are placeholders until CAD selection is connected.</p>`;
if(ui.selection==='Heat transfer')form=`<h2>Heat transfer</h2><label>Thermal boundary<select id="cooling">${options(['','Oxide bottom: fixed temperature'],setup.cooling)}</select></label><label>Boundary temperature [K]<input id="temperature" type="number" min="1" max="2000" step="0.01" value="${setup.temperature}"></label><p>Temperature range is a UI input bound, not material validity.</p>`;
if(ui.selection==='Solid mechanics')form=`<h2>Solid mechanics</h2><label>Fixed support<select id="fixed">${options(['','Left end fixed','Both ends fixed'],setup.fixed)}</select></label><p>Conceptual end selections. Other faces are intended to remain free. Geometry mapping is pending.</p>`;
if(form){$('inspector').innerHTML='<span class="muted">MODEL SETUP</span>'+form+'<p id="input-error" role="alert"></p>';}
const bind=(id,fn)=>{const el=$(id);if(el)el.onchange=()=>{fn(el.value);render();};};bind('body-choice',v=>ui.body=v);document.querySelectorAll('[data-shape-material]').forEach(el=>el.onchange=()=>{state.shapes=state.shapes.map((s,i)=>i===+el.dataset.shapeMaterial?{...s,material:el.value}:s);trackEdit();render();});bind('material-choice',v=>setup.materials[ui.body]=v);for(const key of ['terminal','cooling','fixed'])bind(key,v=>setup[key]=v);
const missing=issues();$('status').textContent=`Design inputs · ${missing.length} setup items missing · solver not connected`;
if(ui.page==='Model'&&ui.selection==='Study'){
 $('canvas').innerHTML='<h2>Setup review</h2><p>Input completeness only · not a numerical preflight</p>'+ (missing.length?missing.map(([node,msg])=>`<div class="pair"><span>${msg}</span><button data-fix="${node}">Configure →</button></div>`).join(''):'<div class="pair"><strong>Required setup labels assigned</strong></div>')+'<h3>Execution blockers</h3><p>CAD face mapping, material properties, mesh, coupling adapters and numerical validation are not implemented. Run remains disabled.</p>';
 $('canvas').querySelectorAll('[data-fix]').forEach(b=>b.onclick=()=>{if(b.dataset.fix==='Materials')ui.body=Object.keys(setup.materials).find(k=>!setup.materials[k])||'Core';select(b.dataset.fix);});
}
}



let pendingLoad=null;
let currentFile=null,fileScope=0,savingFile=false,overflowSaveAs=false;
// The change list of the last Use this run's inputs, shown in the run panel while the edit
// revision is the one it made and its run is the one shown: {text, revision, job} or null.
let runInputsNote=null;
const runInputsNoteFor=run=>runInputsNote&&run&&runInputsNote.revision===edits.revision&&runInputsNote.job===run.job?runInputsNote.text:null;
const workspaceLoads=new LatestWorkspaceLoad(()=>loadContext());
function loadContext(){return JSON.stringify({notebook:notebookStamp(),revision:edits.revision,invalid:numericDrafts.issues,jobOperation,pendingJob:pendingJob?.job||null});}
// resultNotice: the message line announces a completed run; an input edit then replaces it,
// so it does not stay on screen as if it described the edited inputs.
let resultNotice=false;
// more: optional words shown behind More after the line (one short line, the rest on request).
// action: {label, data, run}, a button after the text (e.g. Show Run 1), whose data-* attributes are data
const notice = (text,more='',action=null) => {resultNotice=false;const host=$('file-status');host.textContent = text;
 if(action){const button=document.createElement('button');button.type='button';button.className='message-action';button.textContent=action.label;for(const [k,v] of Object.entries(action.data||{}))button.dataset[k]=v;button.onclick=()=>action.run();host.append(' ',button);}
 if(more){const details=document.createElement('details');details.className='message-more';const summary=document.createElement('summary');summary.textContent='More';const body=document.createElement('span');body.className='message-more-text';body.textContent=more;details.append(summary,body);host.append(' ',details);}};
function announceResult(text,action=null){notice(text,'',action);resultNotice=true;}
// Round 21 (W2): after a result dropped Run N, Messages offers [Keep Run N, drop Run M (…) instead]
// when another unpinned run exists besides the new result (M: the oldest such run). The button works
// until the next run starts or the run list is replaced; a stale one does nothing and is removed.
function swapAction(){
 const offer=dropSwap;if(!offer)return null;
 return {label:keepInsteadLabel(offer.kept,offer.other),data:{keepRun:String(offer.kept.number)},run:()=>keepDroppedRun(offer)};
}
function keepDroppedRun(offer){
 const button=$('file-status').querySelector('[data-keep-run]');
 const fresh=offer===dropSwap&&runs===offer.list&&runs.includes(offer.newest)&&!runs.includes(offer.kept)&&swapCandidate(runs,offer.newest)===offer.other&&!solverBusy&&!pendingJob;
 dropSwap=null;if(!fresh){button?.remove();return;}
 runs=swapDropped(runs,offer.kept,offer.other);if(solverRun===offer.other)solverRun=offer.newest;
 render();notice(keptInsteadText(offer.kept,offer.other));
}
// current(): the model inputs (version 7), as a run keeps them; inputsFile(): those inputs with
// Modes to find and the group index option (version 8 when they are not the defaults), as the
// inputs file, a session, a draft, recovery and the edit history keep them.
const current = () => snapshot(state, setup);
const inputsFile = () => {keepTargetInRange(); return withStudy(current(), {modeCount: state.modeCount, groupIndex: state.groupIndex, openBoundary: state.openBoundary});};
// An edited Search near n_eff that a shape or material edit puts out of range (1.45 < target <
// n_max) goes back to the default of the new design, with a message, so the inputs stay valid.
function keepTargetInRange(){
 const ob=state.openBoundary;if(!ob||ob.target==null)return;
 try{parseTarget(ob.target,state.shapes);}catch{state.openBoundary={...ob,target:null};
  // after the message of the edit that caused it
  const text=`Search near n_eff ${ob.target.toFixed(3)} is outside this design's range: back to the default ${targetText(effectiveTarget(state.openBoundary,state.shapes))}.`;setTimeout(()=>notice(text),0);}
}
const setStudy = doc => Object.assign(state, projectStudy(doc), {openBoundary: projectBoundary(doc)});
// The open boundary of the page as a run's settings hold it ({open_edges, target}), or null.
const pmlNow = () => {if (!isOptical()) return null; keepTargetInRange(); return signaturePml(state.openBoundary, state.shapes);};
// The study a run is compared with: the inputs, Modes to find and the group index option
// (workspace-notebook.mjs studySignature).
// The closed window's Search near n_eff (slice C2): the target while the box is on and the Closed
// window is chosen, else null. A shape or material edit that puts it out of range (1.45 < target <
// n_max) sets it back to the new design's default, with a message. It is a physics setting of the
// page and of each run, not saved with the model inputs (this batch).
function closedTargetNow(){
 if(!isOptical()||state.openBoundary||state.searchTarget==null)return null;
 try{checkClosedTarget(state.searchTarget,state.shapes);}catch{const was=state.searchTarget;state.searchTarget=defaultTarget(state.shapes);
  const text=`Search near n_eff ${was.toFixed(3)} is outside this design's range: back to the default ${state.searchTarget.toFixed(3)}.`;setTimeout(()=>notice(text),0);}
 return state.searchTarget;
}
const signature = () => studySignature(current(), state.modeCount, state.groupIndex, pmlNow(), closedTargetNow());
const inputSignature = () => JSON.stringify(current());
const edits=new WorkspaceStore(inputsFile());
// The title and the footer show one save indicator (persistenceTitle), so they never disagree.
let saveIndicator=null,recoveryState=null,latestOffer=null;
// The inputs a model card gave, until the first edit: the indicator says the model is new, not that edits are unsaved.
let newModelInputs=null;
function refreshPersistence(){
  const clean=!edits.dirty;
  // Results not in a session file outrank a clean input snapshot: saving inputs only
  // must not read as saved while completed runs would be lost.
  const runsUnsaved=runs.length>0&&savedRunsState!==runsStamp();
  // Before an application is chosen there is nothing to save or name.
  if(newModelInputs!==null&&newModelInputs!==signature())newModelInputs=null;const fresh=newModelInputs!==null;
  // the viewed run has other inputs, and none was edited: the title says so on Results and Compare
  // (as the dock and the step bar do); on the Model tab it describes the current inputs only
  const seen=isOptical()&&['Results','Compare'].includes(ui.page)?viewedRun():null,viewed=seen&&clean&&seen.signature!==signature()?{run:runNumber(seen),name:seen.label||''}:null;
  saveIndicator={invalid:numericDrafts.invalid,clean,fresh,runsUnsaved,saved:savedFile()&&{...savedFile(),written:lastSavedFile.written===true},file:currentFileNow()?.name||null,fileHow:currentFileNow()?.how||null,loaded:loadedFrom(),viewed};refreshSaveIndicator();
  refreshNotebook();refreshWorkflow();
}
// The title bar names the project and its file state (P3, projectLine); the footer keeps the shown
// model's own indicator (persistenceTitle), so the two answer different questions.
function refreshProjectLine(){
 const line=projectLine();if($('project').textContent!==line)$('project').textContent=line;
 const file=project.file&&project.file.scope===project.scope?project.file:null,hint=projectHint(file);if(hint)$('project').title=hint;else $('project').removeAttribute('title');
 // the Library is headed by the same line, in its view title row
 if(ui.page==='Applications'&&$('view-detail').textContent!==line)$('view-detail').textContent=line;
}
// round 18 (X8): with a project file and another model in the project, the heated model's status bar
// names the model within the project in the header's words (the header names the project), so the
// two never contradict each other; otherwise (no file, or the heated model alone) it keeps its words
function heatedProjectState(){
 const file=project.file&&project.file.scope===project.scope?project.file:null;if(!file||!multiView.inProject()||projectModels().length<2)return null;
 const key=project.ids.multiphysics,inFile=Array.isArray(file.models)&&key?file.models.some(m=>m.key===key):null;
 return modelInProjectTitle({title:multiView.projectTitle(),file,inFile,current:project.stamp===projectStamp(),recovery:recoveryState==='kept'&&multiView.recoveryDropped()?'kept:'+multiView.recoveryDropped():recoveryState});
}
function refreshSaveIndicator(){
 refreshProjectLine();
 if(multiView.active()){const state=heatedProjectState()||multiView.saveState();if($('autosave-status').textContent!==state)$('autosave-status').textContent=state;downloadHint(multiView.saveHint());return;}
 const text=saveIndicator&&persistenceTitle({...saveIndicator,recovery:opticalRecoveryShown()});downloadHint(applicationChosen()&&saveIndicator?persistenceHint({...saveIndicator,recovery:recoveryState}):'');
 // Rewritten only on a change: the footer is a status region read out by screen readers.
 const footer=applicationChosen()&&text?text:latestOffer?`Last session kept in this browser · ${latestOffer.model?latestOffer.model+' · ':''}${latestOffer.runs} ${latestOffer.runs===1?'run':'runs'}`:recoveryState==='unavailable'?'No model chosen · browser recovery unavailable':'No model chosen · nothing to save yet';
 if($('autosave-status').textContent!==footer)$('autosave-status').textContent=footer;
}
// the title text of the header and the footer on the download path (round 14), removed elsewhere
function downloadHint(hint){const el=$('autosave-status');if(hint)el.title=hint;else el.removeAttribute('title');}
function refreshWorkflow(){
 const host=$('workflow');host.hidden=!isOptical()||ui.page==='Applications';if(host.hidden)return;
 const steps=opticalWorkflow({input:current(),modeCount:state.modeCount,groupIndex:state.groupIndex,pml:pmlNow(),searchTarget:closedTargetNow(),invalid:numericDrafts.invalid,block:opticalBlock()||retentionBlock(),busy:solverBusy,pending:!!pendingJob,resumeBlocked:jobResumeBlocked,mesh:meshPreview.record,runs,viewed:viewedRun()});
 steps.forEach((step,index)=>{
  let button=host.querySelectorAll('.workflow-step')[index];if(!button){button=document.createElement('button');button.type='button';button.className='workflow-step';button.append(document.createElement('strong'),document.createElement('span'));button.onclick=()=>{if(step.id==='Results'){ui.page='Results';render();}else select(step.id);};host.append(button);}button.dataset.state=step.state;if(step.tone)button.dataset.tone=step.tone;else delete button.dataset.tone;
  const selected=step.id==='Results'?ui.page==='Results':ui.page==='Model'&&ui.selection===step.id;
  if(selected)button.setAttribute('aria-current','step');else button.removeAttribute('aria-current');
  button.children[0].textContent=`${index+1}. ${step.id}`;button.children[1].textContent=step.wavelength?step.summary:step.detail;
  // The wavelength of the Study step is its own control: it opens the wavelength field.
  if(step.id==='Study'){let chip=$('workflow-wavelength');if(!chip){chip=document.createElement('button');chip.type='button';chip.id='workflow-wavelength';chip.className='workflow-wavelength';chip.title='Edit the wavelength (Physics › Optical modes)';chip.onclick=()=>editWavelengthField();button.after(chip);}chip.hidden=!step.wavelength;chip.textContent=step.wavelength||'';chip.setAttribute('aria-label',`Wavelength ${step.wavelength?step.wavelength.slice(2):''}, edit`);}
 });
}
function rejectInvalidInput(){
  numericDrafts.assertValid();if(heatDrafts.size)throw new Error('Correct or restore the highlighted heat inputs before saving or opening files.');
  if(jouleView.hasDrafts())throw new Error('Correct or restore the highlighted Joule inputs before saving or opening files.');
}
function applyProject(doc,{saved=true,resetHistory=false,quiet=false}={}){
  fileScope++;
  doc=edits.replace(doc,{saved,resetHistory});workspaceLoads.invalidate();numericDrafts.clear();heatDrafts.clear();heatController?.invalidate();jouleView.reset();
  pick.boundary=null;pick.mode='Bodies';Object.assign(state,doc.model);setStudy(doc);Object.assign(ui,{page:'Model',selection:'Study',view:'Section'});
  Object.assign(setup,doc.setup);ui.body='Core';
  checkpointRecovery();render();updateHistory();refreshPersistence();
  if(!quiet)notice('Model inputs restored. Results and CAD geometry are not included.');
}
// The inputs a fresh workspace starts with; an open over them (and no results) asks nothing.
const DEFAULT_INPUTS=current();
const applicationChosen=()=>state.electric!==undefined;
function requestLoad(doc,options={}){
  if(multiView.busy()){notice('Wait for the multiphysics run to finish, or stop it under Study.');return;}
  if(!options.opener)options={...options,opener:document.activeElement};
  // a file opened with File › Open replaces the project (P3): the models whose runs no file holds
  // are named first, and the open question is not asked again after that question
  if(options.newProject&&!options.projectChecked){const asked=!!leaveText(options.label||'the opened inputs');guardLeave(options.label||'the opened inputs',false,()=>requestLoad(doc,{...options,projectChecked:true,leaveChecked:asked}));return;}
  loadInputs(doc,options);
}
function loadInputs(doc,{saved=true,session=null,source='file',label='Saved inputs',recoveryRecord=null,recoveryIndex=null,keepAsLatest=false,savedFile=null,openedFile=null,openedCurrent=null,page=null,opener=document.activeElement,leaveChecked=false,fileName=null,newProject=false,then=null,projectMatched=false,recordProject=null,recordSavedAt=null}={}){
  workspaceLoads.invalidate();
  pendingLoad={input:doc,saved,session,source,label,recoveryRecord,recoveryIndex,keepAsLatest,savedFile,openedFile,openedCurrent,page,opener,fileName,newProject,then,projectMatched,recordProject,recordSavedAt,context:loadContext()};
  // Nothing to lose: no runs or other results and the default inputs, so open at once.
  // leaving a multiphysics run was just confirmed: the hidden optical inputs are not asked about again
  if(leaveChecked||untouchedWorkspace(inputsFile(),DEFAULT_INPUTS,{results:runs.length+(heatRun||heatState.busy?1:0)+(jouleView.hasResult()||jouleView.busy()?1:0)})){const pending=pendingLoad;pendingLoad=null;completeLoad(pending);return;}
  const text=session?sessionLoadText(session,{runs:runs.length,unsaved:runs.length>0&&savedRunsState!==runsStamp()},source):null;
  $('load-confirm').querySelector('h2').textContent=text?text.title:'Replace current inputs?';
  $('load-confirm').querySelector('p').textContent=text?text.description:'Save your current design first if you want to keep it.';
  $('confirm-load').textContent=text?text.button:'Replace inputs';
  const summary=$('load-summary');summary.replaceChildren();
  const entries=[['Source',label],...(text?[['Runs that come back',text.runs],['Comparison',text.comparison]]:[]),['Physics',`${physicsList(current().model,applicationChosen())} → ${physicsList(doc.model)}`],['Geometry',`${designSummary(current().model)} → ${designSummary(doc.model)}`],['Optical study',`λ ${state.wavelength} nm, core mesh ${state.coreMesh} nm → λ ${doc.model.wavelength} nm, core mesh ${doc.model.coreMesh} nm`],['Completed results',session?`${runs.length} now → ${session.runs.length} from the session`:`Keep ${runs.length} retained runs`],['Input Undo',session?'Starts at the opened session':'Replacement can be undone'],
   // a file replaces the project: the models that leave it are named (P3)
   ...(newProject&&multiView.inProject()?[['Project',`${projectModels().map(m=>m.title).join(' and ')} → an untitled project of the opened model`]]:[])];
  for(const [name,value] of entries){const term=document.createElement('dt'),detail=document.createElement('dd');term.textContent=name;detail.textContent=value;summary.append(term,detail);}
  if(!$('load-confirm').open)$('load-confirm').showModal();
}
const dialog=document.createElement('dialog');dialog.id='load-confirm';dialog.setAttribute('aria-labelledby','load-confirm-title');dialog.setAttribute('aria-describedby','load-confirm-description');
dialog.innerHTML='<h2 id="load-confirm-title">Replace current inputs?</h2><p id="load-confirm-description">Save your current design first if you want to keep it.</p><dl id="load-summary" class="load-summary"></dl><button id="cancel-load">Keep current</button> <button id="confirm-load">Replace inputs</button>';
document.body.append(dialog);
function restoreDialogFocus(opener){if(opener?.isConnected&&!opener.disabled)opener.focus({preventScroll:true});}
function cancelLoad(){const opener=pendingLoad?.opener;pendingLoad=null;workspaceLoads.invalidate();dialog.close();restoreDialogFocus(opener);notice('Open cancelled. Current inputs kept.');}
$('cancel-load').onclick=cancelLoad;
dialog.oncancel=event=>{event.preventDefault();cancelLoad();};
$('confirm-load').onclick=()=>{
 const pending=pendingLoad;pendingLoad=null;workspaceLoads.invalidate();dialog.close();if(!pending)return;
 if(pending.context!==loadContext()){notice('Workspace changed while reviewing the replacement. Open it again; current inputs and results kept.');return;}
 completeLoad(pending);
};
function completeLoad(pending){
 if(pending.multiphysics){pending.multiphysics();return;}
 if(!leaveMultiphysics())return;
 // a file opened with File › Open: an untitled project holding that one model (P3); a browser
 // restore or a draft replaces the workspace inputs inside the project
 if(pending.newProject){multiView.discard();resetProject();}
 projectId('workspace');
 if(pending.session){
  if(pending.source==='browser'){notebookStore.adopt(pending.recoveryRecord,{kept:pending.keepAsLatest});restoredFrom(pending.recoveryIndex);}
  const session=pending.session;runs=session.runs;for(const r of runs){const n=r.number;delete r.number;if(Number.isInteger(n))r.number=n;}runNumbersUsed=numberRuns(runs);solverRun=runs.find(r=>r.job===session.selected)||runs.at(-1)||null;compareIds=[...session.comparison];comparePicked=pairChosen(runs,compareIds);restoreView(session.view);
  // Modes to find and the group index option: those of an input of version 8; for an input of
  // version 6 or 7 (a file that did not store them), those of the selected run, as before
  const input=sessionStudyInput(session.input,solverRun);
  // A recovered notebook that still matched its saved file, or the file it was opened from, reads
  // as saved, as the file would.
  const file=pending.source==='file'?null:pending.savedFile,openedMatch=pending.source!=='file'&&!!pending.openedFile&&pending.openedCurrent===true,matched=file?.current===true||openedMatch;
  // before the render that schedules the first recovery save, so that record names the file (the
  // record's file is not part of the save stamp: set later, it would wait for the next change)
  openedFile=pending.source==='file'?pending.label:pending.openedFile||null;
  applyProject(input,{saved:pending.saved||matched,resetHistory:true});
  // the page a recovery record names (Results, Compare or Model), when its runs allow it; else
  // Compare for two runs or more, Results for one (a session file names no page)
  ui.page=restorePage(pending.page,runs.length);
  if(ui.page!=='Model'&&ui.selection==='Study')ui.selection='Geometry';
  render();
  savedNotebookState=pending.source==='file'||matched?notebookStamp():null;savedRunsState=pending.source==='file'||matched?runsStamp():null;
  // a record without a session file belongs to a notebook never saved: no file name carries over
  lastSavedFile=file?{name:file.name,savedAt:file.savedAt,stamp:file.current===true?saveStamp():null,recovered:true,...(file.projectName?{projectName:file.projectName}:{})}:null;
  // the title says what is open until the next change: the file opened, or browser recovery
  // file: the session file the notebook came from (opened, or named by the recovered record), and
  // whether the record said it still matched it
  newModelInputs=null;loadedSession={kind:pending.source==='file'?'opened':'recovered',name:pending.source==='file'?pending.label:null,stamp:saveStamp(),file:pending.source==='file'?pending.label:pending.openedFile||null,fileCurrent:pending.source==='file'||openedMatch};
  openedStamp=pending.source==='file'||openedMatch?saveStamp():null;
  rememberOpened(pending.fileName);if(pending.source!=='file'){rememberOpened(recoveredFileName(file,pending.openedFile,pending.openedCurrent),'recovered');restoreProjectFile(file,pending.openedFile,{matched:pending.projectMatched===true});restoreProjectName(pending.recordProject,{savedFile:file,openedFile:pending.openedFile,openedCurrent:pending.openedCurrent,savedAt:pending.recordSavedAt});}refreshPersistence();
  // the runs keep the numbers the session stored (version 12), else are numbered by their place in
  // the file, which Studio writes only when that numbering is exact: nothing is said about numbering
  // (HQ decision 2026-11-24-openphysics-studio-session-v12-k10-amended)
  notice((pending.source==='file'?`Opened ${pending.label}. Its results were read from the file, not recomputed; input undo starts here.`:`Recovered from this browser (${pending.label}), not recomputed. `+(file?`Last session file ${file.name}${matched?'':'; changed since'}. Input undo starts here.`:'File › Save keeps it in a file; input undo starts here.')));
  // round 23 (E2): a browser restore names the runs that came back without fields
  if(pending.source!=='file'&&pending.session){const missing=fieldsNotKeptText(runs);if(missing)$('file-status').append(missing);}
  pending.then?.();
 }else{loadedSession=null;newModelInputs=null;applyProject(pending.input,{saved:pending.saved});rememberOpened(pending.fileName);refreshPersistence();notice(`Model inputs restored · ${pending.label}. Results and CAD geometry are not included.`);}
}
$('save-project').onclick=()=>{if(multiView.active()){multiView.saveInputs();return;}try{
  rejectInvalidInput();const doc=inputsFile();const blob=new Blob([JSON.stringify(doc,null,2)+'\n'],{type:'application/json'});
  const name=modelFileName(applicationSlug());downloadFile(blob,name);
  edits.record(doc);edits.markSaved();newModelInputs=null;refreshPersistence();notice(`Model file ${name} sent to your browser's Downloads. It has the inputs but no computed results`+(runs.length?'; File › Save keeps the runs too, in the project file.':'.'));
}catch(e){notice(e.message);}};
// A model file: an optical, heat or Joule heating inputs file, or a multiphysics model. File ›
// Open (the session file input) sends model files here.
$('project-file').onchange=event=>{const file=event.target.files[0];event.target.value='';if(file)openModelFile(file);};
async function openModelFile(file){try{
 // a multiphysics document opens as a multiphysics model; any document opens in one that is open
 if(file.size<=(1<<20)){const text=(await file.text()).replace(/^\uFEFF/,'');let tree=null;try{tree=JSON.parse(text);}catch{}
  if(tree&&typeof tree==='object'&&!Array.isArray(tree)&&(tree.openphysics===ENVELOPE||(multiView.active()&&typeof tree.openphysics==='string'))){if(multiView.busy())throw new Error('Wait for the multiphysics run to finish.');
   guardLeave(file.name,false,()=>{openingModel=true;fileScope++;multiView.openText(text,file.name).then(()=>{multiphysicsProject();rememberOpened(file.name);}).catch(e=>notice('Open failed: '+e.message+(multiView.active()?' The current model and its runs are kept.':' Current inputs kept.'))).finally(()=>{openingModel=false;});});return;}}
 const loaded=await workspaceLoads.read(async()=>{if(file.size>MAX_BYTES)throw new Error('Model file exceeds 64 KiB.');return parseProject((await file.text()).replace(/^\uFEFF/,''));});
 if(loaded)requestLoad(loaded.value,{label:file.name,fileName:file.name,opener:$('open-session'),newProject:true});
}catch(e){notice('Open failed: '+e.message+' Current inputs kept.');}}
// A multiphysics model or session file opened with File › Open: an untitled project holding that
// one model (P3); the workspace and its runs leave the tab, after the leave question named them.
function multiphysicsProject(){clearWorkspace();resetProject();projectId('multiphysics');render();refreshPersistence();}
$('save-draft').onclick=()=>{try{rejectInvalidInput();const doc=inputsFile();localStorage.setItem(DRAFT_KEY,JSON.stringify(doc));edits.record(doc);edits.markSaved();newModelInputs=null;refreshPersistence();notice('Draft saved in this browser. Use Restore draft after reloading.');}catch(e){notice('Draft not saved: '+e.message);}};
$('restore-draft').onclick=()=>{try{rejectInvalidInput();const text=localStorage.getItem(DRAFT_KEY);if(!text)throw new Error('No draft saved in this browser.');requestLoad(parseProject(text),{label:'Browser draft'});}catch(e){notice('Restore failed: '+e.message+' Current inputs kept.');}};


let recoverable=null;
function showRecovery(){
 $('recover-inputs').disabled=!recoverable;
 $('recovery-status').textContent=recoverable?'Recent valid inputs available ('+new Date(recoverable.savedAt).toLocaleString()+'). Results and invalid drafts are not included.':'Valid input changes are kept automatically for recovery in this browser. Use File › Save for a file with the results.';
}
function checkpointRecovery(){
 try{writeRecovery(localStorage,inputsFile());recoverable=readRecovery(localStorage);showRecovery();}
 catch(error){$('recovery-status').textContent='Automatic input recovery unavailable: '+error.message+' Use File › Save, or File › Export › Model file.';}
}
try{recoverable=readRecovery(localStorage);showRecovery();}catch(error){$('recovery-status').textContent='Recovery could not be read: '+error.message+' Current inputs kept.';}
$('recover-inputs').onclick=()=>{try{rejectInvalidInput();if(recoverable)requestLoad(recoverable.input,{saved:false,label:'Recent valid inputs'});}catch(error){notice(error.message);}};

function updateHistory(){ $('undo-edit').disabled=multiView.active()?!multiView.canUndo():!edits.canUndo;$('redo-edit').disabled=multiView.active()?!multiView.canRedo():!edits.canRedo; }
function trackEdit(group=null){if(multiView.active())return;const before=edits.signature;edits.record(inputsFile(),group);if(edits.signature!==before){checkpointRecovery();inputsChangedSinceResult();offerDue=true;}updateHistory();refreshPersistence();}
// Round 18 (X1): an edit, Undo or Redo that leaves the current inputs and study settings equal to a
// run's (its signature: geometry, materials, wavelength, mesh, Modes to find, group index, boundary
// and search targets) says so after the edit's own message, in the heated model's words, with Show
// Run N. Run study still runs if pressed. Called after the edit's message, which it follows: an edit
// sets offerDue, and the change or click that commits it (after the field's own message) asks; an
// earlier offer on the line is replaced, so typing never repeats it.
let offerDue=false;
function offerMatchingRun(){
 offerDue=false;const host=$('file-status');host.querySelector('#match-offer')?.remove();
 if(multiView.active()||!applicationChosen()||!isOptical()||numericDrafts.invalid||solverBusy)return;
 const sig=signature(),run=runs.findLast(r=>r.signature===sig);if(!run)return;
 const offer=document.createElement('span');offer.id='match-offer';
 const show=document.createElement('button');show.type='button';show.className='message-action';show.textContent=`Show Run ${runNumber(run)}`;show.dataset.showRun=String(runNumber(run));
 show.onclick=()=>{if(!runs.includes(run))return;solverRun=run;ui.page='Results';render();notice(`${runNumberTitle(run)} shown under Results; the inputs are unchanged.`);};
 // round 20 (Z1): the edit's request to run would contradict it: it is taken off, the edit's own
 // sentence stays (the generic "run again" line, which has none, leaves the offer alone)
 host.textContent=matchingRunMessage(host.textContent);
 offer.append((host.textContent?' ':'')+matchesAgainText(runNumber(run),run.label||'')+'. ',show);host.append(offer);
}
const INPUTS_CHANGED_TEXT='Inputs changed since the last result. Run again to compute the new inputs.';
function inputsChangedSinceResult(){
 if(resultNotice)notice(INPUTS_CHANGED_TEXT);
 if(jobPhase==='done'){jobPhase='idle';$('job-message').textContent='';refreshJobControls();}
}
// A run's inputs as the current inputs (Use this run's inputs), with its Modes to find and group
// index option: one input edit, so Undo takes all three back and Redo applies them again. The
// runs and the page stay as they are.
function useRunInputs(run){
 if(multiView.active()||!runs.includes(run))return;
 if(numericDrafts.invalid){notice('Correct or restore the highlighted inputs first.');return;}
 const prior=inputsFile(),priorTarget=closedTargetNow(),doc=edits.replace(withStudy(run.input,{modeCount:runModeCount(run),groupIndex:run.group_index_method!==undefined,openBoundary:runChoice(run)}));workspaceLoads.invalidate();newModelInputs=null;
 // slice C2: the closed window's Search near n_eff is not in the inputs file; the run's comes back with it (on and its target, or off)
 // round 22 (V1, V6): named as Modes to return; the target is set here and is not part of Undo, so
 // the message does not say that Undo takes it back
 const runTarget=runSearchTarget(run),returned=t=>t==null?'highest n_eff':'nearest to '+shortTarget(t),targetChange=priorTarget===runTarget?[]:[`Modes to return ${returned(priorTarget)} → ${returned(runTarget)}`];
 // only the settings that change, from → to (round 13); the same words stay where the button was
 // until the next input edit (round 14), so they are kept before the redraw
 const inputs=inputChanges(prior,doc),changed=[...inputs,...targetChange];
 const undo=!targetChange.length?'The next run uses them; Undo takes them back.':inputs.length?`The next run uses them; Undo takes back the other inputs. ${TARGET_NOT_UNDONE}`:`The next run uses it. ${TARGET_NOT_UNDONE}`;
 const text=`Current inputs set from ${runNumberTitle(run)}: ${changed.length?changed.join(' · '):'no listed setting changes'}. ${undo}`;
 runInputsNote={text,revision:edits.revision,job:run.job};
 restoreEdit(doc,null);state.searchTarget=runTarget;inputsChangedSinceResult();render();notice(text);
}
// round 22 (V6): Use this run's inputs sets the closed window's Modes to return, which Undo does not change
const TARGET_NOT_UNDONE='Modes to return is set and is not part of Undo.';
const runNumberTitle=run=>runTitle(runNumber(run),run.label||'');
// label null: no notice (the caller says what happened)
function restoreEdit(doc,label){
 numericDrafts.clear();heatDrafts.clear();heatController?.invalidate();jouleView.clearDrafts();
 Object.assign(state,doc.model);setStudy(doc);Object.assign(setup,doc.setup);pick.boundary=null;
 checkpointRecovery();render();updateHistory();refreshPersistence();if(label!==null)notice(label+' · input changes only; no solver executed.');
}
$('undo-edit').onclick=()=>{if(multiView.active())multiView.undo();else{restoreEdit(edits.undo(),'Undo');offerMatchingRun();}};
$('redo-edit').onclick=()=>{if(multiView.active())multiView.redo();else{restoreEdit(edits.redo(),'Redo');offerMatchingRun();}};
document.addEventListener('input',event=>trackEdit(event.target));
document.addEventListener('change',()=>{trackEdit();edits.endGroup();if(offerDue)setTimeout(offerMatchingRun,0);});
document.addEventListener('click',()=>{trackEdit();edits.endGroup();if(offerDue)setTimeout(offerMatchingRun,0);});
document.addEventListener('focusout',()=>edits.endGroup());
document.addEventListener('keydown',event=>{
 if(!(event.ctrlKey||event.metaKey)||event.altKey||document.querySelector('dialog[open]'))return;
 // File › Open (Ctrl+O), Save (Ctrl+S) and Save As (Shift+Ctrl+S), also from a text field: run
 // inside this key press, so the save picker may open
 const fileKey=event.key.toLowerCase();
 if(fileKey==='o'&&!event.shiftKey||fileKey==='s'){event.preventDefault();if(event.repeat)return;
  // a text field commits its value on change: blur it first, so the file holds what is shown
  if(document.activeElement?.matches('input,textarea,select'))document.activeElement.blur();
 const item=$(fileKey==='o'?'menu-open':event.shiftKey?'menu-save-as':'menu-save');if(!item.disabled)item.click();else notice('Fix or discard the invalid inputs first.');return;}
 if(event.target.closest('input,textarea,select,[contenteditable="true"]'))return;
 const canUndo=multiView.active()?multiView.canUndo():edits.canUndo,canRedo=multiView.active()?multiView.canRedo():edits.canRedo;
 if(event.key.toLowerCase()==='z'){event.preventDefault();if(event.shiftKey){if(canRedo)$('redo-edit').click();}else if(canUndo)$('undo-edit').click();}
 else if(event.key.toLowerCase()==='y'){event.preventDefault();if(canRedo)$('redo-edit').click();}
});

// The run Results shows (the selected run), which the dock, the footer, the step bar and the title describe.
function viewedRun(){return runs.includes(solverRun)?solverRun:null;}
// comparePicked: the pair was picked on Compare (or read as chosen from a file), so new runs keep it (round 16)
let solverBusy=false,solverRun=null,runs=[],compareIds=[null,null],comparePicked=false;
// the largest run number used in this tab (round 17, U2: workspace-workflow.mjs numberRuns)
let runNumbersUsed=0;
// the message of the runs a new run dropped (the run limit), said after the run's own message
// round 21 (W2): the drop the last result made, for its Messages line; dropSwap: the swap that line
// offers (Keep Run N, drop Run M instead), in memory only, until the next run starts or the run list is replaced
let droppedNote='',dropSwap=null;const fieldView={mode:0,component:'magnitude',window:'Core region'};const fieldProbe={x:0,y:.15,active:false};let savedNotebookState=null,savedRunsState=null;
let notebookRecoveryRecord=null,notebookLoadVersion=0;
// The last session file saved (or recovered as saved): {name, savedAt, stamp}; stamp is the
// inputs and runs it held, so the title shows it as saved until the next edit or run.
let lastSavedFile=null;
// What the title names until the next change: {kind: 'opened' | 'recovered', name, stamp}.
let loadedSession=null;
// The session file these optical runs were opened from (or that a recovered record names), by
// name: browser recovery keeps it so its lists can name the file.
let openedFile=null;
const loadedFrom=()=>loadedSession?{kind:loadedSession.kind,name:loadedSession.name,current:loadedSession.stamp===saveStamp(),file:loadedSession.file,fileCurrent:loadedSession.fileCurrent}:null;
// What a session file is "the same as" for the title: the model inputs and the runs (their names
// and pins). The selected run, the Compare choice and the field view are left out: a click on a
// run, a page or a mode does not make the notebook differ from its file.
const saveStamp=()=>JSON.stringify({input:workspaceInputs(),runs:runs.map(runStampEntry)});
// The content stamp when the notebook was opened from openedFile (or recovered while it still
// matched it); null when no file was opened. Browser recovery keeps whether it still matches.
let openedStamp=null;
const openedCurrent=()=>openedFile?openedStamp!==null&&openedStamp===saveStamp():null;
// The page a recovery record names: the last of Model, Results and Compare shown (Connections
// counts as Model), so a restore opens the same view.
let recordedPage=null;
const pageForRecord=()=>{if(['Model','Results','Compare'].includes(ui.page))recordedPage=ui.page;else if(ui.page==='Connections')recordedPage='Model';return recordedPage;};
const savedFile=()=>lastSavedFile?{name:lastSavedFile.name,savedAt:lastSavedFile.savedAt,current:lastSavedFile.stamp===saveStamp(),recovered:lastSavedFile.recovered===true,...(lastSavedFile.projectName?{projectName:lastSavedFile.projectName}:{})}:null;
const applicationSlug=()=>isOptical()?'optical-waveguide':isHeat()?'heat-conduction':isJoule()?'joule-heating':state.electric===undefined?'workspace':'multiphysics';
// Browser recovery also keeps the last saved file, so its stamp includes it.
const autosaveStamp=()=>notebookStamp()+JSON.stringify([savedFile(),openedCurrent(),pageForRecord(),recordProjectNow()]);
const notebookStore=indexedNotebookStore();
// the note of the last recovery snapshot kept without the study settings (shown once in the message line)
let recoveryNote='';
// round 23 (E2): the numbers of the runs whose fields the last optical recovery snapshot left out
// (over 16 MiB it keeps the selected and pinned runs' fields and as many others as fit, newest
// first): the header and the indicator say "kept for recovery in this browser without the fields of
// Run 3 and Run 5"
let opticalRecoveryDropped=[];
const opticalRecoveryShown=()=>recoveryState==='kept'&&!multiView.active()&&opticalRecoveryDropped.length?'keptFields:'+opticalRecoveryDropped.join(','):recoveryState;
// round 18 (X4): the off state Messages last named, posted once until recovery works again; after a
// run's result message the line is added to it, so the result stays in view
let recoveryOffPosted=null;
function postRecoveryOff(){
 const text=recoveryOffText(recoveryState);if(!text||recoveryOffPosted===recoveryState)return;recoveryOffPosted=recoveryState;
 const host=$('file-status');if(resultNotice&&host.textContent){host.append(' '+text);}else notice(text);
}
// S2 (field size of open runs): a new run that makes the session go over 16 MiB adds one line after
// the run's message: the size and what File › Save will ask or refuse. When Save refuses, browser
// recovery is off too and the line says so, so X4's line for that state is not posted again.
let sessionSizePending=false;
function postSessionSize(){
 sessionSizePending=false;if(!runs.length)return;
 // round 23 (E2): the runs whose fields browser recovery leaves out, named as its snapshot names them
 let text=null;try{const make=captureSession(inputsFile(),runs,solverRun?.job||null,compareIds,currentView());let left=null;try{make();left=make.dropped;}catch{}
  text=sessionSizeText(writeOpticalSession(inputsFile(),runs,solverRun?.job||null,compareIds,currentView()),left);}catch{return;}
 if(!text)return;if(text.endsWith(' Browser recovery is off.'))recoveryOffPosted='overLimit';
 const host=$('file-status');if(resultNotice&&host.textContent){host.append(' '+text);}else notice(text);
}
const notebookAutosave=new NotebookAutosave(notebookStore,{onState:state=>{
 // The save indicator reads "updating", not "pending": right after Save session it would read as if the save were not done.
 if(state.phase==='pending'||state.phase==='saving')recoveryState='updating';
 if(state.phase==='current'){recoveryState='kept';recoveryOffPosted=null;}
 if(state.phase==='saved'){recoveryState='kept';recoveryOffPosted=null;opticalRecoveryDropped=recoveryKind==='optical'&&Array.isArray(state.dropped)?state.dropped:[];notebookRecoveryRecord=state.record;notebookLoadVersion++;const first=!ownLatest;ownLatest=true;const restored=restoredIndex!==null;restoredIndex=null;if(notebookStore.movedEarlier()||first||restored)renderEarlierSessions();$('recover-notebook').disabled=false;$('retry-notebook').disabled=true;$('notebook-recovery-detail').textContent='Browser recovery updated '+new Date(state.record.savedAt).toLocaleTimeString()+'. Latest completed session kept in this browser for this server address; shared across tabs. Use File › Save for a file you can keep.'+(state.note?' '+state.note:'');if(state.note&&state.note!==recoveryNote)notice(state.note);recoveryNote=state.note;}
 if(state.phase==='error'){recoveryState=state.code==='recovery-conflict'?'conflict':state.code==='recovery-over-limit'?'overLimit':state.code==='recovery-quota'?'quota':'unavailable';$('retry-notebook').disabled=false;$('notebook-recovery-detail').textContent=state.message+' Use current notebook for recovery to review an explicit replacement. Previous completed snapshot is retained if the database transaction failed.';postRecoveryOff();}
 refreshSaveIndicator();
}});
async function loadNotebookRecovery(){
 const version=notebookLoadVersion;
 try{const record=await notebookStore.load();const recovered=readNotebookRecovery(record);if(version!==notebookLoadVersion)return;notebookStore.adopt(record);notebookRecoveryRecord=record||null;ownLatest=false;$('recover-notebook').disabled=!recovered;$('retry-notebook').disabled=true;
  latestOffer=recovered?{runs:recovered.session.runs.length,savedAt:recovered.savedAt,model:recoveredModel(recovered),entry:recoveredEntry(recovered),recovered}:null;
  if(recovered){$('notebook-recovery-detail').textContent='Saved '+new Date(recovered.savedAt).toLocaleString()+'. Restore last session from this browser brings back inputs and completed results. Latest snapshot is shared across tabs on this origin.';}
  refreshSaveIndicator();
  await renderEarlierSessions();
  if(ui.page==='Applications')render();
 }catch(error){if(version!==notebookLoadVersion)return;recoveryState='unavailable';refreshSaveIndicator();$('notebook-recovery-detail').textContent=error.message;$('retry-notebook').disabled=false;}
}
// The model a recovered multiphysics session names in the footer; null for optical ones.
const recoveredModel=recovered=>recovered.session.application==='multiphysics'?String(recovered.session.document.name||'Multiphysics model'):null;
// A recovered session as the recovery lists name it: every entry names its model and its runs.
// file: the session file the list names for the entry (distinctRecords), else the record's own.
// file: the session file the entry names; fileCurrent whether this record still matched it (null
// when the record does not say, or the file comes from an older merged record)
// fileSavedAt: when that file was saved, for a file this record was saved to (an opened file has
// no save time here)
const recoveredEntry=(recovered,file)=>{const own=recovered.savedFile?.name||recovered.openedFile||null,name=file||own,
 fileCurrent=name&&name===own?(recovered.savedFile?recovered.savedFile.current:recovered.openedCurrent):null,
 fileSavedAt=name&&recovered.savedFile?.name===name?recovered.savedFile.savedAt:null;
 const also=name?projectAlso(recovered,name):[];
 return {runs:recovered.session.runs.length,savedAt:recovered.savedAt,model:recoveredModel(recovered)||'Optical waveguide',names:sessionRunNames(recovered.session),file:name,fileCurrent,...(fileSavedAt?{fileSavedAt}:{}),...(also.length?{also}:{})};};
// round 18 (X7): the other model of the same project file, when browser recovery holds a record of
// it under that file name (the newest), with its runs; inTab when this tab already holds that model's runs
const entryFile=e=>e.file||e.recovered.savedFile?.name||e.recovered.openedFile;
function projectAlso(recovered,name){
 const kind=recovered.session.application==='multiphysics'?'multiphysics':'optical';
 const other=recoveryList().find(e=>(e.recovered.session.application==='multiphysics'?'multiphysics':'optical')!==kind&&(e.file||e.recovered.savedFile?.name||e.recovered.openedFile)===name);
 if(!other)return [];const o=other.recovered,inTab=kind==='optical'?multiView.projectRuns()>0:runs.length>0;
 // round 19 (Y1): "(already in this tab)" names the runs the tab holds, not the stored record's
 const tab=!inTab?null:kind==='optical'?multiView.runs().map(r=>runTitle(r.number,r.label||'')):runs.map(r=>runTitle(r.number,r.label||''));
 // round 20 (Z2): which record it is, to restore it after this one (found again then: indices move)
 return [{model:recoveredModel(o)||'Optical waveguide',names:tab||sessionRunNames(o.session),runs:tab?tab.length:o.session.runs.length,inTab,
  record:{application:o.session.application,savedAt:o.savedAt,file:name,runs:o.session.runs.length}}];
}
// Earlier sessions: what browser recovery held when an earlier page started new work.
// earlierRecords: the stored records as read, for the list's de-duplication (distinctRecords).
let earlierSessions=[],earlierRecords=[];
// ownLatest: this tab has written the latest record, so it is the tab's own session, not one to
// recover; it still hides an earlier copy of the same text.
let ownLatest=false;
// The stored sessions the lists offer, each once and newest first: {kind, index, recovered, file}.
// restoredIndex (round 19, Y1): the record just restored into this tab (-1: the latest), left out of
// the lists until this tab's own record of it is written (which then hides its copies)
let restoredIndex=null;
function recoveryList(){
 const parsed=new Map(earlierSessions.map(e=>[e.index,e.recovered]));
 return distinctRecords(notebookRecoveryRecord,earlierRecords).filter(e=>e.index!==restoredIndex).flatMap(({index,file})=>{
  if(index<0)return latestOffer&&!ownLatest?[{kind:'latest',index,recovered:latestOffer.recovered,file}]:[];
  return parsed.has(index)?[{kind:'earlier',index,recovered:parsed.get(index),file}]:[];
 });
}
// Each model card's record: the newest session of its model with runs in browser recovery, offered
// before Start new while this tab holds none of that model's runs (workspace-applications.mjs
// cardRecords): the Optical waveguide card for optical sessions, the Heated silicon waveguide card
// for multiphysics ones.
function cardRecordMap(){
 const busy=new Set([...(runs.length?['optical']:[]),...(multiView.projectRuns()?['heated-waveguide']:[])]);
 const list=recoveryList().filter(e=>e.recovered.session.runs.length).map(e=>({...e,application:e.recovered.session.application}));
 return cardRecords(list,busy);
}
// the newest stored session with runs (round 19, Y1): a card offering another one says "older"
const newestRecord=()=>recoveryList().find(e=>e.recovered.session.runs.length)||null;
function cardResumeOffers(){
 const out={},newest=newestRecord();
 for(const [card,found] of Object.entries(cardRecordMap())){const entry=recoveredEntry(found.recovered,found.file);
  out[card]={...cardResumeChoice(entry,entry.model,undefined,{older:!!newest&&newest.index!==found.index}),record:found.index,onResume:button=>found.kind==='latest'?recoverLatest(button):recoverEarlier(found.index,button),onStartNew:()=>chooseTemplate(card)};}
 return out;
}
// The landing page offers to resume until the page has runs or the user starts new.
let resumeDismissed=false;
// Round 19 (Y1): every stored session, newest first, the newest with runs leading (resumeChoices);
// a card repeats its model's newest. Still hidden while the tab holds optical runs.
function resumeOffer(){
 if(resumeDismissed||runs.length)return null;
 const list=recoveryList(),latest=list.find(e=>e.kind==='latest');
 // round 20 (Z2): the pair only while the tab holds runs of neither model
 const pairable=!runs.length&&!multiView.projectRuns();
 const withPair=entry=>{const o=pairable?entry.also?.[0]:null;return o&&!o.inTab&&o.record?{...entry,pair:{model:o.model,runs:o.runs,savedAt:o.record.savedAt}}:entry;};
 return {latest:latest?withPair(recoveredEntry(latest.recovered,latest.file)):null,earlier:list.filter(e=>e.kind==='earlier').map(e=>withPair({...recoveredEntry(e.recovered,e.file),index:e.index})),
  onLatest:button=>recoverLatest(button),onEarlier:(index,button)=>recoverEarlier(index,button),onPair:(index,button)=>restorePair(index,button),
  onOpenFile:()=>$('open-session').click(),onStartNew:()=>{resumeDismissed=true;render();document.querySelector('[data-template]')?.focus();}};
}
// Round 20 (Z2): the newest offer of a project with both models restores both: the newest record
// as its own button would, then, once that restore has completed (a load question answered with
// Replace; Cancel stops both), the other model's record, found again by its model, time and file
// (the first restore moves the stored records). The tab then shows the newest record's model.
// A failed second restore keeps the first and says so; that model's card offer stays.
function restorePair(index,opener){
 const first=recoveryList().find(e=>e.index===index);if(!first)return;
 const entry=recoveredEntry(first.recovered,first.file),other=entry.also?.[0];
 const own=options=>index<0?recoverLatest(opener,options):recoverEarlier(index,opener,options);
 if(!other||other.inTab||!other.record){own();return;}
 const card=first.recovered.session.application==='multiphysics'?'heated-waveguide':'optical',firstFile=first.recovered.savedFile,record=other.record;
 const then=async()=>{
  await renderEarlierSessions();
  const again=recoveryList().find(e=>e.recovered.session.application===record.application&&e.recovered.savedAt===record.savedAt&&entryFile(e)===record.file);
  if(!again){notice(`${other.model} was not restored: its browser record is no longer stored.`);return;}
  const done=()=>{chooseTemplate(card);notice(`Restored ${pairLine(entry,{model:other.model,runs:record.runs})} from this browser, not recomputed.`);};
  const options={then:done,failed:message=>notice(`${other.model} was not restored: ${message}`),projectMatched:firstFile?.current===true&&firstFile.name===record.file};
  if(again.kind==='latest')recoverLatest(opener,options);else recoverEarlier(again.index,opener,options);
 };
 own({then});
}
function restoredFrom(index){if(!Number.isInteger(index))return;restoredIndex=index;renderEarlierSessions();}
// A later call supersedes an earlier one still reading storage, so the list is never doubled.
let earlierGeneration=0;
async function renderEarlierSessions(){
 const generation=++earlierGeneration;
 let list=[];try{list=await notebookStore.loadEarlier();}catch{return;}
 if(generation!==earlierGeneration)return;
 const box=$('earlier-sessions');box.replaceChildren();earlierSessions=[];earlierRecords=list;
 list.forEach((record,index)=>{let recovered;try{recovered=readNotebookRecovery(record);}catch{return;}
  // keep the storage index: a record that does not parse is skipped, not renumbered
  earlierSessions.push({index,recovered});});
 // each session once, newest first: a copy of the latest record's text or of a newer one is not listed
 for(const {index,recovered,file} of recoveryList().filter(e=>e.kind==='earlier')){
  const button=document.createElement('button');button.type='button';button.dataset.earlier=String(index);
  button.textContent='Restore earlier session from this browser · '+sessionLine(recoveredEntry(recovered,file))+' · '+new Date(recovered.savedAt).toLocaleString();
  button.onclick=()=>recoverEarlier(index,button);box.append(button);}
 // the start page lists the same entries; redrawn with the focus kept on the control that had it
 if(ui.page==='Applications'){const el=document.activeElement,key=el?.id?'#'+el.id:el?.dataset?.template?`[data-template="${el.dataset.template}"]`:null;render();if(key)document.querySelector(key)?.focus({preventScroll:true});}
}
// After a project save: the stored records of the models written name the project file (S5, round
// 16); the lists are read again so the Library cards say so. A failure leaves the records as they were.
async function relinkRecovery(sessions,savedFile){
 try{if(!await notebookStore.relink(sessions,savedFile))return;
  const record=await notebookStore.load();notebookRecoveryRecord=record||null;
  if(latestOffer){const recovered=readNotebookRecovery(record);if(recovered)latestOffer={...latestOffer,recovered,entry:recoveredEntry(recovered)};}
  await renderEarlierSessions();if(ui.page==='Applications')render();
 }catch{}
}
// options (round 20, Z2): then, called once the restore has completed; failed(message) in place of
// the usual failure message; projectMatched, passed to restoreProjectFile.
async function recoverEarlier(index,opener,{then=null,failed=null,projectMatched=false}={}){
 if(solverBusy){notice('Wait for the calculation or stop waiting before recovering a session.');return;}
 try{
  rejectInvalidInput();
  // round 20 follow-up: this tab's pending recovery save is written first, so the record read and adopted is the stored one
  const loaded=await workspaceLoads.read(async()=>{await notebookAutosave.settle();const latest=await notebookStore.load();const list=await notebookStore.loadEarlier();const recovered=readNotebookRecovery(list[index]??null);
   if(recovered?.session.application==='multiphysics')await checkSessionModels(recovered.session,validateModel);return {latest,recovered};});
  if(!loaded)return;const {latest,recovered}=loaded.value;if(!recovered)throw new Error('That earlier session is no longer stored.');
  if(solverBusy)throw new Error('Calculation started while reading recovery.');rejectInvalidInput();
  if(recovered.session.application==='multiphysics'){requestMultiphysicsSession(recovered.session,{label:'Earlier browser session · '+new Date(recovered.savedAt).toLocaleString(),source:'browser',opener,recoveryRecord:latest,recoveryIndex:index,savedFile:recovered.savedFile,openedFile:recovered.openedFile,openedCurrent:recovered.openedCurrent,then,projectMatched,recordProject:recovered.project,recordSavedAt:recovered.savedAt});return;}
  // Adopt the latest record: the next save keeps it as an earlier session in turn.
  requestLoad(recovered.session.input,{saved:false,session:recovered.session,source:'browser',recoveryRecord:latest,recoveryIndex:index,savedFile:recovered.savedFile,openedFile:recovered.openedFile,openedCurrent:recovered.openedCurrent,page:recovered.page,opener,label:'Earlier browser session · '+new Date(recovered.savedAt).toLocaleString(),then,projectMatched,recordProject:recovered.project,recordSavedAt:recovered.savedAt});
 }catch(error){if(failed)failed(error.message);else notice('Earlier session not recovered: '+error.message);}
}
$('retry-notebook').onclick=()=>(multiView.active()?multiView.recovery():runs.length)?notebookAutosave.retry():loadNotebookRecovery();
$('recover-notebook').onclick=()=>recoverLatest($('recover-notebook'));
async function recoverLatest(opener,{then=null,failed=null,projectMatched=false}={}){
 if(solverBusy){notice('Wait for the calculation or stop waiting before recovering a session.');return;}
 $('recover-notebook').disabled=true;
 try{rejectInvalidInput();const loaded=await workspaceLoads.read(async()=>{await notebookAutosave.settle();const record=await notebookStore.load();const recovered=readNotebookRecovery(record);if(recovered?.session.application==='multiphysics')await checkSessionModels(recovered.session,validateModel);return {record,recovered};});if(!loaded)return;const {record,recovered}=loaded.value;if(!recovered)throw new Error('No session is stored for recovery.');if(solverBusy)throw new Error('Calculation started while reading recovery.');rejectInvalidInput();
  if(recovered.session.application==='multiphysics'){requestMultiphysicsSession(recovered.session,{label:'Browser recovery · '+new Date(recovered.savedAt).toLocaleString(),source:'browser',opener,recoveryRecord:record,recoveryIndex:-1,keepAsLatest:true,savedFile:recovered.savedFile,openedFile:recovered.openedFile,openedCurrent:recovered.openedCurrent,then,projectMatched,recordProject:recovered.project,recordSavedAt:recovered.savedAt});return;}
  requestLoad(recovered.session.input,{saved:false,session:recovered.session,source:'browser',recoveryRecord:record,recoveryIndex:-1,keepAsLatest:true,savedFile:recovered.savedFile,openedFile:recovered.openedFile,openedCurrent:recovered.openedCurrent,page:recovered.page,opener,label:'Browser recovery · '+new Date(recovered.savedAt).toLocaleString(),then,projectMatched,recordProject:recovered.project,recordSavedAt:recovered.savedAt});}
 catch(error){if(failed)failed(error.message);else notice('Session recovery failed: '+error.message+' Current inputs and results kept.');}
 finally{$('recover-notebook').disabled=!notebookRecoveryRecord;}
};

let pendingRecoveryReplacement=null;
const recoveryDialog=document.createElement('dialog');recoveryDialog.id='recovery-replace-confirm';recoveryDialog.setAttribute('aria-labelledby','recovery-replace-title');recoveryDialog.setAttribute('aria-describedby','recovery-replace-description');
recoveryDialog.innerHTML='<h2 id="recovery-replace-title">Replace browser recovery?</h2><p id="recovery-replace-description">This replaces the shared recovery snapshot for this browser and server address. Save either notebook to a session file first if you need both. Current inputs, results and Undo stay in this tab.</p><dl class="load-summary" id="recovery-replace-summary"></dl><button id="cancel-recovery-replace">Keep stored recovery</button> <button id="confirm-recovery-replace">Replace browser recovery</button>';
document.body.append(recoveryDialog);
function cancelRecoveryReplacement(){pendingRecoveryReplacement=null;workspaceLoads.invalidate();recoveryDialog.close();restoreDialogFocus($('replace-notebook'));notice('Browser recovery replacement cancelled. Both notebooks kept.');}
$('cancel-recovery-replace').onclick=cancelRecoveryReplacement;
recoveryDialog.oncancel=event=>{event.preventDefault();cancelRecoveryReplacement();};
$('replace-notebook').onclick=async()=>{
 try{
  // a multiphysics model: its own record (a run, or an edit since it was opened)
  const multi=multiView.active()?multiView.recovery():null;
  if(multiView.active()&&!multi)throw new Error('Complete a run or edit the model before replacing browser recovery.');
  if(!multi){rejectInvalidInput();if(!runs.length)throw new Error('Complete or import a run before replacing notebook recovery.');}
  if(solverBusy||notebookAutosave.writing)throw new Error('Wait for calculation and recovery storage to finish, then review again.');
  const loaded=await workspaceLoads.read(()=>notebookStore.load());if(!loaded)return;
  const record=loaded.value;let prior='No stored notebook';
  try{const recovered=readNotebookRecovery(record);if(recovered)prior=recovered.session.runs.length+' runs · '+new Date(recovered.savedAt).toLocaleString();}
  catch{prior='Unreadable stored notebook';}
  pendingRecoveryReplacement=multi?{record,context:loadContext(),stamp:multi.stamp+JSON.stringify(recordProjectNow()),makeText:multi.makeText,extra:{savedFile:multi.savedFile,openedFile:multi.openedFile,openedCurrent:multi.openedCurrent,project:recordProjectNow()}}:{record,context:loadContext(),stamp:autosaveStamp(),makeText:captureSession(inputsFile(),runs,solverRun?.job||null,compareIds,currentView()),extra:{savedFile:savedFile(),openedFile,openedCurrent:openedCurrent(),page:pageForRecord(),project:recordProjectNow()}};
  const summary=$('recovery-replace-summary');summary.replaceChildren();
  for(const [name,value] of [['Stored recovery',prior],['Replace with',multi?multiView.runCount()+' runs · '+multiView.modelName():runs.length+' runs · '+designSummary(current().model)],['Current inputs and Undo','Kept'],['Other tabs','Their next automatic save will detect this replacement']]){
   const term=document.createElement('dt'),detail=document.createElement('dd');term.textContent=name;detail.textContent=value;summary.append(term,detail);
  }
  recoveryDialog.showModal();
 }catch(error){notice('Cannot replace browser recovery: '+error.message);}
};
$('confirm-recovery-replace').onclick=async()=>{
 const pending=pendingRecoveryReplacement;pendingRecoveryReplacement=null;workspaceLoads.invalidate();recoveryDialog.close();if(!pending)return;
 if(pending.context!==loadContext()){notice('Workspace changed during review. Review browser recovery again; stored notebook kept.');return;}
 try{await notebookAutosave.replaceReviewed(pending.record,pending.stamp,pending.makeText,pending.extra);}
 catch(error){notice('Browser recovery not replaced: '+error.message);}
};

// the mode shown is one of the selected run's modes (a file is refused otherwise)
function currentView(){return {...fieldView,mode:Math.max(0,Math.min(fieldView.mode,(solverRun?.effective_index.length??8)-1)),probe:{...fieldProbe},profile:{...profileState}};}
function restoreView(view){Object.assign(fieldView,{mode:view.mode,component:view.component,window:view.window});Object.assign(fieldProbe,view.probe||{x:0,y:.15,active:false});Object.assign(profileState,view.profile||{axis:'x',coordinate:.15,open:false});}
// The completed runs as a session file keeps them; inputs and view settings are not results.
function runsStamp(){return JSON.stringify(runs.map(runStampEntry));}
function notebookStamp(){return JSON.stringify({input:workspaceInputs(),runs:runs.map(runStampEntry),selected:solverRun?.job||null,comparison:compareIds,view:currentView()});}
// The application the last recovery record was scheduled for: when the tab moves between an
// optical and a multiphysics model, the stored record is kept as an earlier session.
let recoveryKind=null;
function scheduleRecovery(kind,stamp,makeText,extra){if(recoveryKind&&recoveryKind!==kind)notebookStore.keepPrevious();recoveryKind=kind;notebookAutosave.schedule(stamp,makeText,extra);}
function refreshNotebook(){
 if(multiView.active()){const rec=multiView.recovery();$('replace-notebook').disabled=!rec;if(rec)scheduleRecovery('multiphysics',rec.stamp+JSON.stringify(recordProjectNow()),rec.makeText,{savedFile:rec.savedFile,openedFile:rec.openedFile,openedCurrent:rec.openedCurrent,project:recordProjectNow()});
  $('notebook-status').textContent=multiView.runCount()?(multiView.unsavedRuns()?'Changed since the last session file · File › Save keeps it':'Matches the last session file opened or saved'):'No completed runs in this session';$('save-session').classList.toggle('unsaved-session',multiView.unsavedRuns()>0);return;}
 const stamp=notebookStamp();$('replace-notebook').disabled=!runs.length||numericDrafts.invalid;if(runs.length&&!numericDrafts.invalid)scheduleRecovery('optical',autosaveStamp(),captureSession(workspaceInputs(),runs,solverRun?.job||null,compareIds,currentView()),{savedFile:savedFile(),openedFile,openedCurrent:openedCurrent(),page:pageForRecord(),project:recordProjectNow()});const changed=savedNotebookState!==stamp;$('notebook-status').textContent=runs.length?(changed?'Changed since the last session file · File › Save keeps it':'Matches the last session file opened or saved'):'No completed runs in this session';$('save-session').classList.toggle('unsaved-session',runs.length>0&&changed);}
const opticalBlock=()=>connection.ready?opticalSupport(state,setup):connection.message;
const retentionBlock=()=>runs.length===RUN_LIMIT&&runs.every(run=>run.pinned)?'All six runs are pinned. Unpin a run in Results before starting another calculation.':'';
const opticalDocument=()=>buildOpticalDocument({...state,searchTarget:closedTargetNow()},setup);
// The parts the inputs words compare for a run and the current inputs (round 23, E6: every part of
// studySignature, workspace-workflow.mjs studyInputParts): [runParts, currentParts]
const runStudy=run=>({input:run.input,modeCount:runModeCount(run),groupIndex:run.group_index_method!==undefined,pml:isOpenRun(run)?run.settings.pml:null,searchTarget:runSearchTarget(run)});
const studyParts=run=>studyInputParts(runStudy(run),{input:current(),modeCount:state.modeCount,groupIndex:state.groupIndex===true,pml:pmlNow(),searchTarget:closedTargetNow()});
// Modes to find (1 to 8): the number of modes a run asks for, saved with the inputs (version 8
// when not 2) and kept with each run.
const MODE_COUNT_NOTE='Modes to find is saved with the model inputs and kept with each run of a session.';
// Also compute group index (off by default, saved with the inputs): the run's document gains
// results.group_index and the engine solves λ0 − 1 nm and λ0 + 1 nm as well (workspace-optical.mjs)
const GROUP_INDEX_LABEL='Also compute group index (3 solves)';
const GROUP_INDEX_OPEN_WARNING='Group index is on: open-boundary runs with it take about three times as long.';
// With an open boundary too (slice P3): the engine's n_g is then complex, and Re n_g is shown.
const groupIndexField=()=>`<label class="check-field"><input id="group-index-check" type="checkbox"${state.groupIndex?' checked':''}> ${GROUP_INDEX_LABEL}</label><p class="input-note">${GROUP_INDEX_NOTE}</p>`;
// Outer boundary (Physics › Optical modes): Closed window (PEC) or Open boundary (PML), and
// Search near n_eff, kept to 3 decimals. The group index option is kept either way.
const bindBoundaryField=()=>{
 document.querySelectorAll('input[name="outer-boundary"]').forEach(radio=>radio.onchange=()=>{
  const open=radio.value==='open'&&radio.checked;if(open===!!state.openBoundary)return;setOuterBoundary(open);});
 const target=$('target-number');if(target)target.onchange=()=>{
  let t;try{t=parseTarget(target.value,state.shapes);}catch(error){notice(error.message);target.value=(state.openBoundary.target??Number(target.defaultValue)).toFixed(3);return;}
  state.openBoundary={...state.openBoundary,target:t};render();notice(`Search near n_eff ${t.toFixed(3)}: the next run returns the modes nearest it.`);};
};
// The outer boundary chosen (the radio in Physics › Optical modes, or Use Open boundary under a
// closed run's edge note, round 18 X9), with its message; nothing runs.
function setOuterBoundary(open){
  state.openBoundary=open?openChoice():null;
  render();notice(open?'Open boundary: a PML of 1 µm outside every edge; loss includes leakage. Close single edges in Geometry › Boundaries.':'Closed window: four PEC edges; loss counts material absorption only.');
  // round 18 (X2): an open run with the group index takes about three times as long: said in a warning style
  if(open&&state.groupIndex===true){const warn=document.createElement('span');warn.className='message-warning';warn.id='group-index-open-warning';warn.textContent=GROUP_INDEX_OPEN_WARNING;$('file-status').append(' ',warn);}
}
// Search near n_eff in a closed window (slice C2): Modes to return in Physics › Optical modes (round
// 22, V1: the radios Highest n_eff above 1.45 and Nearest to n_eff with the field n_eff to search near,
// always enabled, in place of the box and its disabled field), and the edge note's shortcut (with
// Modes to find 4); each sets the inputs with a message and runs nothing. state.searchTarget stays the
// one input: null is Highest (the box off), a number Nearest (the box on), so documents and sessions
// are unchanged. The field's value while Highest is chosen is kept in memory only (ui.closedNear).
// K10: when a kept run has the new inputs, the message offers it (No need to run: Run N …)
function setClosedSearch(t){state.searchTarget=t;render();notice(closedSearchNotice(t));offerMatchingRun();}
function useClosedSearch(t){if(state.openBoundary||(state.searchTarget===t&&state.modeCount===SHORTCUT_MODE_COUNT))return;state.searchTarget=t;state.modeCount=SHORTCUT_MODE_COUNT;render();notice(`${closedSearchNotice(t)} Modes to find set to ${SHORTCUT_MODE_COUNT}. ${SHORTCUT_RUN_TEXT}`);offerMatchingRun();}
// the field's index while Highest is chosen: the last one typed, if still in this design's range, else the default
const closedNearDraft=()=>{try{if(ui.closedNear!=null)return checkClosedTarget(ui.closedNear,state.shapes);}catch{}return defaultTarget(state.shapes);};
// round 22 (V2): before a run, the closed window's slab warning (a geometry and material check, no
// solve): with Highest n_eff above 1.45 and an edge-touching shape whose index is as high as the core's;
// gone with Nearest to n_eff or Open boundary. The result-side edge note stays as it is.
const edgeWarning=()=>isOptical()&&applicationChosen()&&!state.openBoundary&&state.searchTarget==null?edgeSlabRisk(state.shapes):null;
// its two buttons, in the plan line and in Physics › Optical modes: the edge note's shortcut (the same
// target estimate, defaultTarget) and Use Open boundary; each sets the inputs and runs nothing
function edgeWarningButtons(prefix){
 const near=defaultTarget(state.shapes),search=document.createElement('button'),open=document.createElement('button');
 search.type=open.type='button';search.className=open.className='message-action';search.id=prefix+'-search';open.id=prefix+'-open';
 search.textContent=shortcutText(near);search.onclick=()=>useClosedSearch(near);
 open.textContent='Use Open boundary';open.onclick=()=>{if(!state.openBoundary)setOuterBoundary(true);};
 return [search,open];
}
const closedSearchField=()=>{
 if(state.openBoundary)return '';const near=state.searchTarget!=null,t=near?state.searchTarget:closedNearDraft(),risk=edgeWarning();
 return `${risk?`<div class="closed-edge-warning" id="closed-edge-warning"><p class="validation-warning" id="closed-edge-warning-text">${escapeHtml(edgeSlabWarningText(risk))}</p><p class="closed-edge-actions" id="closed-edge-actions"></p></div>`:''}<fieldset class="boundary-choice closed-search" id="closed-search"><legend>${CLOSED_SEARCH_LEGEND}</legend><label class="radio-field"><input type="radio" name="closed-search" id="closed-search-highest" value="highest"${near?'':' checked'}> ${HIGHEST_LABEL}</label><span class="closed-search-near"><label class="radio-field"><input type="radio" name="closed-search" id="closed-search-nearest" value="nearest"${near?' checked':''}> ${NEAREST_LABEL}</label><input id="closed-target-number" type="number" min="1.45" step="0.001" value="${t.toFixed(3)}" aria-label="${NEAR_FIELD_LABEL}" aria-describedby="closed-search-help"></span></fieldset><p class="input-note" id="closed-search-help">${CLOSED_SEARCH_HELP}</p>`;
};
const bindClosedSearchField=()=>{
 const highest=$('closed-search-highest'),nearest=$('closed-search-nearest'),field=$('closed-target-number');if(!highest||!nearest||!field)return;
 $('closed-edge-actions')?.append(...edgeWarningButtons('closed-edge'));
 // the field's index, checked, as the target: Nearest to n_eff; an invalid one restores the choice and the field
 const take=()=>{const t=Math.round(Number(field.value)*1000)/1000;
  try{checkClosedTarget(t,state.shapes);}
  catch(error){notice(error.message);field.value=(state.searchTarget??closedNearDraft()).toFixed(3);nearest.checked=state.searchTarget!=null;highest.checked=!nearest.checked;return;}
  ui.closedNear=t;if(state.searchTarget===t)return;setClosedSearch(t);};
 highest.onchange=()=>{if(highest.checked&&state.searchTarget!=null)setClosedSearch(null);};
 nearest.onchange=()=>{if(nearest.checked)take();};
 // typing an index selects Nearest to n_eff at once; the index is taken when the field changes (or
 // is left with the choice moved but the value unchanged)
 field.oninput=()=>{nearest.checked=true;};
 field.onchange=take;
 field.onblur=()=>{if(field.isConnected&&nearest.checked&&state.searchTarget==null)take();};
};
// The group index box in Study or Optical modes (one panel at a time): the option, then Messages says what the next run does.
const bindGroupIndexField=()=>{const box=$('group-index-check');if(box)box.onchange=e=>{state.groupIndex=e.target.checked;render();notice(groupIndexNotice(state.groupIndex));};};
// The wavelength and Modes to find: one field each, the same in Physics › Optical modes and in
// Study (only one of the two panels is shown at a time, so the ids stay unique).
const wavelengthField=()=>`<label>Wavelength [nm]<input id="wavelength-number" type="number" min="1400" max="1700" step="any" value="${state.wavelength}"></label>`;
// round 18 (X2; round 17 U3 named the slow options only): what the next optical run does, beside Run
// study, with how long the last comparable run of this tab took; the options keep their state (a
// task does not reset them), so a run that is slower than one solve says why first
// round 18 (X3): before the run, the run the six-run limit would drop, with Pin Run N (the limit is unchanged)
// Round 21 (W2): Run study starts at once; while the run computes (or waits as a pending job) the line
// says what its result drops, "When this run finishes, Run 3 (…) is dropped", and Pin Run N keeps it
// (the line then names the next unpinned run). Pin is hidden when pinning would leave the result no
// slot. Round 21 (W5): before a run the line is hidden while the inputs equal a run's (Messages then
// says no run is needed); it returns when they differ from every run.
function refreshDropWarning(){
 const running=solverBusy||!!pendingJob,list=droppedBy(runs,RUN_LIMIT);
 const matched=!running&&!numericDrafts.invalid&&runs.some(r=>r.signature===signature());
 const host=$('run-drop'),run=matched?null:list[0]||null;host.hidden=!run;$('run-options').classList.toggle('dropping',!!run);if(!run)return;
 const text=running?dropWhileRunningText(list):dropWarningText(list.length>1?list:run);$('run-drop-text').textContent=text;$('run-drop-text').title=text;
 const pin=$('run-drop-pin');pin.textContent=`Pin Run ${run.number}`;pin.dataset.pinRun=String(run.number);
 // the finishing result needs a free slot: no pin that would leave fewer unpinned runs than it drops
 pin.hidden=runs.filter(r=>!r.pinned).length<=list.length;pin.disabled=false;
 pin.onclick=()=>{if(!runs.includes(run)||run.pinned||runs.filter(r=>!r.pinned).length<=droppedBy(runs,RUN_LIMIT).length)return;run.pinned=true;render();
  // round 22 (V4): the drop moves to the next unpinned run: Messages names it
  const next=droppedBy(runs,RUN_LIMIT);notice(next.length?pinnedDropText(run,next,solverBusy||!!pendingJob):pinNotice(run));};
}
function refreshRunOptions(){
 const host=$('run-options');if(!host)return;const shown=isOptical()&&!multiView.active()&&applicationChosen();host.hidden=!shown;if(!shown)return;
 const open=!!pmlNow(),plan={open,searches:open&&lowerTarget(effectiveTarget(state.openBoundary,state.shapes))!==null?2:1,groupIndex:state.groupIndex===true,pmlCheck:ui.pmlCheck===true&&hasOpenEdge(state.openBoundary),modeCount:state.modeCount,searchTarget:open?null:closedTargetNow()};
 const kinds={isOpen:isOpenRun,hasGroup:hasGroupIndex},last=lastComparableRun(runs,plan,kinds),estimate=plan.groupIndex?groupIndexEstimate(runs,plan,kinds):null,text=runPlanText({...plan,last:plan.groupIndex?null:last?.duration??null,estimate});
 refreshDropWarning();refreshEdgeWarning();refreshGroupIndexOff(plan.groupIndex);
 const line=$('run-plan');if(line.textContent!==text)line.textContent=text;line.title=plan.groupIndex?'What the next run does; change it in Study or Physics › Optical modes. The estimate is the wall time of the last run in this tab with the same boundary, 3 times it when that run had no group index.':'What the next run does; change it in Study or Physics › Optical modes. The time is the wall time of the last run in this tab with the same boundary and group index setting.';
}
// round 23 (E3): Turn off group index, beside the plan line while the option is on, removed while it
// is off (a row made here around the plan line, so the page's markup is unchanged). It is the
// option's own input edit (Undo takes it back); the option stays an input and no run turns it off.
function refreshGroupIndexOff(on){
 let button=$('run-plan-group-off');if(!on){button?.remove();return;}if(button)return;
 if(!$('run-plan').parentElement.classList.contains('run-plan-row')){const row=document.createElement('span');row.className='run-plan-row';$('run-plan').before(row);row.append($('run-plan'));}
 button=document.createElement('button');button.type='button';button.id='run-plan-group-off';button.className='message-action';button.textContent='Turn off group index';button.onclick=turnOffGroupIndex;$('run-plan').after(button);
}
function turnOffGroupIndex(){if(state.groupIndex!==true)return;state.groupIndex=false;render();notice(groupIndexNotice(false));}
// round 22 (V2): the slab warning in the plan line, a row under it (made here, so the page's markup is
// unchanged) with the two buttons. Round 23 (E1): its short words (edgeSlabShortText), never cut:
// the row wraps, the buttons on a line of their own when the words and the buttons do not fit, and
// the box grows for it; the full sentence is the title and stays in Physics › Optical modes.
function refreshEdgeWarning(){
 let host=$('run-edge');const risk=edgeWarning();
 if(!host){host=document.createElement('span');host.id='run-edge';host.className='run-edge';host.hidden=true;const text=document.createElement('span');text.id='run-edge-text';text.className='run-edge-text';host.append(text);$('run-plan').after(host);}
 host.hidden=!risk;$('run-options').classList.toggle('edge-warning',!!risk);if(!risk){host.dataset.key='';return;}
 const text=edgeSlabShortText(risk),key=text+'\n'+defaultTarget(state.shapes);if(host.dataset.key===key)return;host.dataset.key=key;
 $('run-edge-text').textContent=text;$('run-edge-text').title=edgeSlabWarningText(risk);host.querySelectorAll('button').forEach(b=>b.remove());host.append(...edgeWarningButtons('run-edge'));
}
const modeCountField=()=>{const f=INPUT_FIELDS.modeCount;return `<label>${f.label}<input id="${f.id}" type="number" min="${f.min}" max="${f.max}" step="1" value="${state.modeCount}"></label>`;};
// round 20 (Z6): the scope names both boundaries, as the Open boundary choice sits beside it
const OPTICAL_SCOPE_BOUNDARY='3 × 2.4 µm window, closed (PEC edges) or with an open boundary (PML 1 µm outside the open edges, PEC on the closed ones)';
function solverPanel(){document.querySelector('main').classList.toggle('comparing',ui.page==='Compare');document.querySelector('main').classList.toggle('choosing',ui.page==='Applications');
 const block=opticalBlock();// Plain text, not steps: the step bar above and the model tree are what select a node.
 if(isOptical())$('sequence').innerHTML='<span class="sequence-note">Optical mode analysis · Run checks the inputs, then computes · mesh and window convergence not certified</span>';if(['Results','Compare'].includes(ui.page))$('sequence').innerHTML='<span class="sequence-note">Each result keeps the inputs it was run with · Compare matches modes by field overlap · convergence not certified</span>';$('status').textContent=solverBusy?'Optical computation running':block?'Coupled solver unavailable · optical-only template supported':opticalReadyStatus(opticalFreshness(current(),runs,viewedRun(),state.modeCount,state.groupIndex,pmlNow(),closedTargetNow()));$('run-optical').disabled=solverBusy||!!pendingJob||!!block;
 $('run-optical').textContent=solverBusy?'Computing…':'Run study';
 if(ui.page==='Model'&&['Study','Optical modes'].includes(ui.selection)){
  const info=document.createElement('section');info.innerHTML='<h3>Optical adapter scope</h3><p>2D cross section with up to 8 rectangles, circles or polygons of ten lossless materials inside the window; silica background; wavelength 1400–1700 nm; core mesh 20–60 nm; '+OPTICAL_SCOPE_BOUNDARY+'; 1 to 8 modes (Modes to find, 2 by default). Heater, thermal and mechanical settings are excluded. Mesh/window convergence is not certified.</p>';
  const msg=document.createElement('p');msg.textContent=block||'Optical input supported. Solver validation runs before submission.';info.append(msg);
  if(ui.selection==='Study'&&!block)$('canvas').innerHTML='<h2>Optical study</h2><p>Run uses the inputs as they are when you press it.</p>'+pair('Geometry',escapeHtml(designSummary(current().model)))+pair('Wavelength',state.wavelength+' nm')+pair('Core mesh',state.coreMesh+' nm')+pair('Background',setup.materials.Oxide)+'<button id=review-geometry>Edit geometry</button> <button id=review-materials>Edit materials</button>';
   if($('review-geometry'))$('review-geometry').onclick=()=>select('Geometry');if($('review-materials'))$('review-materials').onclick=()=>select('Materials');
  $('canvas').append(info);if(ui.selection==='Study'&&!block)$('inspector').innerHTML='<h2>Optical execution</h2>'+pair('State',solverBusy?'Computing':solverRun?'Completed run available':'Ready for validation')+'<p>Run captures current inputs. Other physics remain unavailable.</p>';
 }
 const controls=document.querySelector('.workspace > .toolbar');controls.style.display=['Applications','Connections','Results','Compare'].includes(ui.page)?'none':'flex';document.querySelector('.workspace > .note').textContent=['Results','Compare'].includes(ui.page)?'Field data belongs to a captured run. Imported results are labeled; no automatic computation.':isOptical()?'Optical cross section uses the submitted geometry, in nm. Shapes, materials, wavelength and core mesh editable; window fixed; outer boundary chosen in Physics › Optical modes.':'Conceptual geometry only · no CAD kernel or computed deformation';
 if(ui.page==='Compare'){renderComparison();renderRunList();return;}
 if(ui.page==='Results'&&solverRun){
  const [runParts,nowParts]=studyParts(solverRun);
  const same=solverRun.signature===signature();$('inspector').innerHTML='<h2>Selected run</h2>'+`<div class="pair"><span>Name</span><strong id="run-name-value">${escapeHtml(solverRun.label||'Not named')}</strong></div>`+pair('Inputs',same?'Same as the current inputs':escapeHtml(inputsDifferText(runParts,nowParts)))+(same&&!runInputsNoteFor(solverRun)?'':'<div id="use-run-slot"></div>')+runDetails(solverRun)+'<p>File › Save keeps this run with its fields in the session file. File › Export › Model file keeps the inputs without results.</p>'; $('canvas').innerHTML='<h2>Computed optical modes</h2>';$('run-details').ontoggle=()=>{ui.runDetailsOpen=$('run-details')?.open===true;};
  const desc=document.createElement('p');desc.textContent=runInputsLine(runParts,nowParts);$('canvas').append(desc);
  // fewer modes than asked: "Found 3 of 8 modes above n = 1.45"
  // an open run: "Found 2 of 2 modes near n_eff 2.460" always (the target decides what is found)
  if(isOpenRun(solverRun))$('canvas').append(foundLine(solverRun));
  else if(isClosedTargetRun(solverRun)){const line=document.createElement('p');line.id='modes-found';line.className='modes-found';line.textContent=closedFoundText(solverRun.effective_index.length,runModeCount(solverRun),runSearchTarget(solverRun))+'.';$('canvas').append(line);}
  else{const found=foundText(solverRun.effective_index.length,runModeCount(solverRun));if(found){const line=document.createElement('p');line.id='modes-found';line.className='modes-found';line.textContent=found+'.';$('canvas').append(line);}}
  $('canvas').append(modesTable(solverRun));if(isOpenRun(solverRun))$('canvas').append(candidatesDisclosure(solverRun));if(solverRun.field)renderField();else{const none=document.createElement('p');none.id='fields-not-kept';none.textContent=solverRun.origin==='recovered'?'This run’s fields were not kept in browser recovery (over 16 MiB): n_eff, the TE fractions and the effective areas were.':'This run’s fields were not kept in the session file: n_eff, the TE fractions and the effective areas were.';$('canvas').append(none);}
  const note=document.createElement('p');note.textContent=(solverRun.origin==='local'?'Actual local solver output. ':solverRun.origin==='recovered'?'Recovered from this browser, not recomputed. ':'Loaded from file, not recomputed. Studio checks that the file is well formed, not who made it. ')+' '+RANKING_TEXT+' '+COMPARE_MATCH_TEXT+' File › Save keeps the results. No thermal or mechanical solve was performed.';$('canvas').append(note);
 }
 if(ui.page==='Results'){if(!solverRun)$('canvas').innerHTML='<h2>No completed runs</h2><p>Choose Library → Optical waveguide, edit the model and run an optical study. A session file can also restore prior results.</p>';renderRunList();}
 if(ui.page==='Model'&&ui.selection==='Optical modes'&&isOptical())$('inspector').innerHTML='<h2>Optical modes</h2>'+pair('Equation','Vector optical eigenproblem')+``+wavelengthField()+pair('Material data',OPTICAL_MATERIAL_DATA)+modeCountField()+`<p class="input-note">${MODE_COUNT_NOTE}</p>`+groupIndexField()+boundaryFieldHtml(state.openBoundary,state.shapes)+closedSearchField()+'<p>Run from Study to compute optical fields for the current cross section.</p>';
 if(ui.page==='Model'&&ui.selection==='Optical modes'&&isOptical()){bindGroupIndexField();bindBoundaryField();bindClosedSearchField();}
 if(ui.page==='Connections'&&isOptical()){$('inspector').innerHTML='<h2>Active interfaces</h2>'+pair('Optical modes','Enabled')+pair('Couplings','None')+'<p>This application computes optical modes only.</p>';document.querySelector('.workspace > .note').textContent='One optical interface; no thermal or mechanical field transfer is configured.';}
 if(ui.page==='Model'&&ui.selection==='Mesh'&&isOptical())renderMeshPreview();
 if(ui.page==='Model'&&ui.selection==='Study'&&isOptical())renderOpticalStudy();
}

// Requests other than Run go through this: a lost server starts automatic
// reconnection, and a restarted server is reconnected so the next request works.
const watchedApi=(path,body)=>solverApi(path,body).catch(error=>{const kind=connectionFailure(error);if(kind==='unreachable')connectionLost();else if(kind==='restarted'&&connection.ready)connectWorkspace();throw error;});
const preflight=new OpticalPreflight(watchedApi,()=>{if(ui.page==='Model'&&ui.selection==='Study')render();});
function renderOpticalStudy(){
 const host=$('canvas'),panel=$('inspector');host.innerHTML='<h2>Optical study</h2><p>Review the current input, optionally check it, then run explicitly.</p>'+pair('Geometry',escapeHtml(designSummary(current().model)))+pair('Wavelength',state.wavelength+' nm')+pair('Core mesh',state.coreMesh+' nm')+pair('Background',setup.materials.Oxide);
 const actions=document.createElement('div');actions.className='study-actions';
 for(const name of ['Geometry','Materials']){const edit=document.createElement('button');edit.textContent='Edit '+name.toLowerCase();edit.onclick=()=>select(name);actions.append(edit);}
 // The wavelength is shown here but set in Physics › Optical modes: open it with the field focused.
 const editWavelength=document.createElement('button');editWavelength.id='edit-wavelength';editWavelength.textContent='Edit wavelength';editWavelength.onclick=()=>editWavelengthField();actions.append(editWavelength);
 const check=document.createElement('button');check.textContent=preflight.busy?'Checking inputs…':'Check inputs';check.disabled=preflight.busy||solverBusy||!!opticalBlock()||numericDrafts.invalid;
 check.onclick=()=>preflight.check(current(),opticalDocument(),connection.instance);actions.append(check);
 const exportDoc=document.createElement('button');exportDoc.textContent='Export solver JSON';exportDoc.disabled=!!opticalSupport(state,setup)||numericDrafts.invalid;
 exportDoc.onclick=()=>{try{rejectInvalidInput();downloadFile(new Blob([JSON.stringify(opticalDocument(),null,2)],{type:'application/json'}),'studio-optical-solver.json');notice('Solver document exported: a simcase input with geometry in nm and other lengths as quantities, not a workspace session.');}catch(error){notice(error.message);}};actions.append(exportDoc);host.append(actions);
 const block=opticalBlock()||retentionBlock();if(block){const message=document.createElement('p');message.textContent=block;message.className='validation-warning';host.append(message);}
 if(preflight.error){const error=document.createElement('p');error.setAttribute('role','alert');error.textContent='Input check failed: '+preflight.error+' Previous check retained.';host.append(error);}
 const record=preflight.record;
 if(record){const report=document.createElement('section');report.className='validation-report';const heading=document.createElement('h3');const same=!numericDrafts.invalid&&record.signature===signature()&&record.serverInstance===connection.instance;
 heading.textContent=(same?'Current inputs':'Earlier inputs or server')+' · '+(record.ok?'document accepted':'document rejected');report.append(heading);
 const captured=document.createElement('p');captured.textContent=designSummary(record.input.model)+' · λ '+record.input.model.wavelength+' nm · mesh '+record.input.model.coreMesh+' nm · '+new Date(record.checkedAt).toLocaleTimeString();report.append(captured);
 const summary=document.createElement('pre');summary.textContent=record.ok?record.summary:record.error;report.append(summary);
 for(const d of record.diagnostics){const line=document.createElement('p');line.textContent=`${d.severity} ${d.code}${d.path?' at '+d.path:''}: ${d.message}`;report.append(line);}host.append(report);
 }else host.insertAdjacentHTML('beforeend','<p>No document check in this tab. Run always validates again before submission.</p>');
 const scope=document.createElement('p');scope.textContent='Document checks validate the schema and settings; they do not generate a mesh, solve fields, verify material accuracy or certify convergence. Run captures current inputs, validates them again, then starts a calculation.';host.append(scope);
 panel.innerHTML='<h2>Execution settings</h2>'+pair('State',opticalWorkflow({input:current(),modeCount:state.modeCount,groupIndex:state.groupIndex,pml:pmlNow(),searchTarget:closedTargetNow(),invalid:numericDrafts.invalid,block,busy:solverBusy,pending:!!pendingJob,resumeBlocked:jobResumeBlocked,runs})[3].summary)+`<p id="next-run-inputs" class="next-run">${escapeHtml(numericDrafts.invalid?'Next run: correct the highlighted inputs first':nextRunText(current(),state.modeCount,state.groupIndex,pmlNow(),closedTargetNow()))}</p>`+wavelengthField()+modeCountField()+groupIndexField()+studyOpenHtml(pmlNow()?state.openBoundary:null,state.shapes,ui.pmlCheck===true,state.modeCount)+pair('Core mesh',state.coreMesh+' nm')+pair('Window','3 × 2.4 µm')+(state.openBoundary?pair('Outer edges',openEdges(state.openBoundary).length?`PML 1 µm on ${openEdges(state.openBoundary).join(', ')}; PEC elsewhere`:'PEC (every edge closed)')+'<p>The window is fixed; the outer boundary is chosen in Physics › Optical modes. Electrical, thermal and mechanical solves are unavailable in this workspace.</p>':pair('Outer edges','PEC')+'<p>The window is fixed; the outer boundary is chosen in Physics › Optical modes. Electrical, thermal and mechanical solves are unavailable in this workspace.</p>');
 bindGroupIndexField();{const box=$('pml-check');if(box)box.onchange=()=>{ui.pmlCheck=box.checked;refreshRunOptions();notice(box.checked?`PML check on: the next run solves the same mesh again with strength 6, once per mode (${state.modeCount} more solve${state.modeCount===1?'':'s'} at most).`:'PML check off: the next run is one solve.');};}
 document.querySelector('.workspace > .note').textContent='Checks and runs capture inputs separately. A prior accepted document does not certify the current model.';
 if(!opticalSupport(state,setup)){const details=document.createElement('details');details.className='solver-document';const title=document.createElement('summary');title.textContent=(numericDrafts.invalid?'Last valid solver document':'Solver document')+' · simcase input (engine document) · geometry in nm, other lengths as quantities such as "1550 nm"';const body=document.createElement('pre');body.textContent=JSON.stringify(opticalDocument(),null,2);details.append(title,body);host.append(details);}
}

let meshView='Full window';
const meshPreview=new MeshPreview((path,body)=>watchedApi(path+'?workspace_instance='+encodeURIComponent(connection.instance),body),()=>{if(ui.page==='Model'&&ui.selection==='Mesh')render();});
function renderMeshPreview(){
 document.querySelector('.workspace > .note').textContent='Actual mesh, axes in nm; preview is attached to captured inputs. Shaded triangles belong to shapes; dark triangles to the silica background.';
 const host=$('canvas'),panel=$('inspector');host.innerHTML='<h2>Optical mesh</h2><p>Generate the actual triangular mesh without solving optical modes.</p>';
 const generate=document.createElement('button');generate.id='generate-mesh';generate.textContent=meshPreview.busy?'Generating mesh…':'Generate mesh';generate.disabled=meshPreview.busy||solverBusy||!!opticalBlock()||numericDrafts.invalid;
 generate.onclick=async()=>{try{rejectInvalidInput();await meshPreview.generate(current(),opticalDocument());}catch(error){notice(error.message);}};host.append(generate);
 panel.innerHTML='<h2>Mesh settings</h2>'+`<label>Core mesh size [nm]<input id="core-mesh-number" type="number" min="20" max="60" step="any" value="${state.coreMesh}"></label>`+pair('Applies to','Silicon and silicon nitride shapes')+pair('Far target','160 nm')+pair('Window','3 × 2.4 µm')+'<p>Smaller core mesh sizes take longer and produce larger session files. Mesh generation does not certify convergence. The solve generates its own mesh from the same document.</p>';
 if(meshPreview.error){const error=document.createElement('p');error.setAttribute('role','alert');error.textContent='Mesh generation failed: '+meshPreview.error+' Previous preview retained.';host.append(error);}
 const record=meshPreview.record;if(!record){host.insertAdjacentHTML('beforeend','<p>No mesh generated in this tab.</p>');return;}
 const stale=record.signature!==inputSignature();const note=document.createElement('p');note.textContent=(stale?'Earlier input mesh — regenerate for current inputs. ':'Current input mesh. ')+designSummary(record.input.model)+' · core mesh '+record.input.model.coreMesh+' nm';host.append(note);
 const label=document.createElement('label');label.textContent='Mesh view';const view=document.createElement('select');view.id='mesh-view';view.innerHTML=options(['Full window','Core region'],meshView);label.append(view);host.append(label);
 const canvas=document.createElement('canvas');canvas.id='mesh-preview';canvas.style.cssText='display:block;width:100%;height:360px';canvas.setAttribute('role','img');host.append(canvas);
 panel.insertAdjacentHTML('beforeend',pair('Nodes',record.data.stats.nodes)+pair('Triangles',record.data.stats.triangles)+pair('Minimum angle',record.data.stats.minAngle+'°')+pair('Mean quality',record.data.stats.meanQuality));
 const draw=()=>drawMesh(canvas,record.data,meshView,regionBounds(record.input.model,.15,.65,.5));view.onchange=()=>{meshView=view.value;draw();};fieldResize=new ResizeObserver(draw);fieldResize.observe(canvas);draw();
}

// Zoomed view around the design, in µm: padded bounds, at least the given half sizes, kept inside the window.
function regionBounds(model,pad,halfX,halfY){
 const b=designBounds(model.shapes),cx=(b.xmin+b.xmax)/2000,cy=(b.ymin+b.ymax)/2000;
 const hx=Math.min(1.5,Math.max(halfX,(b.xmax-b.xmin)/2000+pad)),hy=Math.min(1.2,Math.max(halfY,(b.ymax-b.ymin)/2000+pad));
 const x=Math.min(1.5-hx,Math.max(-1.5+hx,cx)),y=Math.min(1.2-hy,Math.max(-1.2+hy,cy));
 return [x-hx,x+hx,y-hy,y+hy];
}
function fieldColor(t){const stops=[[18,38,59],[23,111,139],[69,187,159],[249,235,130]];const z=Math.min(2.999999,Math.max(0,t)*3),i=Math.floor(z),a=z-i;return 'rgb('+stops[i].map((v,k)=>Math.round(v+(stops[i+1][k]-v)*a)).join(',')+')';}
let fieldResize=null,profileResize=null,profileRedraw=()=>{};const profileState={axis:'x',coordinate:.15,open:false};
function addProbeControls(host,redraw){
 const form=document.createElement('form');form.className='probe-controls';
 form.innerHTML='<strong>Inspect displayed sample</strong><label>x [nm]<input id="probe-x" type="number" step="any" min="-1500" max="1500" required></label><label>y [nm]<input id="probe-y" type="number" step="any" min="-1200" max="1200" required></label><button type="submit">Inspect point</button><button type="button" id="clear-probe">Clear point</button><span>Click a plot or enter coordinates. Values belong to triangle centroids; no interpolation.</span>';
 host.append(form);$('probe-x').value=nmValue(fieldProbe.x);$('probe-y').value=nmValue(fieldProbe.y);
 form.onsubmit=event=>{event.preventDefault();if(!form.reportValidity())return;fieldProbe.x=Number($('probe-x').value+'e-3');fieldProbe.y=Number($('probe-y').value+'e-3');fieldProbe.active=true;redraw();refreshPersistence();};
 $('clear-probe').onclick=()=>{fieldProbe.active=false;redraw();refreshPersistence();};
}
// A µm view coordinate as an nm input value (0.1 nm resolution, a plain number for the field).
const nmValue=um=>String(Number((um*1000).toFixed(1)));
function probeOutput(host,id){const output=document.createElement('p');output.id=id;output.className='probe-output';output.setAttribute('role','status');host.append(output);return output;}

function renderField(){
 if(fieldResize)fieldResize.disconnect();
 // the mode shown is one of this run's modes (a run may find fewer than another)
 fieldView.mode=Math.min(fieldView.mode,solverRun.effective_index.length-1);
 const host=document.createElement('section');host.className='field-result';host.innerHTML=`<div class="toolbar"><label>Mode <select id="field-mode">${solverRun.effective_index.map((_,i)=>i).map(i=>`<option value="${i}" ${i===fieldView.mode?'selected':''}>${escapeHtml(modeOptionLabel(i,opticalModes(solverRun)))}</option>`).join('')}</select></label><label>Quantity <select id="field-component">${['magnitude','Ex','Ey','Ez'].map(c=>`<option ${c===fieldView.component?'selected':''} value="${c}">${c==='magnitude'?'|E|':'|'+c+'|'}</option>`).join('')}</select></label><label>View <select id="field-window">${['Core region','Full window'].map(c=>`<option ${c===fieldView.window?'selected':''}>${c}</option>`).join('')}</select></label></div><canvas id="optical-field" role="img" style="display:block;width:100%;height:var(--optical-plot-height,340px)"></canvas><div style="display:flex;align-items:center;gap:10px;padding:10px 0"><span>0</span><div style="flex:1;height:12px;background:linear-gradient(to right,#12263b,#176f8b,#45bb9f,#f9eb82)"></div><span>1</span></div><p id="field-description"></p>`;
 $('canvas').append(host);
 for(const [id,key] of [['field-mode','mode'],['field-component','component'],['field-window','window']])$(id).onchange=()=>{fieldView[key]=key==='mode'?+$(id).value:$(id).value;drawField();profileRedraw();};
 probeOutput(host,'field-probe');addProbeControls(host,()=>drawField());fieldResize=new ResizeObserver(()=>{if($('optical-field'))drawField();});fieldResize.observe(host);drawField();renderLineProfile(host,[solverRun]);
}
function drawField(canvas=$('optical-field'),run=solverRun,descriptionTarget=$('field-description'),sampleTarget=$('field-probe'),redraw=()=>drawField(),mode=fieldView.mode){
 if(!canvas||!run)return;
 const {values,maximum}=fieldScalars(run.field,mode,fieldView.component);
 const box=canvas.getBoundingClientRect(),w=box.width,h=box.height;if(w<1||h<1)return;
 const dpr=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);const ctx=canvas.getContext('2d');ctx.scale(dpr,dpr);ctx.fillStyle='#12202a';ctx.fillRect(0,0,w,h);
 const full=fieldView.window==='Full window',region=regionBounds(run.input.model,.4,.9,.72),xmin=full?-1.5:region[0],xmax=full?1.5:region[1],ymin=full?-1.2:region[2],ymax=full?1.2:region[3];
 const margin={left:54,right:20,top:20,bottom:45};const scale=Math.min((w-margin.left-margin.right)/(xmax-xmin),(h-margin.top-margin.bottom)/(ymax-ymin));
 const pw=(xmax-xmin)*scale,ph=(ymax-ymin)*scale,left=margin.left+(w-margin.left-margin.right-pw)/2,top=margin.top;
 const X=x=>left+(x-xmin)*scale,Y=y=>top+(ymax-y)*scale;
 // the drawn window in µm, so a check can compare plots of the same run
 canvas.dataset.viewBounds=[xmin,xmax,ymin,ymax].join(',');
 ctx.save();ctx.beginPath();ctx.rect(left,top,pw,ph);ctx.clip();
 run.field.triangles.forEach((triangle,i)=>{ctx.beginPath();triangle.forEach((n,j)=>{const p=run.field.nodes[n];if(j)ctx.lineTo(X(p[0]),Y(p[1]));else ctx.moveTo(X(p[0]),Y(p[1]));});ctx.closePath();ctx.fillStyle=fieldColor(values[i]);ctx.fill();});
 ctx.strokeStyle='#f5f1da';ctx.setLineDash([4,3]);ctx.lineWidth=1;for(const shape of run.input.model.shapes){ctx.beginPath();if(shape.type==='circle')ctx.arc(X(shape.cx/1000),Y(shape.cy/1000),shape.r/1000*scale,0,2*Math.PI);else shapeCorners(shape).forEach(([x,y],i)=>i?ctx.lineTo(X(x/1000),Y(y/1000)):ctx.moveTo(X(x/1000),Y(y/1000)));ctx.closePath();ctx.stroke();}
 if(profileState.open){ctx.strokeStyle='#e7bc73';ctx.setLineDash([8,4]);ctx.lineWidth=1.5;ctx.beginPath();if(profileState.axis==='x'&&profileState.coordinate>=ymin&&profileState.coordinate<=ymax){ctx.moveTo(X(xmin),Y(profileState.coordinate));ctx.lineTo(X(xmax),Y(profileState.coordinate));}else if(profileState.axis==='y'&&profileState.coordinate>=xmin&&profileState.coordinate<=xmax){ctx.moveTo(X(profileState.coordinate),Y(ymin));ctx.lineTo(X(profileState.coordinate),Y(ymax));}ctx.stroke();}ctx.restore();
 ctx.strokeStyle='#91a8b7';ctx.strokeRect(left,top,pw,ph);ctx.fillStyle='#cfdae0';ctx.font='12px Segoe UI';ctx.textAlign='center';
 for(const x of nmTicks(xmin,xmax,Math.max(3,Math.min(7,Math.floor(pw/64)))))ctx.fillText(formatNm(x),X(x),top+ph+18);
 ctx.fillText('x [nm]',left+pw/2,top+ph+38);ctx.textAlign='right';for(const y of nmTicks(ymin,ymax,Math.max(3,Math.min(7,Math.floor(ph/40)))))ctx.fillText(formatNm(y),left-8,Y(y)+4);
 ctx.save();ctx.translate(13,top+ph/2);ctx.rotate(-Math.PI/2);ctx.textAlign='center';ctx.fillText('y [nm]',0,0);ctx.restore();
 const q=fieldView.component==='magnitude'?'|E|':'|'+fieldView.component+'|';const description=`Mode ${mode+1}: ${q} / max|E|, relative amplitude (0–1). Each mode uses its own vector maximum. Triangle-centroid samples, constant color per triangle; dashed outlines = shapes. Not absolute power.${maximum===0?' Zero field returned.':''}`;
 if(descriptionTarget)descriptionTarget.textContent=description;canvas.setAttribute('aria-label',description);
 if(sampleTarget){
  sampleTarget.textContent='No point selected.';
  if(fieldProbe.active){
   const sample=probeField(run.field,values,fieldProbe.x,fieldProbe.y);
   sampleTarget.textContent=sample?`At (${formatNm(fieldProbe.x,1)}, ${formatNm(fieldProbe.y,1)}) nm: ${q} / max|E| = ${sample.value.toPrecision(6)} · triangle ${sample.index+1}, centroid (${formatNm(sample.centroid[0],1)}, ${formatNm(sample.centroid[1],1)}) nm. Stored centroid value, not interpolated.`:'No triangle contains this point in the captured result.';
   if(fieldProbe.x>=xmin&&fieldProbe.x<=xmax&&fieldProbe.y>=ymin&&fieldProbe.y<=ymax){const px=X(fieldProbe.x),py=Y(fieldProbe.y);ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.beginPath();ctx.moveTo(px-6,py);ctx.lineTo(px+6,py);ctx.moveTo(px,py-6);ctx.lineTo(px,py+6);ctx.stroke();}
  }
  canvas.style.cursor='crosshair';canvas.onclick=event=>{
   const rect=canvas.getBoundingClientRect(),px=(event.clientX-rect.left)*w/rect.width,py=(event.clientY-rect.top)*h/rect.height;
   if(px<left||px>left+pw||py<top||py>top+ph)return;
   fieldProbe.x=Math.max(xmin,Math.min(xmax,xmin+(px-left)/scale));fieldProbe.y=Math.max(ymin,Math.min(ymax,ymax-(py-top)/scale));fieldProbe.active=true;
   if($('probe-x'))$('probe-x').value=nmValue(fieldProbe.x);if($('probe-y'))$('probe-y').value=nmValue(fieldProbe.y);redraw();refreshPersistence();
  };
 }

}


// "mode 1" when every run shows the same rank, else "A mode 1 · B mode 3"
const modeWords=modes=>modes.every(m=>m===modes[0])?`mode ${modes[0]+1}`:modes.map((m,i)=>`${i?'B':'A'} mode ${m+1}`).join(' · ');
// modes: the mode shown for each run, read at each redraw (Results follows its Mode picker)
function renderLineProfile(host,profileRuns,updateFields=()=>drawField(),shownModes=()=>profileRuns.map(()=>fieldView.mode)){
 const details=document.createElement('details');details.className='line-profile';details.open=profileState.open;
 const summary=document.createElement('summary');summary.textContent='Line profile and CSV';details.append(summary);
 const form=document.createElement('form');form.className='profile-controls';form.innerHTML='<label>Profile direction<select id="profile-axis" aria-label="Profile direction"><option value="x">Horizontal · along x</option><option value="y">Vertical · along y</option></select></label><label>Fixed coordinate [nm]<input id="profile-coordinate" type="number" step="any" required></label><button type="submit">Show profile</button>';details.append(form);
 const description=document.createElement('p');description.setAttribute('role','status');details.append(description);
 const canvas=document.createElement('canvas');canvas.style.cssText='display:block;width:100%;height:260px';canvas.setAttribute('role','img');details.append(canvas);
 const legend=document.createElement('div');legend.className='profile-legend';details.append(legend);
 const note=document.createElement('p');note.textContent='Step segments use the stored value of each intersected triangle. No interpolation or absolute power. Each mode uses its own max|E| normalization.';details.append(note);
 const csv=document.createElement('button');csv.type='button';csv.textContent='Export profile CSV';csv.disabled=true;details.append(csv);const png=document.createElement('button');png.type='button';png.textContent='Export profile PNG';png.style.marginLeft='8px';png.disabled=true;details.append(png);host.append(details);
 $('profile-axis').value=profileState.axis;$('profile-coordinate').value=nmValue(profileState.coordinate);
 const range=()=>{const extent=$('profile-axis').value==='x'?1200:1500;$('profile-coordinate').min=-extent;$('profile-coordinate').max=extent;};range();$('profile-axis').onchange=range;
 let series=[],cacheKey='';
 profileRedraw=()=>{if(!details.isConnected||!details.open)return;try{
  const modes=shownModes();
  const key=JSON.stringify([profileState.axis,profileState.coordinate,modes,fieldView.component]);if(key!==cacheKey){series=profileRuns.map((run,i)=>({run,mode:modes[i],segments:lineProfile(run.field,fieldScalars(run.field,modes[i],fieldView.component).values,profileState.axis,profileState.coordinate)}));cacheKey=key;}
  const q=fieldView.component==='magnitude'?'|E|':'|'+fieldView.component+'|';description.textContent=`Displayed: ${profileState.axis==='x'?'y':'x'} = ${formatNm(profileState.coordinate,1)} nm · ${modeWords(modes)} · ${q} / max|E| (0–1). Full-domain profile; the amber dashed line marks its location in the field view when visible.`;
  legend.replaceChildren();series.forEach((item,i)=>{const line=document.createElement('p');line.style.color=i?'#e7bc73':'#80d7c0';line.textContent=`${i?'B':'A'} · ${runLabel(item.run)} · ${item.segments.length} intervals`;legend.append(line);});
  drawProfile(canvas,series,profileState.axis,profileState.coordinate);csv.disabled=!series.some(item=>item.segments.length);png.disabled=csv.disabled;
 }catch(error){description.textContent='Profile unavailable: '+error.message;csv.disabled=true;png.disabled=true;}};
 form.onsubmit=event=>{event.preventDefault();if(!form.reportValidity())return;profileState.axis=$('profile-axis').value;profileState.coordinate=Number($('profile-coordinate').value+'e-3');profileRedraw();updateFields();refreshPersistence();};
 details.ontoggle=()=>{if(!details.isConnected)return;profileState.open=details.open;profileRedraw();updateFields();refreshPersistence();};
 csv.onclick=()=>downloadFile(new Blob([profileCsv(series,profileState.axis,profileState.coordinate,fieldView.mode,fieldView.component)],{type:'text/csv'}),'studio-profile.csv');
 png.onclick=()=>{
  const out=document.createElement('canvas');out.width=canvas.width;out.height=canvas.height+180;const ctx=out.getContext('2d');ctx.fillStyle='#12202a';ctx.fillRect(0,0,out.width,out.height);ctx.drawImage(canvas,0,0);ctx.font='14px Segoe UI';ctx.fillStyle='#cfdae0';
  const modes=series.map(item=>item.mode),q=fieldView.component==='magnitude'?'|E|':'|'+fieldView.component+'|';ctx.fillText(`Line ${profileState.axis==='x'?'y':'x'} = ${formatNm(profileState.coordinate,1).replace('−','-')} nm | ${modeWords(modes)} | ${q} / max|E|`,12,canvas.height+24);
  ctx.fillText('Relative amplitude 0 to 1 per mode. Stored triangle values; no interpolation.',12,canvas.height+48);
  series.forEach((item,i)=>{ctx.fillStyle=i?'#e7bc73':'#80d7c0';ctx.fillText(`${i?'B':'A'}: ${item.run.job} | ${designSummary(item.run.input.model)} | ${item.run.input.model.wavelength} nm | ${item.run.origin}`,12,canvas.height+76+i*24);});
  ctx.fillStyle='#cfdae0';ctx.fillText('Full domain. No absolute-power claim.',12,canvas.height+142);out.toBlob(blob=>{if(blob)downloadFile(blob,'studio-profile.png');},'image/png');
 };
 profileResize=new ResizeObserver(profileRedraw);profileResize.observe(canvas);profileRedraw();
}

function downloadFile(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
// ---- File › Save and Save As (workspace-files.mjs) ----
// currentFile: the model's current file (workspace-files.mjs rememberFile), {name, handle, how,
// scope}: the name Save As or the Save name dialog chose, the file the picker wrote, or the file
// File › Open read. Save writes the picker's file again, or downloads under the name, while scope
// still names the same model: every open, model switch and Reset design moves fileScope on, so
// Save never writes one model's session into another's file or under another model's name.
// (declared with pendingLoad, above: the header reads it from the first render)
function fileScopeKey(){return (multiView.active()?'multiphysics':applicationSlug())+':'+fileScope;}
function currentFileNow(){return currentFileFor(currentFile,fileScopeKey());}
// a file File › Open read becomes the current file of the model it opened (after that open's scope)
function rememberOpened(name,how='opened'){if(name){currentFile=rememberFile({name,how,scope:fileScopeKey()});refreshPersistence();}}
// A browser restore whose record still matched the session file it names (the title's "same as
// file X"): X becomes the current file, so Save downloads under it and Save As suggests it (round 14).
const recoveredFileName=(savedFile,openedFile,openedCurrent)=>savedFile?.current===true?savedFile.name:!savedFile&&openedFile&&openedCurrent===true?openedFile:null;
// The name dialog, where the browser has no save picker or the picker could not be used: the
// file name (letters, digits, spaces, . _ - ( ) only; .json added), then a download.
const nameDialog=document.createElement('dialog');nameDialog.id='save-name-dialog';nameDialog.setAttribute('aria-labelledby','save-name-title');nameDialog.setAttribute('aria-describedby','save-name-note');
nameDialog.innerHTML='<form method="dialog"><h2 id="save-name-title">Save As</h2><p id="save-name-contents" hidden></p><p id="save-name-unavailable" hidden></p><label for="save-name-input">File name</label><input id="save-name-input" type="text" autocomplete="off" spellcheck="false" maxlength="200" aria-describedby="save-name-hint"><small id="save-name-hint">Letters, digits, spaces and . _ - ( ) only; .json is added if missing.</small><p id="save-name-note">Your browser saves to its Downloads folder, or asks where if you set it to.</p><div class="leave-actions"><button type="button" id="save-name-cancel">Cancel</button> <button type="submit" id="save-name-download" class="primary">Download</button></div></form>';
document.body.append(nameDialog);
// Round 16: the Save As note on the download path (the Chrome and Edge sentence is in the docs only)
const DOWNLOAD_SAVE_AS_NOTE='This browser cannot write to the file, so later saves download again under this name and may add “ (1)”.';
let nameAnswer=null;
// Resolves the sanitised name, or null on Cancel or Escape.
// nameDialogContents: what a project file will hold (round 18, X5), set for the time of a project save
// (deliverProject), so the dialog says it on every project save; null for other files
let nameDialogContents=null;
function askFileName(suggested,{saveAs,unavailable=null,why=null}){
 return new Promise(resolve=>{
  const opener=document.activeElement;
  nameAnswer=value=>{nameAnswer=null;if(nameDialog.open)nameDialog.close();restoreDialogFocus(opener);resolve(value);};
  $('save-name-title').textContent=saveAs?'Save As':'Save';
  const contents=nameDialogContents;$('save-name-contents').hidden=!contents;$('save-name-contents').textContent=contents||'';
  // why: the reason Save asks (round 17, U8), in the same line as an unavailable picker's
  $('save-name-unavailable').hidden=!unavailable&&!why;$('save-name-unavailable').textContent=[why,unavailable?`The browser's save dialog was not available (${unavailable}), so the file is downloaded instead.`:''].filter(Boolean).join(' ');
  $('save-name-note').textContent='Your browser saves to its Downloads folder, or asks where if you set it to.'+(saveAs?' '+DOWNLOAD_SAVE_AS_NOTE:' If that folder already has a file of this name, the browser may add “ (1)” to the new one.');
  const input=$('save-name-input');input.value=suggested;nameDialog.showModal();input.focus();input.select();
 });
}
$('save-name-input').oninput=event=>{if(event.isComposing)return;const el=event.target,clean=el.value.replace(/[^A-Za-z0-9 ._()-]+/g,'');if(clean!==el.value){const at=el.selectionStart-(el.value.length-clean.length);el.value=clean;el.setSelectionRange(Math.max(0,at),Math.max(0,at));}};
nameDialog.querySelector('form').onsubmit=event=>{event.preventDefault();nameAnswer?.(sanitizeFileName($('save-name-input').value,$('save-name-input').defaultValue||'session.json'));};
$('save-name-cancel').onclick=()=>nameAnswer?.(null);
nameDialog.oncancel=event=>{event.preventDefault();nameAnswer?.(null);};
// Delivers a session file's text: the picker file (Save with a target, or Save As where the
// picker works), else the name dialog and a download. Resolves {written, name, via, after} or
// {written: false, message}. Called inside the click or key press, before anything is awaited.
function deliverSession(text,suggestedName,{saveAs}){
 savingFile=true;const scope=fileScopeKey(),target=currentFileNow(),prefill=suggestedSaveName(target,suggestedName);
 const keep=(name,how,handle=null)=>{if(fileScopeKey()===scope)currentFile=rememberFile({name,how,handle,scope});};
 return saveToFile(text,{suggestedName:prefill,target,saveAs}).then(async result=>{
  if(result.status==='saved'){keep(result.name,'picker',result.handle);return {written:true,name:result.name,via:'picker',after:''};}
  // Save with a known name and no picker: downloaded again under it, without asking
  if(result.status==='known'){downloadFile(new Blob([text],{type:'application/json'}),result.name);keep(result.name,'download');
   return {written:true,name:result.name,via:'download',again:target.how==='download',known:true,after:' '+downloadAgainNote(result.name)};}
  if(result.status!=='unavailable')return {written:false,message:notWrittenNotice(result,{saveAs})};
  $('save-name-input').defaultValue=prefill;
  const name=await askFileName(prefill,{saveAs,unavailable:result.error});
  if(!name)return {written:false,message:notWrittenNotice({status:'cancelled'},{saveAs})};
  downloadFile(new Blob([text],{type:'application/json'}),name);keep(name,'download');
  // the name dialog said before the download that the browser may add " (1)"; Messages says what happened
  return {written:true,name,via:'download',after:''};
 }).finally(()=>{savingFile=false;});
}
// The start of a save notice: what happened to the file, and no more.
const savedWhere=result=>result.via==='picker'?`Saved to ${result.name}`:result.known&&result.again?`Downloaded ${result.name} again`:`Session file ${result.name} sent to your browser's Downloads`;
// A run as the run list, Compare and the profile legend name it: its name, design, wavelength
// and completion time. The job id is in Run details, not here: hash ids made labels wrap.
// with seconds: unnamed runs of the same minute read apart
const runTime=run=>new Date(run.completedAt).toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});
// A run in the run list and the Compare pickers: its number with its name, then its inputs and time.
// a run's number in this tab (round 17, U2): it never changes while the run is kept
function runNumber(run){return runs.includes(run)&&Number.isInteger(run.number)?run.number:null;}
function runLabel(run){const n=runNumber(run);return `${n?runTitle(n,run.label)+' · ':run.label?run.label+' · ':''}${runDesign(run)} · λ ${run.input.model.wavelength} nm · ${runTime(run)}${run.origin==='imported'?' · from file':run.origin==='recovered'?' · recovered':''}`;}
// Where a run came from, kept out of the primary labels and available on request.
// The modes table of a run: | Mode | n_eff | Polarization | Absorption loss (dB/cm) | A_eff (µm²) | n_g |, one merged polarization
// cell per degenerate pair, and the absorption-loss note once below the table.
// An open run (slice P2): "Loss (dB/cm)" with the open boundary's cells ("< 0.01 dB/cm" below what it
// resolves), n_eff with its Im part, and the PML check column when the check ran; polarization and
// A_eff on the physical window, the PML excluded, and Re n_g (slice P3).
function modesTable(run){
 const box=document.createElement('div');box.className='modes-table';
 const open=isOpenRun(run),{rows,loss}=modeTableRows(opticalModes(run),{open,...(open?{areaHelp:OPEN_AREA_HELP,polarizationHelp:OPEN_POLARIZATION_HELP,missing:SOURCE_TEXT.noWindow,areaMissing:SOURCE_TEXT.noWindow}:{})});
 const lambda0=run.input.model.wavelength*1e-9,im=run.effective_index_im,candidates=open?openStatuses(run):null;
 const checks=open&&run.pml_check?run.effective_index.map((re,i)=>checkVerdict(re,im[i],run.pml_check.paired[i],lambda0,candidates[i])):null;
 if(open)rows.forEach((r,i)=>{const cell=openLoss(im[i],lambda0,candidates[i]);r.neff=openIndexText(run.effective_index[i],im[i]);r.loss=cell.text;r.lossTitle=cell.title;r.lossFloor=cell.floor;r.depends=checks?.[i].status==='depends';if(r.depends)r.lossTitle=DEPENDS_HELP;});
 const table=document.createElement('table');table.id='modes-table';
 const caption=document.createElement('caption');caption.textContent=open?openTableTitle():'Computed modes';table.append(caption);
 const cell=(tag,text,attrs={})=>{const el=document.createElement(tag);el.textContent=text;for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);return el;};
 const head=document.createElement('tr');head.append(cell('th','Mode',{scope:'col'}),cell('th','n_eff',{scope:'col'}),cell('th','Polarization',{scope:'col',title:open?OPEN_POLARIZATION_HELP:POLARIZATION_HELP}),cell('th',loss.header,{scope:'col',title:loss.help}),cell('th','A_eff (µm²)',{scope:'col',title:open?OPEN_AREA_HELP:AREA_HELP}),cell('th','n_g',{scope:'col',title:groupIndexHelp()}));
 if(checks)head.append(cell('th',CHECK_HEADER,{scope:'col',title:CHECK_HELP}));
 const thead=document.createElement('thead');thead.append(head);table.append(thead);
 // the n_g hint, when the run has no n_g: on a line above the table (as Compare has it), the header just "n_g"
 if(!hasGroupIndex(run))box.append(groupIndexHintLine('modes-table-hint'));
 const body=document.createElement('tbody');
 // round 17 (U1): a closed-window mode mostly in a shape touching the window edge gets a note row,
 // after its row (after the last row of a degenerate group, whose polarization cell spans the group)
 // slice C2: a closed-window search names its core mode the same way (Mode 2 is the core mode: …)
 const edge=new Map(edgeNotes(run).map(n=>[n.mode,n.text])),core=new Map(coreNotes(run).map(n=>[n.mode,n.text])),pending=[];let spanEnd=-1;
 const described=m=>[...(edge.has(m-1)?['edge-note-'+m]:[]),...(core.has(m-1)?['core-note-'+m]:[])].join(' ');
 for(const r of rows){const tr=document.createElement('tr');tr.append(cell('th',r.label,{scope:'row',...(described(r.mode)?{'aria-describedby':described(r.mode)}:{})}),cell('td',r.neff,{'data-neff':String(r.mode)}));
  if(r.polarization?.rowspan>1)spanEnd=r.mode-1+r.polarization.rowspan-1;if(edge.has(r.mode-1)||core.has(r.mode-1))pending.push(r.mode);
  if(r.polarization)tr.append(cell('td',r.polarization.text,{title:r.polarization.title,'data-polarization':String(r.mode),...(r.polarization.rowspan>1?{rowspan:String(r.polarization.rowspan)}:{})}));
  {const lossCell=cell('td',r.loss,{'data-loss':String(r.mode),title:r.lossTitle,...(r.depends?{'data-pml-dependent':'',class:'pml-dependent'}:{})});if(r.depends){lossCell.textContent='';const em=document.createElement('em');em.textContent=r.loss;lossCell.append(em);}tr.append(lossCell);}
  tr.append(cell('td',r.area.text,{title:r.area.title,'data-area':String(r.mode),...(r.area.value===null?{}:{'data-area-value':String(r.area.value)})}));
  {const g=groupIndexCell(run,r.mode-1);tr.append(cell('td',g.text,{title:g.title,class:'num','data-group-index':String(r.mode),...(g.value===null?{}:{'data-group-index-value':String(g.value)})}));}
  if(checks){const c=checks[r.mode-1],td=cell('td','',{'data-pml-check':String(r.mode),'data-pml-check-status':c.status,title:c.title});if(c.status==='depends'){const strong=document.createElement('strong');strong.textContent='Depends on the PML';td.append(strong,c.text.slice('Depends on the PML'.length));}else td.textContent=c.text;tr.append(td);}
  body.append(tr);
  if(pending.length&&r.mode-1>=spanEnd){for(const m of pending.splice(0)){
   if(edge.has(m-1)){const note=document.createElement('tr');note.className='edge-note-row';const td=cell('td',edge.get(m-1),{colspan:String(head.children.length),id:'edge-note-'+m,'data-edge-note':String(m),class:'edge-note'});note.append(td);body.append(note);}
   if(core.has(m-1)){const note=document.createElement('tr');note.className='edge-note-row core-note-row';const td=cell('td',core.get(m-1),{colspan:String(head.children.length),id:'core-note-'+m,'data-core-note':String(m),class:'edge-note'});note.append(td);body.append(note);}}}}
 table.append(body);box.append(table);
 // round 18 (X9): in a row under the last edge note (the note's own text unchanged), the inputs that find such a mode: Use Open boundary and,
 // since slice C2 (Q2, Q5, Q8), Search near 2.46 · 4 modes (the design's default target, the closed window kept), in place of
 // C0's Set Modes to find to M; each sets the inputs with a message and runs nothing, and is left out when the current inputs
 // already have it
 {const last=[...body.querySelectorAll('[data-edge-note]')].at(-1);if(last){const near=defaultTarget(state.shapes),actions=document.createElement('span');actions.className='edge-actions';actions.id='edge-actions';
  if(!state.openBoundary){const b=document.createElement('button');b.type='button';b.className='message-action';b.id='edge-use-open';b.textContent='Use Open boundary';b.onclick=()=>{if(!state.openBoundary)setOuterBoundary(true);};actions.append(b);}
  if(!state.openBoundary&&!(state.searchTarget===near&&state.modeCount===SHORTCUT_MODE_COUNT)){const b=document.createElement('button');b.type='button';b.className='message-action';b.id='edge-search-near';b.textContent=shortcutText(near);b.onclick=()=>useClosedSearch(near);actions.append(b);}
  if(actions.children.length){const tr=document.createElement('tr');tr.className='edge-note-row edge-actions-row';const td=cell('td','',{colspan:last.getAttribute('colspan'),class:'edge-note'});td.append(actions);tr.append(td);last.parentElement.after(tr);}}}
 // slice C2 (A1): a closed-window search lists only modes above n = 1.45 and says how many it left out
 if(isClosedTargetRun(run)){const out=leftOutText(run.effective_index.length,runModeCount(run));if(out){const note=document.createElement('p');note.className='table-note';note.id='left-out-note';note.textContent=out;box.append(note);}}
 const help=document.createElement('p');help.className='table-note';help.textContent=`Polarization: ${open?OPEN_POLARIZATION_HELP:POLARIZATION_HELP}. TE-like at 90 % TE or more, TM-like at 10 % or less, otherwise hybrid. A_eff: ${open?OPEN_AREA_HELP:AREA_HELP+'.'}`;box.append(help);
 // the loss note: absorption only, with the lossless words when every mode has k = 0
 // (a closed window adds where leakage is found: Open boundary in Physics › Optical modes)
 {const note=document.createElement('p');note.className='table-note';note.id=rows.every(r=>r.lossless)?'lossless-note':'loss-note';note.textContent=open?loss.note:loss.note+' '+CLOSED_POINTER;box.append(note);}
 return box;
}
// The attenuation status of each mode of an open run (its candidate's), or null.
function openStatuses(run){
 const c=run.open_boundary.candidates;
 return run.effective_index.map((re,i)=>c.find(x=>x.selected&&x.effective_index.re===re&&x.effective_index.im===run.effective_index_im[i])?.attenuation_status??null);
}
function runDetails(run){
 opticalModes(run);
 const rows=[['Job',run.job],['Completed',new Date(run.completedAt).toLocaleString()],['Source',run.origin==='local'?'Computed by this Studio':run.origin==='recovered'?'Browser recovery':'Imported file'],...(run.serverVersion?[['simcase version',run.serverVersion]]:[]),...(Number.isInteger(run.inputRevision)?[['Input change in this tab',String(run.inputRevision)]]:[]),['Polarization (TE fraction)',SOURCE_TEXT[run.te.source]],['Effective area',SOURCE_TEXT[run.area.source]]];
 return '<details class="run-details" id="run-details"'+(ui.runDetailsOpen?' open':'')+'><summary>Run details</summary>'+rows.map(([a,b])=>pair(a,escapeHtml(b))).join('')+'</details>';
}
const pinNotice=run=>run.pinned?'Run pinned: new runs will not replace it. File › Save keeps it in a file.':'Run unpinned: once six runs are kept, a new run replaces the oldest unpinned one. Press Enter in Run name to pin it again.';
// Naming applies on Enter or when the field is left, and pins the run. Leaving the field
// updates the panel in place, so a click on another control in it is not lost to a redraw.
function nameRun(run,value,redraw){
 let label;try{label=validateRunLabel(value);}catch(error){notice(error.message);return;}
 if(label===(run.label||'')&&(!label||run.pinned))return;
 // a name pins the run, except while a calculation runs: pinning the last free slot then
 // would leave the finishing result nowhere to go
 const pinBlocked=(solverBusy||!!pendingJob)&&!run.pinned;
 run.label=label;if(label&&!pinBlocked)run.pinned=true;
 if(redraw)render();else{
  document.querySelectorAll('[data-run]').forEach(b=>{const r=runs.find(x=>x.job===b.dataset.run);if(r)b.textContent=runItemText(r);});
  document.querySelectorAll('#compare-a option,#compare-b option').forEach(o=>{const r=runs.find(x=>x.job===o.value);if(r){o.textContent=runLabel(r);o.title=o.textContent;}});document.querySelectorAll('#compare-a,#compare-b').forEach(sel=>{sel.title=sel.selectedOptions[0]?.textContent||'';});
  document.querySelectorAll('.compare-grid article h3').forEach((h,i)=>{const r=runs.find(x=>x.job===compareIds[i]);if(r)h.textContent=fieldHeading(i?'B':'A',r,runNumber(r));});
  profileRedraw();syncUnpinButton();if($('run-list-heading'))$('run-list-heading').textContent=runListHeading();
  document.querySelectorAll('#compare-table-runs [data-side]').forEach((h,i)=>{const r=runs.find(x=>x.job===compareIds[i]);if(r)h.textContent=h.dataset.side+' · '+runHeading(r,runNumber(r));});
  // the dock heading, the footer and the title name the run too (refreshInputIssues rewrites all three)
  if($('open-in-results')&&run===solverRun)$('open-in-results').textContent=`Open ${runTitle(runNumber(run),run.label)} in Results`;if($('run-name-value'))$('run-name-value').textContent=run.label||'Not named';refreshInputIssues();
 }
 notice(label&&pinBlocked?`Run named “${label}”. It is not pinned while a calculation runs; press Enter in Run name when the calculation ends to pin it.`:label?`Run named “${label}” and pinned: new runs will not replace it. File › Save keeps it in a file.`:'Run name cleared.'+(run.pinned?' The run stays pinned until you unpin it.':''));
}
// Naming a run pins it, so the run list offers only Unpin, for a pinned run; an unpinned run is
// kept again by naming it (Enter in Run name). Updated in place so the name field keeps focus.
function syncUnpinButton(){
 const slot=$('unpin-slot');if(!slot)return;const pinned=!!solverRun?.pinned;let button=$('pin-run');
 if(!pinned){button?.remove();return;}
 if(!button){button=document.createElement('button');button.id='pin-run';button.type='button';button.textContent='Unpin this run';button.onclick=()=>{solverRun.pinned=false;render();$('run-name-input')?.focus();notice(pinNotice(solverRun));};slot.append(button);}
}
const runItemText=run=>(run.pinned?'Pinned · ':'')+runLabel(run);
const runListHeading=()=>`Runs · ${runs.length} of ${RUN_LIMIT} · ${runs.filter(r=>r.pinned).length} pinned`;
function renderRunList(){
 const panel=$('inspector');if(ui.page==='Compare')panel.innerHTML='<h2>Runs</h2>';
 const importRuns=document.createElement('button');importRuns.id='import-runs';importRuns.textContent='Add runs from file (inputs unchanged)';importRuns.title='Adds the runs in a session or run file to this list; the current inputs are not replaced';importRuns.disabled=solverBusy||!!pendingJob;importRuns.onclick=()=>$('run-import-file').click();panel.append(importRuns);
 const title=document.createElement('h3');title.id='run-list-heading';title.textContent=runListHeading();panel.append(title);
 for(const run of [...runs].reverse()){
  const b=document.createElement('button');b.className='run-item';b.setAttribute('aria-pressed',String(solverRun?.job===run.job));b.dataset.run=run.job;b.textContent=runItemText(run);
  // on Compare the two compared runs say which side they are, so the newest-first list and A/B agree
  const side=ui.page==='Compare'&&runs.length>1?compareSide(run.job,compareIds):'';if(side){const sep=document.createElement('span');sep.className='compare-side-sep';sep.textContent=' · ';const tag=document.createElement('span');tag.className='compare-side';tag.textContent=`Compare ${side}`;b.append(sep,tag);}
  // on Compare a run click selects the run and stays on Compare (the A and B pickers choose what
  // is compared); Open in Results below shows it there. Elsewhere it opens Results on that run.
  b.onclick=()=>{solverRun=run;if(ui.page!=='Compare')ui.page='Results';render();if(ui.page==='Compare')document.querySelector(`.run-item[data-run="${CSS.escape(run.job)}"]`)?.focus();};panel.append(b);
 }
 if(ui.page==='Compare'&&solverRun){const open=document.createElement('button');open.type='button';open.id='open-in-results';open.textContent=`Open ${runTitle(runNumber(solverRun),solverRun.label)} in Results`;open.title='Shows the selected run in Results; the comparison stays as it is';open.onclick=()=>{ui.page='Results';render();};panel.append(open);}
 if(solverRun){
  const unpinSlot=document.createElement('span');unpinSlot.id='unpin-slot';panel.append(unpinSlot);syncUnpinButton();
  const nameForm=document.createElement('form');nameForm.className='run-name';
  const nameLabel=document.createElement('label');nameLabel.textContent='Run name';const nameInput=document.createElement('input');nameInput.id='run-name-input';nameInput.type='text';nameInput.maxLength=80;nameInput.value=solverRun.label||'';nameInput.placeholder='For example: design A';nameInput.setAttribute('aria-describedby','run-name-hint');nameLabel.append(nameInput);
  const rename=document.createElement('button');rename.id='rename-run';rename.type='submit';rename.textContent='Apply name';
  const hint=document.createElement('p');hint.id='run-name-hint';hint.className='input-hint';hint.textContent='Press Enter to apply. Naming a run pins it, so new runs do not replace it; Enter on a named, unpinned run pins it again.';
  nameForm.append(nameLabel,rename,hint);panel.append(nameForm);
  const target=solverRun;
  nameForm.onsubmit=event=>{event.preventDefault();nameRun(target,nameInput.value,true);};
  // Enter applies here, before the change event the browser fires ahead of an implicit submit
  nameInput.onkeydown=event=>{if(event.key==='Enter'&&!event.isComposing){event.preventDefault();nameRun(target,nameInput.value,true);}};
  nameInput.onchange=()=>{if(nameInput.isConnected)nameRun(target,nameInput.value,false);};
  const exportRun=document.createElement('button');exportRun.id='export-run';exportRun.textContent='Export this run';exportRun.style.marginTop='10px';exportRun.onclick=()=>{try{
   const text=sessionText(solverRun.input,[solverRun],solverRun.job,[solverRun.job,solverRun.job],currentView());
   if(new TextEncoder().encode(text).length>MAX_SESSION_BYTES)throw new Error('This run exceeds the session size limit.');
   const name='studio-run-'+solverRun.job+'.json';downloadFile(new Blob([text],{type:'application/json'}),name);notice(`Run file ${name} sent to the browser's downloads, with the run's inputs and fields${isOpenRun(solverRun)?' (on the physical window only, PML excluded)':''}. Add runs from file adds it to a session. The current design is unchanged.`);
  }catch(error){notice(error.message);}};panel.append(exportRun);
  // a viewed run with other inputs than the current ones: its inputs become the current inputs at
  // once (the runs stay as they are, so nothing is asked), and Undo takes them back
  if(solverRun.signature!==signature()){const restore=document.createElement('button');restore.id='restore-run-input';restore.className='primary';restore.textContent='Use this run’s inputs';const target=solverRun;restore.onclick=()=>useRunInputs(target);restore.disabled=numericDrafts.invalid;
   const why=document.createElement('p');why.id='restore-run-input-hint';why.className='input-hint';why.textContent=`The next run uses the current inputs (${designSummary(current().model)}). This loads ${runNumberTitle(target)}’s inputs instead; Undo takes them back.`;restore.setAttribute('aria-describedby',why.id);
   const slot=$('use-run-slot');if(slot)slot.append(restore,why);else panel.append(restore,why);}
  else if(runInputsNoteFor(solverRun)){const done=document.createElement('p');done.id='restore-run-input-done';done.className='input-hint';done.textContent=runInputsNoteFor(solverRun);const slot=$('use-run-slot');if(slot)slot.append(done);else panel.append(done);}
  const exportPng=document.createElement('button');exportPng.id='export-field';exportPng.textContent='Export field PNG';exportPng.style.marginTop='10px';exportPng.disabled=ui.page!=='Results';exportPng.onclick=()=>{
   const source=$('optical-field');if(!source)return;const out=document.createElement('canvas');out.width=source.width;out.height=source.height+170;const ctx=out.getContext('2d');ctx.fillStyle='#12202a';ctx.fillRect(0,0,out.width,out.height);ctx.drawImage(source,0,0);ctx.fillStyle='#cfdae0';ctx.font='14px Segoe UI';ctx.fillText(`Job ${solverRun.job} | mode ${fieldView.mode+1} | ${fieldView.component} / max|E|`,12,source.height+25);ctx.fillText('Relative amplitude 0–1 per mode; not absolute power.',12,source.height+48);ctx.fillText(`${designSummary(solverRun.input.model)} | wavelength ${solverRun.input.model.wavelength} nm | core mesh ${solverRun.input.model.coreMesh} nm | ${solverRun.origin}`,12,source.height+70);const grad=ctx.createLinearGradient(35,0,out.width-35,0);for(let i=0;i<=3;i++)grad.addColorStop(i/3,fieldColor(i/3));ctx.fillStyle=grad;ctx.fillRect(35,source.height+92,out.width-70,12);ctx.fillStyle='#cfdae0';ctx.fillText('0',12,source.height+104);ctx.fillText('1',out.width-20,source.height+104);ctx.fillText(fieldProbe.active?'Probe ('+formatNm(fieldProbe.x,1).replace('−','-')+', '+formatNm(fieldProbe.y,1).replace('−','-')+') nm; centroid sample, no interpolation.':'No probe point selected.',12,source.height+140);if(profileState.open)ctx.fillText('Profile line: '+(profileState.axis==='x'?'y':'x')+' = '+formatNm(profileState.coordinate,1).replace('−','-')+' nm (amber dashed).',12,source.height+162);out.toBlob(blob=>{if(blob)downloadFile(blob,'studio-field.png');},'image/png');
  };panel.append(exportPng);
  // The image is drawn from the Results plot; Compare shows two runs and has no single plot.
  if(ui.page!=='Results'){const why=document.createElement('p');why.id='export-field-hint';why.className='input-hint';why.textContent=ui.page==='Compare'?'Field images export from Results: Open in Results shows the selected run there.':'Field images export from Results: select a run in the list above to open it there.';exportPng.setAttribute('aria-describedby',why.id);panel.append(why);}
 }
 const csv=document.createElement('button');csv.id='export-table';csv.textContent='Export run table CSV';csv.disabled=!runs.length;csv.style.marginTop='10px';csv.onclick=()=>downloadFile(new Blob([runTableCsv(runs)],{type:'text/csv'}),'studio-runs.csv');panel.append(csv);
 const limit=document.createElement('p');limit.textContent=RUNS_KEPT_TEXT+' Pinned runs stay; when a new run arrives, the oldest unpinned run is replaced. File › Save keeps every run in one file; Export this run writes one run to its own file.';panel.append(limit);
}
// The n_g hint ("Off · turn on in Study or Optical modes", its help as title) after "n_g: ",
// for a line above a table whose runs did not compute n_g.
function groupIndexHint(){const hint=document.createElement('small');hint.dataset.groupIndexHint='';hint.textContent=GROUP_INDEX_HINT;hint.title=GROUP_INDEX_OFF_HELP;return hint;}
function groupIndexHintLine(id){const line=document.createElement('p');line.id=id;line.className='table-hint';line.append('n_g: ',groupIndexHint());return line;}
// The modes of A and B matched by field overlap on a common grid (workspace-match.mjs): one row
// per matched mode (or degenerate pair), then each mode of A and of B without a match. The columns
// (Modes, Polarization A B, Overlap, n_eff A B, Δn_eff, Δ %, A_eff A B, absorption loss A B, n_g A B)
// have short headers grouped as A | B; each leaf header keeps its full label in data-column. The
// row header reads "1 ↔ 1" with the full pairing as its accessible name and title. Round 13: at
// 1440 × 900 every column fits the box (a Polarization cell on two lines, the class then the
// share, its " · " kept in the text but not shown; the n_g hint on the line above the table, not
// in its header). Where the box is narrower (a phone) the first column stays in view while the
// others scroll, with a shadow at the right edge and a line saying so while columns are hidden.
function compareTable(a,b,match){
 const box=document.createElement('div');box.className='compare-table';
 const cell=(tag,text,attrs={})=>{const el=document.createElement(tag);el.textContent=text;for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);return el;};
 // "TE-like · 98.2 % TE" on two lines: the class, then the share; textContent stays the same
 const polarizationCell=text=>{const td=document.createElement('td');td.className='pol';const at=text.indexOf(' · ');
  if(at<0){td.textContent=text;return td;}
  const kind=document.createElement('span'),sep=document.createElement('span'),share=document.createElement('span');
  kind.className='pol-kind';kind.textContent=text.slice(0,at);sep.className='pol-sep';sep.textContent=' · ';share.className='pol-share';share.textContent=text.slice(at+3);td.append(kind,sep,share);return td;};
 if(match.error){box.append(cell('p','Modes not matched: '+match.error,{class:'table-note',id:'compare-match-error'}));return box;}
 const runs=document.createElement('p');runs.id='compare-table-runs';runs.className='table-runs';
 // each run names its boundary after its number and name (round 18, X6): "closed" or "open (PML 1 µm)"
 for(const [side,run] of [['A',a],['B',b]]){const line=document.createElement('span');line.dataset.side=side;line.textContent=side+' · '+runHeading(run,runNumber(run));runs.append(line);}
 // the n_g hint, when neither run computed n_g: on this line, so the n_g columns stay narrow
 if(![a,b].some(hasGroupIndex)){const line=document.createElement('span');line.className='table-hint';line.append('n_g: ',groupIndexHint());runs.append(line);}
 const frame=document.createElement('div');frame.className='compare-table-frame';
 const more=cell('p','Scroll sideways for all 14 columns ›',{class:'table-note scroll-hint','data-scroll-hint':''});more.hidden=true;
 const scroll=document.createElement('div');scroll.className='compare-table-scroll';scroll.tabIndex=0;scroll.setAttribute('role','region');scroll.setAttribute('aria-labelledby','compare-neff-caption');
 const table=document.createElement('table');table.id='compare-neff';
 const caption=document.createElement('caption');caption.id='compare-neff-caption';caption.textContent=match.disabled?'Modes of A and B (not matched)':'Modes of A and B matched by field overlap';table.append(caption);
 const head=document.createElement('thead'),top=document.createElement('tr'),sides=document.createElement('tr');
 // [short header, full label (one column) or the full label's start (A and B), help]
 const columns=[['Modes','Modes'],['Polarization','Polarization',POLARIZATION_HELP,true],['Overlap','Overlap'],['n_eff','n_eff',null,true],['Δn_eff (B − A)','Δn_eff (B − A)'],['Δ % (of A)','Δ % (of A)'],['A_eff (µm²)','A_eff',AREA_HELP,true,' (µm²)'],[isOpenRun(a)||isOpenRun(b)?'Loss (dB/cm)':'Absorption loss (dB/cm)','Absorption loss',isOpenRun(a)&&isOpenRun(b)?OPEN_LOSS_HELP:isOpenRun(a)||isOpenRun(b)?'Each side follows its run: material absorption only in a closed window, with leakage for an open boundary':ABSORPTION_HELP,true,' (dB/cm)'],['n_g','n_g',groupIndexHelp(),true]];
 for(const [short,full,help,paired,unit=''] of columns){
  if(!paired){top.append(cell('th',short,{scope:'col',rowspan:'2','data-column':full,...(help?{title:help}:{})}));continue;}
  const group=cell('th',short,{scope:'colgroup',colspan:'2',...(help?{title:help}:{})});top.append(group);
  // the loss of each side follows its own run: "Absorption loss A (dB/cm)" and "Loss B (dB/cm)"
  for(const [side,run] of [['A',a],['B',b]]){const loss=full==='Absorption loss'&&isOpenRun(run),name=loss?'Loss':full,h=loss?OPEN_LOSS_HELP:help;sides.append(cell('th',side,{scope:'col','data-column':`${name} ${side}${unit}`,title:`${name} ${side}${unit}`+(h?': '+h:''),...(full==='Polarization'?{class:'pol'}:{})}));}
 }
 // one column group per header of the first row, so its scope=colgroup headers name their two columns
 for(const [,,,paired] of columns){const group=document.createElement('colgroup');if(paired)group.span=2;table.append(group);}
 head.append(top,sides);table.append(head);
 // n_eff of a unit: the mode's, or the mean of a pair
 const index=(run,unit)=>unit.reduce((t,i)=>t+run.effective_index[i],0)/unit.length;
 const indexText=(run,unit)=>unit?(unit.length>1?'mean ':'')+formatIndex(index(run,unit)):'—';
 // A_eff of a unit: the mode's, or the mean of a pair with its note
 const areaCell=(run,unit,side)=>{if(!unit)return cell('td','—');const v=unitArea(run,unit);return cell('td',v.text,{title:v.title,['data-area-'+side]:v.value===null?'':String(v.value)});};
 // absorption loss of a unit, from the saved indices (the mode's, or the mean of a pair)
 // an open run's loss on two lines, the value then "dB/cm", as the polarization cells are (textContent
 // unchanged): with matched rows, "< 0.01 dB/cm" would otherwise widen the table past 1440 px (O2)
 const lossCell=(run,unit,side)=>{const v=unitLoss(run,unit),td=cell('td',v.text,{class:'num',title:v.title,['data-loss-'+side]:v.value===null?'':String(v.value)});
  const at=v.text.lastIndexOf(' dB/cm');if(isOpenRun(run)&&at>0){td.textContent='';td.classList.add('loss-split');const value=document.createElement('span'),sep=document.createElement('span'),u=document.createElement('span');
   value.className='loss-value';value.textContent=v.text.slice(0,at);sep.className='pol-sep';sep.textContent=' ';u.className='loss-unit';u.textContent='dB/cm';td.append(value,sep,u);}
  return td;};
 // round 17 (U4): an unmatched row's Overlap is the best overlap found, on two lines ("best 0.05" /
 // "(< 0.8, not matched)", textContent unchanged), so the column stays narrow
 const bestCell=(best,other)=>{const text=bestOverlapText(best),td=cell('td',text,{class:'num',...(best?{'data-best-overlap':String(best.eta),title:`Best overlap, with ${other} ${unitName(best.unit)}. Modes are matched at an overlap of ${MATCH_THRESHOLD} or more, at least ${MATCH_MARGIN} above the next best.`}:{})});
  const at=text.indexOf(' (');if(at>0){td.textContent='';td.classList.add('best-split');const v=document.createElement('span'),sep=document.createElement('span'),why=document.createElement('span');v.className='best-value';v.textContent=text.slice(0,at);sep.className='pol-sep';sep.textContent=' ';why.className='best-why';why.textContent=text.slice(at+1);td.append(v,sep,why);}
  return td;};
 // n_g of a unit: the mode's, or the mean of a pair; "—" with its help when the run has none
 const ngCell=(run,unit,side)=>{const v=unitGroupIndex(run,unit);return cell('td',v.text,{class:'num',title:v.title,['data-group-index-'+side]:v.value===null?'':String(v.value)});};
 // "1", or "1–2" for a pair or group; "—" for no unit
 const short=unit=>unit?(unit.length===1?String(unit[0]+1):`${unit[0]+1}–${unit.at(-1)+1}`):'—';
 const body=document.createElement('tbody');
 for(const r of compareMatchRows(match)){
  const tr=document.createElement('tr');
  if(r.kind==='match'){
   const mean=index(a,r.unitA);tr.dataset.match=`${r.unitA.join('-')}:${r.unitB.join('-')}`;
   tr.append(cell('th',`${short(r.unitA)} ↔ ${short(r.unitB)}`,{scope:'row',title:r.text,'aria-label':`A ${unitName(r.unitA)} ↔ B ${unitName(r.unitB)}`}),polarizationCell(unitPolarization(a,r.unitA)),polarizationCell(unitPolarization(b,r.unitB)),cell('td',formatOverlap(r.pair.eta),{'data-overlap':String(r.pair.eta),class:'num'}),
    cell('td',indexText(a,r.unitA),{class:'num'}),cell('td',indexText(b,r.unitB),{class:'num'}),cell('td',formatDelta(r.pair.delta),{class:'num','data-delta':''}),cell('td',formatPercent(mean===0?null:r.pair.delta/mean*100),{class:'num','data-delta-percent':''}),areaCell(a,r.unitA,'a'),areaCell(b,r.unitB,'b'),lossCell(a,r.unitA,'a'),lossCell(b,r.unitB,'b'),ngCell(a,r.unitA,'a'),ngCell(b,r.unitB,'b'));
  }else{
   tr.dataset.noMatch=`${r.kind.toUpperCase()}:${(r.unitA||r.unitB).join('-')}`;
   tr.append(cell('th',`${short(r.unitA)} ↔ ${short(r.unitB)}`,{scope:'row',title:r.text,'aria-label':r.text}),polarizationCell(r.unitA?unitPolarization(a,r.unitA):'—'),polarizationCell(r.unitB?unitPolarization(b,r.unitB):'—'),bestCell(r.best,r.kind==='a'?'B':'A'),cell('td',indexText(a,r.unitA)),cell('td',indexText(b,r.unitB)),cell('td','—'),cell('td','—'),areaCell(a,r.unitA,'a'),areaCell(b,r.unitB,'b'),lossCell(a,r.unitA,'a'),lossCell(b,r.unitB,'b'),ngCell(a,r.unitA,'a'),ngCell(b,r.unitB,'b'));
  }
  body.append(tr);
 }
 table.append(body);scroll.append(table);frame.append(scroll);
 // the scroll cue: the line and the right-edge shadow while columns are hidden on the right
 const cue=()=>{const over=scroll.scrollWidth>scroll.clientWidth+1;more.hidden=!over;frame.classList.toggle('more-right',over&&scroll.scrollLeft+scroll.clientWidth<scroll.scrollWidth-1);};
 scroll.addEventListener('scroll',cue,{passive:true});new ResizeObserver(cue).observe(scroll);
 // an open run without physical bounds is not matched (workspace-match.mjs MATCH_OPEN_TEXT): every mode is listed unmatched
 const note=cell('p',match.disabled?match.disabled+'. Every mode of A and of B is listed, not matched.':MATCH_NOTE,{class:'table-note',id:'compare-match-note'});
 box.append(runs,more,frame,note);
 // round 17 (U1): a closed run whose modes lie mostly in a shape touching the window edge says so,
 // which also says why such a run matches none of an open run's modes
 {const lines=[['A',a],['B',b]].flatMap(([side,run])=>edgeNotes(run).map(n=>`${side} · ${runTitle(runNumber(run),run.label)}: ${n.text}`));
  if(lines.length){const p=cell('p','',{class:'table-note',id:'compare-edge-note'});lines.forEach((t,i)=>{if(i)p.append(document.createElement('br'));p.append(t);});box.append(p);}}
 // the two loss columns count different things: say so
 if(isOpenRun(a)!==isOpenRun(b))box.append(cell('p',isOpenRun(b)?COMPARE_LOSS_NOTE:COMPARE_LOSS_NOTE_BA,{class:'table-note',id:'compare-loss-note'}));
 return box;
}
// The matched modes shown in the Compare plots (in memory only: session files keep the Results mode)
let compareChoice=null;
// Compare just opened (not redrawn while open): its pane then scrolls so the plots' middle, where
// the window is centred on the core, is in view, as Results shows its plot; a redraw keeps the scroll
var compareOpen=false;
function frameComparePlots(grid){
 const pane=$('canvas'),box=pane.getBoundingClientRect(),plot=grid.querySelector('canvas')?.getBoundingClientRect();if(!plot)return;
 // the middle of the plot 24 px above the pane's bottom edge, never scrolling the plots' headings out of view
 const need=plot.top+plot.height/2-(box.bottom-24),room=grid.getBoundingClientRect().top-box.top;
 if(need>0)pane.scrollTop+=Math.min(need,Math.max(0,room));
}
function renderComparison(){
 // set once the plots are drawn: a Compare shown without plots (one run, a run without fields) frames them when they come
 const opening=!compareOpen;
 const host=$('canvas');host.innerHTML='<h2>Compare two runs</h2>';
 if(runs.length<2){host.insertAdjacentHTML('beforeend','<p>Compute two designs to compare their fields and inputs. Existing results stay attached to their original inputs.</p>');return;}
 // a pick whose run is gone: both back to the default pair (workspace-compare.mjs defaultComparison)
 if(!compareIds.every(id=>runs.some(r=>r.job===id))){compareIds=defaultComparison(runs);comparePicked=false;}
 const bar=document.createElement('div');bar.className='toolbar compare-selection';
 for(let side=0;side<2;side++){const label=document.createElement('label');label.textContent=side?'B':'A';const select=document.createElement('select');select.id=side?'compare-b':'compare-a';
  // round 17 (U9): the accessible name says what is picked; the full run label is the title, so an
  // ellipsis at a narrow width hides no part of it (the label starts with the run's number and name)
  select.setAttribute('aria-label',side?'Run B':'Run A');for(const r of runs){const o=document.createElement('option');o.value=r.job;o.textContent=runLabel(r);o.title=o.textContent;o.selected=r.job===compareIds[side];select.append(o);}select.title=select.selectedOptions[0]?.textContent||'';select.onchange=()=>{compareIds[side]=select.value;comparePicked=true;compareChoice=null;render();};label.append(select);bar.append(label);}host.append(bar);
 // a kept pair (round 16): the newest run, when newer than both, is offered beside it
 // round 24 (B4): a pair kept because both runs are named, not picked by hand, is offered the two
 // newest runs in one action; a pair picked by hand keeps the round-16 swap and is never replaced
 const newer=newerThanPair(runs,compareIds);if(newer){const line=document.createElement('p');line.id='compare-newer';line.className='compare-newer';const n=runNumber(newer);line.append(`Run ${n} is newer than this pair · `);const swap=document.createElement('button');swap.type='button';swap.id='compare-newer-button';
  const offer=newestPairOffer(runs,compareIds,comparePicked);
  if(offer){const [na,nb]=offer.map(job=>runNumber(runs.find(r=>r.job===job)));swap.textContent=`Compare the two newest: Run ${na} and Run ${nb}`;swap.onclick=()=>{compareIds=[...offer];comparePicked=false;compareChoice=null;render();notice(`Compare shows the two newest runs: Run ${na} (A) and Run ${nb} (B).`);};}
  else{swap.textContent=`Compare Run ${n} with B`;swap.onclick=()=>{compareIds=[compareIds[1],newer.job];comparePicked=true;compareChoice=null;render();notice(`Compare shows Run ${n} with the run that was B, now A.`);};}
  line.append(swap);host.append(line);}
 const a=runs.find(r=>r.job===compareIds[0]),b=runs.find(r=>r.job===compareIds[1]);
 // a run of a file without fields: its modes cannot be matched by overlap or drawn
 const withoutFields=[a,b].filter(r=>!r.field);
 if(withoutFields.length){if(!bar.isConnected)host.append(bar);for(const r of withoutFields)host.append(Object.assign(document.createElement('p'),{className:'compare-no-fields',textContent:`Run ${runNumber(r)} has no saved fields, so its modes cannot be matched by overlap.`}));return;}
 const match=opticalMatch(a,b),choices=match.error?[]:fieldChoices(match,{a,b});
 const chosen=choices.find(c=>compareChoice&&c.a===compareChoice.a&&c.b===compareChoice.b)||choices.find(c=>compareChoice&&c.a===compareChoice.a)||choices[0]||null;
 const shown=chosen?[chosen.a,chosen.b]:[0,0];
 const opts=document.createElement('div');opts.className='toolbar compare-options';opts.innerHTML=`<label class="compare-mode-label">Matched modes <select id="compare-mode" ${choices.length?'':'disabled'}>${choices.length?choices.map((c,i)=>`<option value="${i}" ${c===chosen?'selected':''}>${escapeHtml(c.label)}</option>`).join(''):'<option>No matched modes</option>'}</select></label><label>Quantity <select id="compare-component">${['magnitude','Ex','Ey','Ez'].map(c=>`<option value="${c}" ${fieldView.component===c?'selected':''}>${c==='magnitude'?'|E|':'|'+c+'|'}</option>`).join('')}</select></label><label>View <select id="compare-window">${['Core region','Full window'].map(v=>`<option ${fieldView.window===v?'selected':''}>${v}</option>`).join('')}</select></label>`;host.append(opts);
 const pairOf=chosen&&match.pairs.find(p=>p.accepted&&p.unitA.includes(chosen.a));
 const shownText=chosen?`Shown: A mode ${chosen.a+1} ↔ B mode ${chosen.b+1}, overlap ${formatOverlap(pairOf.eta)}, Δn_eff (B − A) ${formatDelta(pairOf.delta)}${pairOf.unitA.length>1?' (difference of the pair means)':''}.`:match.disabled?`${match.disabled}; the plots show mode 1 of each run, not matched.`:match.error?`Modes not matched (${match.error}); the plots show mode 1 of each run.`:'No mode of A matches a mode of B; the plots show mode 1 of each run, not matched.';
 const description=document.createElement('p');description.id='compare-description';const sameShapes=JSON.stringify(a.input.model.shapes)===JSON.stringify(b.input.model.shapes);description.textContent=`Geometry: ${designSummary(a.input.model)} → ${designSummary(b.input.model)}${sameShapes?' (same shapes)':' (shapes differ)'}. Wavelength: ${a.input.model.wavelength} → ${b.input.model.wavelength} nm. Core mesh: ${a.input.model.coreMesh} → ${b.input.model.coreMesh} nm. ${shownText} ${a.job===b.job?'Same run on both sides. ':''}`;
 const grid=document.createElement('div');grid.className='compare-grid';[a,b].forEach((run,i)=>{const article=document.createElement('article');const h=document.createElement('h3');h.textContent=fieldHeading(i?'B':'A',run,runNumber(run));const which=document.createElement('p');which.className='compare-field-mode';which.id=i?'compare-shown-b':'compare-shown-a';which.textContent=`Mode ${shown[i]+1} · ${unitPolarization(run,[shown[i]])}${chosen?'':' · not matched'}`;const canvas=document.createElement('canvas');canvas.id=i?'compare-field-b':'compare-field-a';canvas.style.cssText='width:100%;height:var(--optical-plot-height,340px);display:block';canvas.setAttribute('role','img');article.append(h,which,canvas);probeOutput(article,i?'compare-probe-b':'compare-probe-a');grid.append(article);});
 // round 22 (V3): no matched mode, and a run's mode 1 is an edge mode: the empty-match line says why,
 // with a link that opens that run in Results
 if(!chosen&&!match.disabled&&!match.error)[['A',a],['B',b]].forEach(([side,run],i)=>{if(i&&a.job===b.job)return;const shape=firstModeEdgeShape(run);if(!shape)return;
  const link=document.createElement('a');link.href='#';link.id='compare-edge-open-'+side.toLowerCase();link.dataset.showRun=String(runNumber(run));link.textContent=`Open Run ${runNumber(run)} in Results`;
  link.onclick=e=>{e.preventDefault();if(!runs.includes(run))return;solverRun=run;ui.page='Results';render();notice(`${runNumberTitle(run)} shown under Results; the inputs are unchanged.`);};
  const reason=document.createElement('span');reason.className='compare-edge-reason';reason.id='compare-edge-reason-'+side.toLowerCase();reason.textContent=noMatchEdgeText(side,runNumberTitle(run),shape);
  description.append(description.textContent.endsWith(' ')?'':' ',reason,' ',link,'.');});
 // the plots first, right under the pickers (as Results shows its plot), then what they show
 host.append(grid,description);
 const legend=document.createElement('div');legend.innerHTML='<div style="display:flex;gap:8px;align-items:center"><span>0</span><div style="flex:1;height:12px;background:linear-gradient(to right,#12263b,#176f8b,#45bb9f,#f9eb82)"></div><span>1</span></div><p>Shared coordinates and 0–1 color scale. Each mode is normalized to its own max|E|; this compares shapes, not absolute amplitudes. Components share their mode vector denominator. No interpolation or field subtraction across meshes.</p>';host.append(legend,compareTable(a,b,match));
 const redraw=()=>{if(!grid.isConnected)return;drawField($('compare-field-a'),a,null,$('compare-probe-a'),redraw,shown[0]);drawField($('compare-field-b'),b,null,$('compare-probe-b'),redraw,shown[1]);};addProbeControls(host,redraw);
 $('compare-mode').onchange=()=>{const c=choices[+$('compare-mode').value];if(c){compareChoice={a:c.a,b:c.b};render();}};
 for(const [id,key] of [['compare-component','component'],['compare-window','window']])$(id).onchange=()=>{fieldView[key]=$(id).value;render();};
 fieldResize=new ResizeObserver(redraw);fieldResize.observe(grid);redraw();renderLineProfile(host,[a,b],redraw,()=>shown);
 compareOpen=true;if(opening)frameComparePlots(grid);
}
let pendingRunImport=null;
const runImportDialog=document.createElement('dialog');runImportDialog.id='run-import-confirm';runImportDialog.setAttribute('aria-labelledby','run-import-title');runImportDialog.setAttribute('aria-describedby','run-import-summary run-import-description');runImportDialog.innerHTML='<h2 id="run-import-title">Add saved runs to this notebook?</h2><p id="run-import-summary"></p><p id="run-import-description">Current model inputs stay unchanged. Matching existing runs retain their names, pins and provenance. Imported fields are not recomputed.</p><button id="cancel-run-import">Keep notebook</button> <button id="confirm-run-import">Import runs</button>';document.body.append(runImportDialog);
const runListStamp=()=>JSON.stringify(runs.map(run=>[run.job,run.completedAt,run.label,run.pinned]));
$('run-import-file').onchange=async event=>{
 const file=event.target.files[0];event.target.value='';if(!file)return;
 try{const loaded=await workspaceLoads.read(async()=>{if(solverBusy||pendingJob)throw new Error('Finish or detach the pending job before importing runs.');if(file.size>MAX_SESSION_BYTES)throw new Error('Session exceeds 16 MiB.');return parseSession(await file.text());});if(!loaded)return;const session=loaded.value;if(solverBusy||pendingJob)throw new Error('A job started while reading the file.');if(session.application==='multiphysics')throw new Error('Add runs from file adds optical runs; open a multiphysics session with Open session.');const merged=mergeRuns(runs,session.runs);workspaceLoads.invalidate();pendingRunImport={session,merged,stamp:runListStamp(),fileName:file.name};
  $('run-import-summary').textContent=`${file.name}: ${merged.added.length} new, ${merged.reused.length} matching, ${merged.evicted.length} older unpinned runs replaced. ${merged.runs.length} runs will remain. Save a session first if you need all current results.`;runImportDialog.showModal();
 }catch(error){pendingRunImport=null;notice('Run import failed: '+error.message+' Current notebook kept.');}
};
function cancelRunImport(){workspaceLoads.invalidate();pendingRunImport=null;runImportDialog.close();restoreDialogFocus($('import-runs'));notice('Run import cancelled. Current notebook kept.');}
$('cancel-run-import').onclick=cancelRunImport;runImportDialog.oncancel=event=>{event.preventDefault();cancelRunImport();};
$('confirm-run-import').onclick=()=>{
 const pending=pendingRunImport;pendingRunImport=null;workspaceLoads.invalidate();runImportDialog.close();if(!pending)return;
 if(solverBusy||pendingJob||runListStamp()!==pending.stamp){notice('Notebook changed while reviewing the import. Open the file again to review current changes.');return;}
 const previous=solverRun;const next=pending.merged.runs;const selected=next.find(run=>run.job===pending.session.selected)||next.findLast(run=>pending.session.runs.some(imported=>imported.job===run.job));
 // the added runs are numbered after the tab's largest number, in file order; a job already in the
 // tab keeps the tab's number; the message names the numbers that changed
 const dropped=runs.filter(r=>!next.includes(r)),added=next.filter(r=>pending.merged.added.includes(r.job));runNumbersUsed=numberRuns(next,Math.max(runNumbersUsed,...runs.map(r=>r.number||0)));runs=next;
 const renumbered=importNumbersText(added.map(r=>({from:pending.session.runs.find(x=>x.job===r.job).number,to:r.number})),pending.fileName);solverRun=selected||runs.at(-1);const other=runs.find(run=>run.job===previous?.job&&run.job!==solverRun.job)||runs.findLast(run=>run.job!==solverRun.job)||solverRun;
 compareIds=[other.job,solverRun.job];ui.page=runs.length>1?'Compare':'Results';render();notice('Saved runs imported. Current model inputs and input undo history kept; imported fields were not recomputed.'+(renumbered?' '+renumbered:'')+dropped.map(r=>' '+droppedRunText(r)).join(''));
};

// The server's check of a document (/api/multiphysics/validate), as the reader reads it.
const validateModel=doc=>studioRequest('POST','/api/multiphysics/validate',{doc});
// Opening a multiphysics session (a file or browser recovery), checked already: the leave
// question when runs would be lost, else the open question when a model would be replaced.
function requestMultiphysicsSession(session,{label,source,opener=document.activeElement,recoveryRecord=null,keepAsLatest=false,savedFile=null,openedFile=null,openedCurrent=null,recoveryIndex=null,then=null,projectMatched=false,recordProject=null,recordSavedAt=null}){
 if(multiView.busy()){notice('Wait for the multiphysics run to finish, or stop it under Study.');return;}
 // a file replaces the project (P3); a browser restore replaces the multiphysics model only
 const model=source==='file'?false:'multiphysics',asked=!!leaveText(label,model);
 const go=()=>{
  const finish=()=>{if(source==='browser'){notebookStore.adopt(recoveryRecord,{kept:keepAsLatest});restoredFrom(recoveryIndex);}fileScope++;multiView.openSession(session,{label,source,savedFile,openedFile,openedCurrent}).then(()=>{if(source==='file'){multiphysicsProject();rememberOpened(label);}else{rememberOpened(recoveredFileName(savedFile,openedFile,openedCurrent),'recovered');restoreProjectFile(savedFile,openedFile,{matched:projectMatched===true});restoreProjectName(recordProject,{savedFile,openedFile,openedCurrent,savedAt:recordSavedAt});refreshPersistence();}then?.();}).catch(e=>notice('Session open failed: '+e.message));};
  // nothing to lose: no multiphysics model open, or one with no runs that was not edited
  if(asked||!multiView.inProject()||(!multiView.projectRuns()&&!multiView.edited())){finish();return;}
  const text=multiphysicsLoadText(session,{runs:multiView.projectRuns(),unsaved:multiView.projectUnsavedRuns()>0,model:'the current model'},source);
  $('load-confirm').querySelector('h2').textContent=text.title;$('load-confirm').querySelector('p').textContent=text.description;$('confirm-load').textContent=text.button;
  const summary=$('load-summary');summary.replaceChildren();
  for(const [name,value] of [['Source',label],['Runs that come back',text.runs],['Model',`${multiView.modelName()} → ${session.document.name||'Untitled model'}`],['Completed results',`${multiView.projectRuns()} now → ${session.runs.length} from the session`],['Input Undo','Starts at the opened session']]){const term=document.createElement('dt'),detail=document.createElement('dd');term.textContent=name;detail.textContent=value;summary.append(term,detail);}
  pendingLoad={multiphysics:finish,opener,context:loadContext()};
  if(!$('load-confirm').open)$('load-confirm').showModal();
 };
 guardLeave(label,model,go);
}
// A multiphysics session over 16 MiB asks first (§2): the maps of the selected and pinned runs
// only, or nothing written. Studio never drops maps without asking.
const overflowDialog=document.createElement('dialog');overflowDialog.id='session-overflow';overflowDialog.setAttribute('aria-labelledby','session-overflow-title');overflowDialog.setAttribute('aria-describedby','session-overflow-description');
overflowDialog.innerHTML='<h2 id="session-overflow-title">Session over 16 MiB</h2><p id="session-overflow-description"></p><div class="leave-actions"><button id="overflow-cancel">Cancel</button> <button id="overflow-keep">Keep maps for selected and pinned runs</button></div>';
document.body.append(overflowDialog);
// an optical session over 16 MiB asks the same: the fields of the selected and pinned runs only
const setOverflowKeepText=multi=>{$('overflow-keep').textContent=multi?'Keep maps for selected and pinned runs':'Keep fields for selected and pinned runs';};
// overflowProject: the question asked for a model of a project save ({saveAs, keep}), else null
// (Export › Model with runs)
let overflowProject=null;
const overflowNothing=()=>notice(overflowProject?'Project not saved: nothing was written.':'Session not saved: nothing was written.');
$('overflow-cancel').onclick=()=>{overflowDialog.close();overflowNothing();};
$('overflow-keep').onclick=()=>{overflowDialog.close();const asked=overflowProject;overflowProject=null;if(asked)saveProjectFile(asked);else saveSessionFile({saveAs:overflowSaveAs,keepSelected:true});};
overflowDialog.oncancel=event=>{event.preventDefault();overflowDialog.close();overflowNothing();};
async function saveMultiphysicsSession({saveAs=false,keepSelected=false}={}){
 const out=await multiView.saveSession({keepSelected,saveAs});
 if(out.question){overflowProject=null;overflowSaveAs=saveAs;setOverflowKeepText(true);$('session-overflow-description').textContent=out.question;if(!overflowDialog.open)overflowDialog.showModal();}
}
// File › Save (and the ribbon's Save) and File › Save As: the session file of the open model.
// Save writes the file Save As chose; without one it asks, as Save As does. Resolves when done.
function saveSessionFile({saveAs=false,keepSelected=false}={}){
 if(savingFile){notice('A save is already in progress.');return Promise.resolve();}
 if(multiView.active())return saveMultiphysicsSession({saveAs,keepSelected}).catch(e=>notice('Session not saved: '+e.message));
 try{rejectInvalidInput();return saveOpticalSession({saveAs,keepSelected}).catch(e=>notice('Session not saved: '+e.message));}catch(e){notice('Session not saved: '+e.message);return Promise.resolve();}
}
// ---- File › Save and Save As: the project file (P3, workspace-project-file.mjs) ----
// Every model of the tab in one file. Each model's session is written by its own writer (the 16
// MiB question is asked per model, naming it); the whole file is at most 64 MiB. Save writes the
// picker's file again, or downloads under the project file's name; Save As always asks. The text is
// made once the file is named (an untitled project takes the file's stem as its name), inside the
// click or key press, so the picker keeps it. keep: the ids of the models whose 16 MiB question was
// answered with Keep.
function saveProjectFile({saveAs=false,keep=[]}={}){
 if(savingFile){notice('A save is already in progress.');return Promise.resolve();}
 try{return saveProject({saveAs,keep:new Set(keep)}).catch(e=>notice('Project not saved: '+e.message));}catch(e){notice('Project not saved: '+e.message);return Promise.resolve();}
}
function saveProject({saveAs,keep}){
 const models=projectModels();if(!models.length){notice('Nothing to save yet: choose a model first.');return Promise.resolve();}
 const parts=[];let noRun='';
 for(const m of models){
  if(m.kind==='workspace'){
   rejectInvalidInput();
   const inputs=workspaceInputs(),out=writeOpticalSession(inputs,runs,solverRun?.job||null,compareIds,currentView(),{keepSelected:keep.has(m.id)});
   if(!out.ok){if(out.refusal)throw new Error(`${m.title}: ${out.refusal}`);askProjectOverflow(m,opticalOverflowQuestion(out.bytes),false,{saveAs,keep});return Promise.resolve();}
   const at={notebook:notebookStamp(),runs:runsStamp(),stamp:saveStamp(),inputs:JSON.stringify(inputs),shown:!mpFlags};
   // the current inputs without a run of their own are said, so the file is not read as holding them (round 14)
   noRun=at.shown&&runs.length&&!runs.some(r=>r.signature===signature())?` Current inputs (${geometryWords(inputs.model)}) have no run yet.`:'';
   // the inputs saved are recorded now, so an edit made while the dialog is open stays on top of them
   if(at.shown)edits.record(inputs);
   // recovery: the text browser recovery holds for this model now, so its record names the file (round 16)
   let recoveryNow=null;if(runs.length){try{recoveryNow=captureSession(inputs,runs,solverRun?.job||null,compareIds,currentView())();}catch{}}
   parts.push({model:m,text:out.text,recovery:recoveryNow,words:modelParts(m.card==='optical'||runs.length?{runs:runs.length,comparison:runs.length>1}:{inputsOnly:true}),notKept:out.notKept,
    mark:(name,savedAt,written,projectName)=>{newModelInputs=null;if(at.shown&&!mpFlags&&JSON.stringify(inputsFile())===at.inputs)edits.markSaved();savedNotebookState=at.notebook;savedRunsState=at.runs;lastSavedFile={name,savedAt,stamp:at.stamp,recovered:false,written,projectName};loadedSession=null;}});
  }else{
   const out=multiView.projectEntry({keepSelected:keep.has(m.id)});
   if(!out.ok){if(out.refusal)throw new Error(`${m.title}: ${out.refusal}`);askProjectOverflow(m,out.question,true,{saveAs,keep});return Promise.resolve();}
   parts.push({model:m,text:out.text,recovery:multiView.recoveryTextNow(),words:modelParts({runs:out.runs,baseline:out.baselines>0}),notKept:out.notKept,mark:out.mark});
  }
 }
 const entries=parts.map(p=>projectEntry({...p.model,text:p.text})),content=projectContent(),active=(multiView.active()?models.find(m=>m.kind==='multiphysics'):models[0]).id;
 const fileText=name=>{const out=writeProject({name,savedAt:new Date().toISOString(),studio:connection.version||'unknown',active,entries});if(!out.ok)throw new Error(out.refusal);return out.text;};
 // the size before anything is asked (the name changes it by a few bytes at most)
 const first=writeProject({name:project.name||'Untitled project',savedAt:new Date().toISOString(),studio:connection.version||'unknown',active,entries});
 if(!first.ok)throw new Error(first.refusal);
 const nameFor=fileName=>savedProjectName({name:project.name,from:project.nameFrom},fileName);
 return deliverProject(fileName=>fileText(nameFor(fileName)),{saveAs}).then(result=>{
  if(!result.written){notice(result.message);return;}
  const savedAt=new Date().toISOString(),name=nameFor(result.name);
  project.name=name;if(project.nameFrom!=='user')project.nameFrom='file';if(project.file)project.file.savedAt=savedAt;project.stamp=projectStamp(name,content);
  for(const p of parts)p.mark(result.name,savedAt,result.via==='picker',name);
  refreshPersistence();
  // every stored record of a model just written names this project file, shown or not (round 16)
  relinkRecovery(parts.flatMap(p=>[p.text,p.recovery].filter(t=>typeof t==='string')),{name:result.name,savedAt,current:true,projectName:name});
  notice(projectSavedNotice({name,file:result.name,via:result.via,known:result.known===true,again:result.again===true,after:noRun+result.after,
   models:parts.map(p=>({title:p.model.title,parts:p.words})),notKept:parts.filter(p=>p.notKept.length).map(p=>({title:p.model.title,kind:p.model.kind,runs:p.notKept}))}));
 });
}
// A model of the project over 16 MiB: the question names it; Keep saves the project again with the
// fields (or maps) of that model's selected and pinned runs only.
function askProjectOverflow(model,question,multi,{saveAs,keep}){
 overflowProject={saveAs,keep:[...keep,model.id]};setOverflowKeepText(multi);
 $('session-overflow-description').textContent=`${model.title}: ${question}`;if(!overflowDialog.open)overflowDialog.showModal();
}
// The project file's delivery: the picker's file (Save with a kept file, or where the picker works),
// else the name dialog and a download; the name suggested is the project file's, else the project
// name's (untitled-project.json), never a model file's name. Resolves {written, name, via, ...}.
function deliverProject(makeText,{saveAs}){
 savingFile=true;nameDialogContents=projectHoldsText();const scope=project.scope,target=project.file&&project.file.scope===scope?project.file:null;
 const prefill=target?target.name:projectFileName(project.name);
 const models=modelList(),keep=(name,how,handle=null)=>{if(project.scope===scope){project.file=rememberFile({name,how,handle,scope});if(project.file)project.file.models=models;}};
 return saveToFile(makeText,{suggestedName:prefill,target,saveAs,description:PROJECT_PICKER_DESCRIPTION}).then(async result=>{
  if(result.status==='saved'){keep(result.name,'picker',result.handle);return {written:true,name:result.name,via:'picker',after:''};}
  // round 17 (U8): on the download path, Save asks first (the Save As name dialog, prefilled with the
  // file's name) when the project's models changed since that file was written or opened
  if(result.status==='known'&&modelsChanged(target)){
   $('save-name-input').defaultValue=result.name;const name=await askFileName(result.name,{saveAs:true,why:modelsChangedText(target,result.name)});
   if(!name)return {written:false,message:notWrittenNotice({status:'cancelled'},{saveAs:true})};
   downloadFile(new Blob([makeText(name)],{type:'application/json'}),name);keep(name,'download');
   return {written:true,name,via:'download',again:name===target.name&&target.how==='download',known:name===target.name,after:name===target.name?' '+downloadAgainNote(name):''};
  }
  if(result.status==='known'){downloadFile(new Blob([makeText(result.name)],{type:'application/json'}),result.name);keep(result.name,'download');
   return {written:true,name:result.name,via:'download',again:target.how==='download',known:true,after:' '+downloadAgainNote(result.name)};}
  if(result.status!=='unavailable')return {written:false,message:notWrittenNotice(result,{saveAs,kind:'Project'})};
  $('save-name-input').defaultValue=prefill;
  const name=await askFileName(prefill,{saveAs,unavailable:result.error});
  if(!name)return {written:false,message:notWrittenNotice({status:'cancelled'},{saveAs})};
  downloadFile(new Blob([makeText(name)],{type:'application/json'}),name);keep(name,'download');
  return {written:true,name,via:'download',after:''};
 }).finally(()=>{savingFile=false;nameDialogContents=null;});
}
$('save-session').onclick=()=>{saveProjectFile({saveAs:false});};
$('menu-save').onclick=()=>{saveProjectFile({saveAs:false});};
$('menu-save-as').onclick=()=>{saveProjectFile({saveAs:true});};
// Export › Model with runs (session file): the shown model alone, as Save As wrote it before P3
$('menu-export-session').onclick=()=>{saveSessionFile({saveAs:true});};
$('menu-open').onclick=()=>$('open-session').click();
setupMenus([$('file-menu-button'),$('edit-menu-button')]);
// the shortcuts as this platform writes them (⌘ on Apple systems)
if(/Mac|iPhone|iPad/.test(navigator.platform||navigator.userAgent||''))for(const k of document.querySelectorAll('.menu-keys'))k.textContent=k.dataset.keys.replace('Shift+Ctrl+','⇧⌘').replace('Ctrl+','⌘');
// Save session: the file as it is, or, over 16 MiB, the dialog (fields of the selected and pinned
// runs only); nothing is written on Cancel or when even that is over the limit.
async function saveOpticalSession({keepSelected=false,saveAs=false}={}){
 const inputs=inputsFile(),out=writeOpticalSession(inputs,runs,solverRun?.job||null,compareIds,currentView(),{keepSelected});
 if(!out.ok){if(out.refusal)throw new Error(out.refusal);overflowProject=null;overflowSaveAs=saveAs;setOverflowKeepText(false);$('session-overflow-description').textContent=opticalOverflowQuestion(out.bytes);if(!overflowDialog.open)overflowDialog.showModal();return;}
 const notebook=notebookStamp(),runsNow=runsStamp(),stampNow=saveStamp(),count=runs.length,inputsText=JSON.stringify(inputs);
 // the current inputs without a run of their own are said, so the file is not read as holding them (round 14)
 const noRun=count&&!runs.some(r=>r.signature===signature())?` Current inputs (${geometryWords(inputs.model)}) have no run yet.`:'';
 // the inputs saved are recorded now, so an edit made while the dialog is open stays on top of them
 edits.record(inputs);
 const result=await deliverSession(out.text,sessionFileName(applicationSlug()),{saveAs});if(!result.written){notice(result.message);return;}
 const name=result.name;newModelInputs=null;if(JSON.stringify(inputsFile())===inputsText)edits.markSaved();savedNotebookState=notebook;savedRunsState=runsNow;lastSavedFile={name,savedAt:new Date().toISOString(),stamp:stampNow,recovered:false,written:result.via==='picker'};loadedSession=null;refreshPersistence();notice(`${savedWhere(result)}: current inputs, ${count===1?'1 run':count+' runs'} and the comparison.`+(out.notKept.length?` Fields not kept for ${out.notKept.map(n=>'Run '+n).join(', ')}.`:'')+noRun+result.after);
}
// ---- File › Open of a project file (P3) ----
// Every check runs before the tab changes: the size, the envelope, each model's check value and
// parseSession, and the server's check of each multiphysics model (as Open session does). One
// failure refuses the whole file and leaves the workspace, its runs and Undo as they were. Then the
// leave question, when some model's runs are in no file; nothing is run.
async function openProjectFile(file){
 try{
  if(solverBusy||pendingJob)throw new Error('Wait for the current calculation, or detach its job, before opening a project.');
  if(multiView.busy())throw new Error('Wait for the multiphysics run to finish, or stop it under Study.');
  if(openingModel)throw new Error('Wait until the model file has been opened.');
  if(file.size>MAX_PROJECT_BYTES)throw new Error(`This project file is ${sizeText(file.size)}, over the 64 MiB limit.`);
  const loaded=await workspaceLoads.read(async()=>{
   const read=readProject(await file.text()),multi=read.models.filter(m=>m.kind==='multiphysics');
   if(multi.length>1)throw new Error(`This project holds ${multi.length} multiphysics models; this Studio holds one per tab.`);
   for(const m of multi){try{await checkSessionModels(m.session,validateModel);}catch(e){throw new Error(`${m.title}: ${e.message}`);}}
   return read;});
  if(!loaded)return;
  if(solverBusy||pendingJob||multiView.busy())throw new Error('A calculation started while reading the file.');
  const read=loaded.value;
  guardLeave(file.name,false,()=>{applyOpenedProject(read,file.name).catch(e=>notice('Project open failed: '+e.message));});
 }catch(e){notice('Project not opened: '+e.message+' The current project is unchanged.');}
}
async function applyOpenedProject(read,fileName){
 const ws=read.models.find(m=>m.kind==='workspace'),mp=read.models.find(m=>m.kind==='multiphysics');
 if(solverBusy||multiView.busy()){notice('A calculation started; the project was not opened.');return;}
 openingModel=true;
 try{
  if(!leaveMultiphysics())return;
  multiView.discard();
  resetProject({name:read.name,nameFrom:nameSource(read.name,fileName),ids:Object.fromEntries(read.models.map(m=>[m.kind,m.id]))});
  if(ws)completeLoad({input:ws.session.input,saved:true,session:ws.session,source:'file',label:fileName,page:null,opener:$('open-session'),context:loadContext()});
  else clearWorkspace();
  if(mp){
   const page=ui.page;
   await multiView.openSession(mp.session,{label:fileName,source:'file',card:mp.card});
   if(read.active!==mp.id){leaveMultiphysics();ui.page=page;render();}
  }
  project.file=rememberFile({name:fileName,how:'opened',scope:project.scope});if(project.file)project.file.models=modelList();project.stamp=projectStamp();
  refreshPersistence();
  const words=read.models.map(m=>({title:m.title,parts:m.kind==='workspace'?modelParts(m.card==='optical'||m.session.runs.length?{runs:m.session.runs.length,comparison:m.session.runs.length>1}:{inputsOnly:true}):modelParts({runs:m.session.runs.length,baseline:Object.keys(m.session.baselines).length>0})}));
  notice(`Opened project ${read.name} (${fileName}): ${modelsText(words)}. Results were read from the file, not recomputed; nothing was run.`);
 }finally{openingModel=false;}
}
$('open-session').onclick=()=>{if(solverBusy){notice('Wait for the current calculation before opening a session.');return;}try{rejectInvalidInput();$('session-file').click();}catch(e){notice(e.message);}};
$('session-file').onchange=async event=>{const file=event.target.files[0];event.target.value='';if(!file)return;try{
 // a project file (P3): its format is the first key Studio writes, so its first bytes say so
 // before a file of up to 64 MiB is read; a hand-edited one is found by its parsed format below
 if((await file.slice(0,4096).text()).includes(JSON.stringify(PROJECT_FORMAT))){openProjectFile(file);return;}
 // an optical, heat or Joule heating model file (inputs only) opens as Open did for it before
 // (read up to 1 MiB, so a model file over its 64 KiB limit gets the model reader's refusal)
 if(file.size<=(1<<20)){let tree=null;try{tree=JSON.parse((await file.text()).replace(/^\uFEFF/,''));}catch{}if(tree?.format==='openphysics-studio-workspace'){openModelFile(file);return;}if(isProjectDocument(tree)){openProjectFile(file);return;}}
 if(multiView.busy())throw new Error('Wait for the multiphysics run to finish, or stop it under Study.');
 const loaded=await workspaceLoads.read(async()=>{if(solverBusy)throw new Error('Calculation is still running.');if(file.size>MAX_SESSION_BYTES)throw new Error('Session exceeds 16 MiB.');
  const text=await file.text();
  // a bare model file opens as the model with no runs (§5), read by the server's reader as written
  if(file.size<=(1<<20)){let tree=null;try{tree=JSON.parse(text.replace(/^\uFEFF/,''));}catch{}if(isModelDocument(tree))return {model:text.replace(/^\uFEFF/,'')};}
  const session=parseSession(text);
  // a multiphysics session: the server checks every model before anything in the tab is replaced
  if(session.application==='multiphysics')await checkSessionModels(session,validateModel);
  return {session};});
 if(!loaded)return;if(solverBusy)throw new Error('Calculation started while reading the file.');
 if(loaded.value.model!==undefined){const text=loaded.value.model,asked=!!leaveText(file.name);
  const open=()=>{openingModel=true;fileScope++;multiView.openText(text,file.name,{asSession:true}).then(()=>{multiphysicsProject();rememberOpened(file.name);}).catch(e=>notice('Session open failed: '+e.message+(multiView.active()?' The current model and its runs are kept.':' Current inputs kept.'))).finally(()=>{openingModel=false;});};
  // an edited model or one with runs is replaced only after the open question, as a session is
  guardLeave(file.name,false,()=>{if(asked||!multiView.inProject()||(!multiView.projectRuns()&&!multiView.edited())){open();return;}
   const runsNow=multiView.projectRuns();
   $('load-confirm').querySelector('h2').textContent='Open model file?';$('load-confirm').querySelector('p').textContent=`It holds the model but no runs. Replaces the current model${runsNow?` and ${runsNow} ${runsNow===1?'run':'runs'} in this tab`:''}; input undo starts at the opened model.`;$('confirm-load').textContent='Open model file';
   const summary=$('load-summary');summary.replaceChildren();
   for(const [name,value] of [['Source',file.name],['Runs that come back','None'],['Model',`${multiView.modelName()} → the model in the file`]]){const term=document.createElement('dt'),detail=document.createElement('dd');term.textContent=name;detail.textContent=value;summary.append(term,detail);}
   pendingLoad={multiphysics:open,opener:$('open-session'),context:loadContext()};if(!$('load-confirm').open)$('load-confirm').showModal();});
  return;}
 const session=loaded.value.session;
 if(session.application==='multiphysics'){requestMultiphysicsSession(session,{label:file.name,source:'file',opener:$('open-session')});return;}
 requestLoad(session.input,{session,label:file.name,fileName:file.name,opener:$('open-session'),newProject:true});
}catch(e){notice('Session open failed: '+e.message+' Current inputs and results kept.');}};

let pendingJob=null;
let jobPhase='idle',jobOperation=0,jobResumeBlocked=false;
// Round 15: the "Optical run complete…" banner leaves after DONE_BANNER_MS or at the next pointer
// or key press or click (assistive technology may send a click alone), whichever comes first (Messages
// keeps the words); the other phases stay until they change.
const DONE_BANNER_MS=6000;let doneBannerTimer=0;
function dismissDoneBanner(){clearTimeout(doneBannerTimer);doneBannerTimer=0;if(jobPhase!=='done')return;jobPhase='idle';refreshJobControls();}
for(const type of ['pointerdown','keydown','click'])document.addEventListener(type,()=>{if(jobPhase==='done')dismissDoneBanner();},true);
const jobMonitor=new OpticalJobMonitor({api:watchedApi,onState:state=>{
 // the runs this result dropped (the run limit) are named after the run's own message (round 17, U2)
 if(state.phase==='done'&&droppedNote){state={...state,message:state.message+' '+droppedNote};droppedNote='';}else if(state.phase==='done')dropSwap=null;
 const wasBusy=solverBusy;if(state.canResume===false)jobResumeBlocked=true;jobPhase=state.phase;solverBusy=['running','loading'].includes(state.phase);
 clearTimeout(doneBannerTimer);doneBannerTimer=0;
 $('job-message').textContent=state.message;$('job-message').title=state.title||''; // round 17 (U11): the job id of a loading result is its title
 if(state.phase==='done')setPending(null);
 if(state.phase==='done')announceResult(state.message,swapAction());else notice(state.message);if(state.phase==='done'&&sessionSizePending)postSessionSize();if(state.phase==='done'||wasBusy!==solverBusy)render();refreshJobControls();
 // the 6 s start once the banner is written and the page rendered: started before the render, the
 // banner was shown for 6 s minus the render of the result page (5.87 s on a macOS runner)
 doneBannerTimer=state.phase==='done'?setTimeout(dismissDoneBanner,DONE_BANNER_MS):0;
},onResult:(result,pending)=>{
 // the modes found (1 to the count asked for), real or {re, im}, ranked by Re n_eff
 const asked=pending.modeCount??DEFAULT_MODE_COUNT,e=result.effective_index,re=Array.isArray(e?.values)?e.values[0]:e?.re?.[0],im=Array.isArray(e?.im)?e.im[0]:null;
 if(e?.unit!=='1'||!Array.isArray(re)||re.length<1||re.length>asked||!re.every(Number.isFinite)||(im!==null&&(!Array.isArray(im)||im.length!==re.length||!im.every(Number.isFinite))))throw new Error('Unsupported optical result.');
 const input=pending.input;
 // the PML check of a run (slice P2): each of its modes paired with the check solve's candidates
 if(pending.checkOf){
  const run=runs.find(r=>r.job===pending.checkOf);if(!run)withPmlCheck(runs,solverRun,pending.checkOf,null);
  // one solve per mode: the records are pooled in this tab until every solve is in
  const pool=checkPools.get(run.job)??[];pool[pending.checkIndex]=checkResultRecord(result);checkPools.set(run.job,pool);
  if(pool.filter(Boolean).length<pending.checkCount)return;
  checkPools.delete(run.job);({runs,selected:solverRun}=withPmlCheck(runs,solverRun,run.job,pairCheck(run.effective_index,run.effective_index_im,pool)));return;
 }
 // an open boundary: the modes above n = 1.45 with their candidate record, and the engine's TE
 // fractions, effective areas (physical window) and group index of those modes (slice P3)
 const open=pending.openBoundary?(()=>{if(im===null)throw new Error('Unsupported optical result.');return openResultValues(result,re,im,pending.openBoundary.target);})():null;
  // a closed-window search (slice C2, A1): the modes above n = 1.45, with the engine's values of those modes
 const target=open?null:pending.searchTarget??null,near=target===null?null:closedResultValues(result,re,target);
 const kept=open?open.re:near?near.re:re,keptIm=open?open.im:im;
 const closedSettings=opticalSettings(input.model.wavelength,input.model.coreMesh,asked);
 const settings=open?openSettings(closedSettings,pending.openBoundary,input.model.shapes):near?closedTargetSettings(closedSettings,target):closedSettings;
 const completed=validateRun({job:pending.job,completedAt:new Date().toISOString(),settings,input,effective_index:keptIm?{re:[...kept],im:[...keptIm]}:[...kept],field:readOpticalField(open?open.data:near?near.data:result,kept.length,{open:!!open}),origin:'local',serverVersion:pending.serverVersion,
  ...(open?{open_boundary:open.record,...keptValues({...engineRunValues(result.summary,re.length),...engineGroupIndex(result.summary,re.length)},open.keep)}:near?keptValues({...engineRunValues(result.summary,re.length),...engineGroupIndex(result.summary,re.length)},near.keep):{
  // the engine's TE fractions and effective areas, kept with the run (a version 9 file keeps them)
  ...engineRunValues(result.summary,re.length),
  // the engine's group index with Also compute group index (a version 9 file keeps it)
  ...engineGroupIndex(result.summary,re.length)})});
 if(result.summary?.group_index_method&&!completed.group_index)notice('The group index of this result could not be read; the run is kept without it.');
 // the reason of each null n_g, in this tab only (a session file does not keep it)
 if(completed.group_index){const reasons=engineGroupIndexReasons(result.summary,re.length);if(reasons)completed.groupIndexReasons=open?open.keep.map(i=>reasons[i]):near?near.keep.map(i=>reasons[i]):reasons;}
 completed.inputRevision=pending.revision;{const started=Date.parse(pending.startedAt);if(Number.isFinite(started))completed.duration=Date.now()-started;}const prior=runs.find(r=>r.job===completed.job);if(prior)completed.number=prior.number;runNumbersUsed=numberRuns([completed],runNumbersUsed);const appended=appendRun(runs,completed),next=prior?inNumberOrder(appended):appended,dropped=runs.filter(r=>!next.includes(r)&&r.job!==completed.job);runs=next;solverRun=runs.find(run=>run.job===completed.job);
 {const other=dropped.length===1?swapCandidate(runs,solverRun):null;dropSwap=other?{kept:dropped[0],other,newest:solverRun,list:runs}:null;}
 // round 22 (V4): with every other earlier run pinned there is no swap: the dropped words say why
 droppedNote=!dropped.length?'':swapCandidate(runs,solverRun)?droppedAfterText(dropped):droppedNoSwapText(dropped);
 compareIds=comparisonAfterRun(runs,compareIds,comparePicked);ui.page='Results';sessionSizePending=true;
}});
function refreshJobControls(){
 if(pendingJob&&connection.ready&&!solverBusy&&pendingJob.serverInstance!==connection.instance){jobResumeBlocked=true;$('job-message').textContent='The server restarted or changed. Detach this job before starting another calculation. Retained results are unchanged.';}
 $('job-input').textContent=pendingJob?pendingJob.job+' · '+designSummary(pendingJob.input.model)+' · λ '+pendingJob.input.model.wavelength+' nm · captured inputs':'';
 $('job-panel').hidden=!pendingJob&&!solverBusy&&jobPhase==='idle';
 // round 20 (Z7): a hidden panel keeps no message ("complete" or "Computing" in the tree while hidden)
 if($('job-panel').hidden){$('job-message').textContent='';$('job-message').title='';}
 $('stop-waiting').disabled=!pendingJob||!solverBusy||!jobMonitor.busy;
 $('resume-job').disabled=!pendingJob||solverBusy||!connection.ready||jobResumeBlocked;
 $('forget-job').disabled=!pendingJob||solverBusy;
 $('run-optical').disabled=solverBusy||!!pendingJob||!!opticalBlock()||!!retentionBlock()||numericDrafts.invalid;
 if(pendingJob&&!solverBusy)$('status').textContent=jobResumeBlocked?'Unavailable job · detach before starting another calculation':'Pending job · resume or detach before starting another calculation';else if(!solverBusy&&retentionBlock())$('status').textContent=retentionBlock();
}
function setPending(record){pendingJob=record;jobResumeBlocked=false;try{storePending(sessionStorage,record);$('job-storage').textContent='';}catch(error){$('job-storage').textContent='Job recovery storage unavailable: '+error.message+' Keep this tab open to retrieve the result.';}}
try{pendingJob=readPending(sessionStorage);if(pendingJob){jobPhase='detached';$('job-message').textContent='Saved job '+pendingJob.job+' is available. Resume retrieves its captured result without changing your current inputs.';}}catch(error){$('job-message').textContent='Job recovery record could not be read: '+error.message;jobPhase='error';}
$('stop-waiting').onclick=()=>{if(jobMonitor.busy){jobOperation++;jobMonitor.stop();}};
$('resume-job').onclick=async()=>{
 if(!pendingJob||solverBusy||!connection.ready||jobResumeBlocked)return;
 jobOperation++;const resumed=pendingJob;try{await jobMonitor.follow(resumed,connection.instance);await followPmlCheck(resumed);}catch(error){if([404,409].includes(error.status))jobResumeBlocked=true;$('job-message').textContent=error.message;}finally{if(solverBusy&&!jobMonitor.busy){solverBusy=false;render();}}
 refreshJobControls();
};
$('forget-job').onclick=()=>{if(solverBusy)return;jobOperation++;setPending(null);jobPhase='idle';$('job-message').textContent='Job detached. Server computation was not cancelled.';notice('Job detached. You may start another calculation; server computation was not cancelled.');render();refreshJobControls();};
$('run-optical').onclick=async()=>{
 if(solverBusy||pendingJob||opticalBlock()||retentionBlock())return;
 try{rejectInvalidInput();}catch(e){notice(e.message);return;}
 // round 21 (W2): no question before the run; a swap offered after the last drop ends here
 dropSwap=null;
 const operation=++jobOperation;edits.record(inputsFile());const capture=edits.capture(),serverVersion=connection.version,serverInstance=connection.instance,doc=opticalDocument();solverBusy=true;jobPhase='validating';render();refreshJobControls();notice('Validating optical input…');$('job-message').textContent='Validating optical input…';
 try{
  // a closed-window search names capabilities v10 (slice C1)
  const em=doc.physics.em1,closedTarget=!em.pml&&em.target_effective_index!==undefined?em.target_effective_index:null,query=closedTarget===null?'':'&'+CLOSED_TARGET_QUERY;
  const validation=await solverApi('/api/validate?workspace_instance='+encodeURIComponent(serverInstance)+query,{doc});if(!validation.ok)throw new Error(validation.error||'Solver validation failed.');
  jobPhase='submitting';$('job-message').textContent='Submitting calculation…';
  const started=await solverApi('/api/run?workspace_instance='+encodeURIComponent(serverInstance)+query,{doc});
  // an open boundary: the choice the run was made with, and whether the PML check follows it
  const ob=builderBoundary(state.openBoundary,state.shapes),openRecord=ob?{openBoundary:{edges:ob.edges,target:ob.target},...(ui.pmlCheck===true?{pmlCheck:true}:{})}:{};
  const record=validatePending({version:1,job:started.job,input:withoutStudy(capture.input),revision:capture.revision,serverVersion,serverInstance,startedAt:new Date().toISOString(),modeCount:doc.physics.em1.mode_count,...openRecord,...(closedTarget===null?{}:{searchTarget:closedTarget})});
  setPending(record);await jobMonitor.follow(record,serverInstance);
  if(operation===jobOperation)await followPmlCheck(record);
 }catch(error){
  const phase=jobPhase,kind=connectionFailure(error);jobPhase='error';
  if(kind==='restarted'){await connectWorkspace();$('job-message').textContent=connection.ready?RESTARTED_MESSAGE:connection.message;}
  else if(kind==='unreachable'){$('job-message').textContent=UNREACHABLE_MESSAGE;connectionLost();}
  else $('job-message').textContent='Calculation request failed: '+error.message+(phase==='submitting'?' If submission reached the server, work may continue.':'');
  notice($('job-message').textContent);
 }
 finally{if(operation===jobOperation){solverBusy=false;render();refreshJobControls();}}
};

// The PML check (slice P2): once the run of `record` is kept, one solve per mode of the same
// document with PML strength 6, a search of 16 and the target at that mode's Re n_eff, on the same
// mesh; their candidates, pooled, are paired with the run's modes (pml_check). A resumed check job
// continues with the next mode; solves finished before a reload are not kept, so the check is
// then incomplete and not stored.
const checkPools=new Map();
async function followPmlCheck(record){
 if(jobPhase!=='done')return;
 const job=record.checkOf??(record.pmlCheck?record.job:null),run=job&&runs.find(r=>r.job===job);if(!run)return;
 const from=record.checkOf?record.checkIndex+1:0,docs=checkDocuments(pendingDocument(record),run.effective_index),{pmlCheck,checkOf,checkIndex,checkCount,...base}=record;
 for(let i=from;i<docs.length;i++){
  solverBusy=true;jobPhase='validating';$('job-message').textContent=`Checking the PML: mode ${i+1} of ${docs.length}, the same mesh with strength 6…`;notice($('job-message').textContent);render();refreshJobControls();
  const doc=docs[i],validation=await solverApi('/api/validate?workspace_instance='+encodeURIComponent(record.serverInstance),{doc});if(!validation.ok)throw new Error(validation.error||'Solver validation failed.');
  jobPhase='submitting';const started=await solverApi('/api/run?workspace_instance='+encodeURIComponent(record.serverInstance),{doc});
  const check=validatePending({...base,job:started.job,startedAt:new Date().toISOString(),checkOf:job,checkIndex:i,checkCount:docs.length});
  setPending(check);await jobMonitor.follow(check,record.serverInstance);if(jobPhase!=='done')return;
 }
 if(!runs.find(r=>r.job===job)?.pml_check){checkPools.delete(job);notice('The PML check is incomplete (the page was reloaded during it); run again to check the PML.');}
}
// The document a pending job was run with, built again from its captured inputs and choices.
function pendingDocument(record){
 const model=record.input.model,ob=record.openBoundary;
 return buildOpticalDocument({...model,modeCount:record.modeCount??DEFAULT_MODE_COUNT,...(ob?{openBoundary:{edges:ob.edges,target:ob.target}}:{})},record.input.setup);
}
async function connectWorkspace(){
 connection.ready=false;connection.message='Checking Studio compatibility…';$('connect-workspace').disabled=true;
 $('connection-status').textContent=connection.message;render();
 try{const caps=checkWorkspaceCapabilities(await solverApi('/api/workspace/capabilities/v8'));connection.ready=true;connection.version=caps.version;connection.instance=caps.instance;connection.message='Connected to simcase '+caps.version+' · optical workspace contract v8';}
 catch(error){
  // no answer at all: say so and keep checking; any other failure is shown and checking stops
  if(connectionFailure(error)==='unreachable'){connection.message=UNREACHABLE_MESSAGE;scheduleReconnect();}
  else{connection.message='Studio connection unavailable or incompatible: '+error.message;$('workspace-tools').open=true;}
 }
 finally{$('connection-status').textContent=connection.message;$('connect-workspace').disabled=false;refreshJobControls();render();refreshJobControls();}
}
// While the server cannot be reached, check every 3 s and reconnect when it is back.
let reconnectTimer=null,reconnecting=false;
function connectionLost(){
 connection.ready=false;connection.message=UNREACHABLE_MESSAGE;$('connection-status').textContent=connection.message;notice(UNREACHABLE_MESSAGE);render();refreshJobControls();
 scheduleReconnect();
}
// One check at a time: the next is scheduled only after the previous one ends. A quiet probe
// runs first, so the page does not flicker through "Checking" while the server is down.
function scheduleReconnect(){
 if(reconnectTimer||reconnecting)return;
 reconnectTimer=setTimeout(async()=>{
  reconnectTimer=null;reconnecting=true;let reachable=true;
  try{
   try{await solverApi('/api/workspace/capabilities/v8');}catch(error){reachable=connectionFailure(error)!=='unreachable';}
   if(reachable)await connectWorkspace();
  }finally{reconnecting=false;}
  if(connection.ready){notice(RECONNECTED_MESSAGE);if($('job-message').textContent===UNREACHABLE_MESSAGE)$('job-message').textContent=RECONNECTED_MESSAGE;}
  else if(!reachable||connection.message===UNREACHABLE_MESSAGE)scheduleReconnect();
 },3000);
}
$('connect-workspace').onclick=connectWorkspace;
installProviderList($('installed-physics'),$('provider-list'),solverApi);
// The ribbon's Physics → Installed opens the same status-bar panel; one status panel at a time.
installStatusPanels([$('installed-physics'),$('workspace-tools')],$('open-installed-physics'));
$('run-heat').onclick=()=>{runHeat().catch(error=>notice('Heat run failed: '+error.message));};heatController?.loadCapability();
$('run-joule').onclick=()=>{jouleView.run();};$('run-multiphysics').onclick=()=>multiView.run();$('run-baseline').onchange=e=>multiView.setBaseline(e.target.checked);$('add-physics').onclick=()=>multiView.addPhysics();$('add-coupling').onclick=()=>multiView.addCoupling();jouleView.loadCapability();
const originalActive=active;active=()=>state.electric===false?originalActive().filter(n=>n!=='Electric currents'):originalActive();document.querySelectorAll('[data-page]').forEach(b=>b.onclick=()=>{ui.page=b.dataset.page;if(ui.page==='Connections')ui.selection='Couplings';render();});installPageTabs(document.querySelector('.page-tabs'));document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{ui.view=b.dataset.view;if(ui.view==='Section'&&pick.boundary!=='oxide-bottom')pick.boundary=null;render();});$('reset').onclick=()=>{if(!leaveMultiphysics())return;fileScope++;numericDrafts.clear();pick.mode='Bodies';pick.boundary=null;ui.body='Core';Object.assign(setup,{materials:{Core:'Silicon',Oxide:'Silica',Heater:''},cooling:'',temperature:293.15,fixed:'',terminal:''});Object.assign(ui,{page:'Model',selection:'Geometry',view:'Perspective'});ui.shape=0;heatDrafts.clear();ui.pmlCheck=false;Object.assign(state,{openBoundary:null,height:220,width:500,wavelength:1550,coreMesh:30,shapes:[{name:'Core',type:'rect',material:'Silicon',x:-250,y:0,w:500,h:220}],thermal:validateThermal(DEFAULT_THERMAL),joule:validateJoule(DEFAULT_JOULE),voltage:1,heat:true,structure:true,optics:true,electric:true});render();};render();refreshPersistence();connectWorkspace();loadNotebookRecovery();})();

installLayout(document.querySelector('main'),document.getElementById('reset-layout'),document.getElementById('layout-status'));
