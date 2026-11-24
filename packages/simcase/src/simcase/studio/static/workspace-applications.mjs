// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0

// Workspace adapter availability, not a claim about the entire solver library.
export const APPLICATIONS=Object.freeze([
 Object.freeze({id:'optical',title:'Optical waveguide',status:'Optical mode solver',available:true,description:'Edit the core, calculate optical modes, compare fields and save results.',scope:'2D cross section in silica · rectangles, circles, polygons · wavelength and core mesh',physics:Object.freeze({electric:false,heat:false,structure:false,optics:true})}),
 Object.freeze({id:'heat',title:'Steady heat conduction',status:'Heat conduction solver',available:true,description:'Edit a rectangular plate, its conductivity, heat source and side conditions, then compute temperature and heat flux.',scope:'2D rectangle · uniform k and source · fixed temperature, insulation, flux or convection per side',physics:Object.freeze({electric:false,heat:true,structure:false,optics:false})}),
 Object.freeze({id:'joule',title:'Joule heating',status:'Electric current and heat solver',available:true,description:'Place conductors of named materials in a rectangle, give each its electrical and thermal conductivity (constant or temperature-dependent), set side potentials and thermal conditions, then compute temperature, potential, current and Joule power.',scope:'2D named material regions in mm · constant or linear-resistivity σ(T) · potential or current and temperature, flux or convection per side',physics:Object.freeze({electric:true,heat:true,structure:false,optics:false})}),
]);
// Coupled models (contract D2): the card opens a multiphysics document; one Run solves every
// physics in the order its couplings give.
export const COUPLED_TEMPLATES=Object.freeze([
 Object.freeze({id:'heated-waveguide',title:'Heated silicon waveguide',status:'Heat → optical modes · coupled',available:true,description:'A silicon core under a heater: steady heat gives the temperature, and the optical modes take n(T) from it on one shared mesh.',scope:'500 × 220 nm core on oxide · 2 µm heater 1.1 µm above · bottom at 300 K · λ 1550 nm'})
]);
export function templatePhysics(id){
 const application=APPLICATIONS.find(a=>a.id===id);
 if(!application)throw new Error('Unknown model template.');
 return {...application.physics};
}
// The runs of a stored session by name, oldest first: a run's name, else "Run <number>" (an
// optical run is numbered by its place in the list, a multiphysics run by its own number).
export function sessionRunNames(session){
 // the run number with the name, as the run list names a run: "Run 1 · design A", or "Run 2"
 return (session?.runs||[]).map((run,i)=>`Run ${Number.isInteger(run.number)?run.number:i+1}`+(run.label?' · '+run.label:''));
}
// One stored session as a recovery list names it: the model, the run count, the run names and,
// when the record came from a session file, that file ("Optical waveguide · 2 runs · design A,
// Run 2 · file optical-waveguide-session-2026-11-22-1425.json"). The lists show each session text
// once (distinctRecords), so two entries never read alike.
export function sessionLine(item){
 return (item.model?item.model+' · ':'')+item.runs+(item.runs===1?' run':' runs')+(item.names?.length?' · '+item.names.join(', '):'')+fileWords(item)+alsoWords(item);
}
// Round 18 (X7): a record names one model, but its project file may hold the other one too. When
// browser recovery holds a record of the other model under the same file, the offer lists it with
// its runs and says this button does not restore it: " · also in this project: Heated silicon
// waveguide · Run 1 (restored separately)", or "(already in this tab)". item.also: [{model, names,
// runs, inTab}].
export const alsoWords=item=>(item.also||[]).map(o=>` · also in this project: ${o.model} · ${o.names?.length?o.names.join(', '):`${o.runs} ${o.runs===1?'run':'runs'}`} (${o.inTab?'already in this tab':'restored separately'})`).join('');
// The session file a recovery entry names: " · same as file x" when the record still matched it,
// " · file x, changed since" when it did not, " · file x" when the record does not say.
export const fileWords=item=>!item.file?'':item.fileCurrent===true?' · same as file '+item.file:item.fileCurrent===false?' · file '+item.file+', changed since':' · file '+item.file;
// One phrase for browser recovery on the Library page; "Open session file…" is for files.
export const RESTORE_TEXT='Restore from this browser';
// What each Library choice does (round 15). A card opens its model with the runs this tab holds kept;
// its offer restores a browser session's runs; the card's Start new opens the model without those runs
// (the inputs are the model's, not emptied); the top box's choice only closes the box.
// Round 16: the button reads "Open model" and the card's description line says the runs stay.
export const CARD_OPEN_TEXT='Open model';
// Round 18 (X10): on the card of a model already in the project (shown or not), "Open model" read as
// if it might reset that model; the card reads "Return to model (2 runs)" there instead.
// Round 20 (Z3): two such cards read alike, so the words name the model: "Return to Optical
// waveguide (2 runs)", "Return to Heated silicon waveguide (1 run)", "Return to Optical waveguide".
export const returnToModelText=(runs,title='model')=>Number.isInteger(runs)&&runs>0?`Return to ${title} (${runs} ${runs===1?'run':'runs'})`:`Return to ${title}`;
export const CARD_STAY_TEXT='Runs stay in this tab until you close it.';
export const CARD_START_NEW_TEXT='Start new (no runs)';
export const RESUME_NOT_NOW_TEXT='Not now (choose a model below)';
// The time an offer names: the time of day for a session saved today, else the date and time.
export function offerTime(savedAt,now=new Date()){
 const t=new Date(savedAt),time=t.toLocaleTimeString([],{hour:'numeric',minute:'2-digit'});
 return t.toDateString()===now.toDateString()?time:t.toLocaleDateString()+' '+time;
}
// The time a card offer names. The record is written a moment after a save, so a record that is
// the same as its session file names the file's save time ("same as file x, saved 9:24 PM"), the
// time people remember; else the browser copy's time, said as such when a file is named beside it.
// Round 19 (Y1): an offer that is not the newest stored session with runs says so, with its save
// time: " · older · saved 5:38 AM", " · older · same as file x, saved T", " · older · browser copy T ·
// same as file x".
function offerTimeWords(item,when,older=false){
 const old=older?' · older':'';
 if(item.file&&item.fileCurrent===true&&item.fileSavedAt)return `${old} · same as file ${item.file}, saved ${when(item.fileSavedAt)}`;
 if(item.file&&item.fileCurrent===true)return `${old} · browser copy ${when(item.savedAt)} · same as file ${item.file}`;
 return `${old} · ${older?'saved ':''}${when(item.savedAt)}${fileWords(item)}`;
}
// A model card's offer when the tab holds none of that model's runs and browser recovery holds a
// session of it: "Restore from this browser · Optical waveguide · design A, design B · 2:25 PM",
// then the file it names, shown before Start new. item: a recovery entry {runs, names, savedAt,
// file, fileCurrent, fileSavedAt}; model: the model the entry names.
// older (round 19, Y1): the entry is not the newest stored session with runs.
export function cardResumeChoice(item,model,when=offerTime,{older=false}={}){
 const names=item.names?.length?item.names.join(', '):`${item.runs} ${item.runs===1?'run':'runs'}`;
 return {label:`${RESTORE_TEXT} · ${model} · ${names}${offerTimeWords(item,when,older)}${alsoWords(item)}`};
}
export const opticalResumeChoice=(item,when=offerTime)=>cardResumeChoice(item,'Optical waveguide',when);
// Which stored session each model card offers: the newest of its model (entries newest first, each
// {kind, index, application}), on the cards whose model this tab does not hold runs of (busy: the
// set of card ids to leave out). {optical: entry, 'heated-waveguide': entry}. Round 19 (Y1): the top
// box lists every session, newest first, so a card's record is also listed there.
export function cardRecords(entries,busy=new Set()){
 const out={};
 for(const entry of entries){const card=entry.application==='multiphysics'?'heated-waveguide':'optical';
  if(!busy.has(card)&&!out[card])out[card]=entry;}
 return out;
}
// What the landing page offers to resume: the latest browser session and the
// earlier ones (C1), each as {runs, savedAt, model, names}: model names the session's model and
// names its runs (sessionLine). Empty when there is nothing.
// Round 19 (Y1): newest first, and the newest stored session with runs leads, whatever its kind:
// "Restore newest from this browser: Optical waveguide · 6 runs · … · saved 5:46 AM" (newest: true);
// each other one "Restore from this browser: … · older · saved 5:38 AM" ("older" left out for a
// session without runs saved after it).
export const RESTORE_NEWEST_TEXT='Restore newest from this browser';
export function resumeChoices(latest,earlier=[],when=offerTime){
 // index: the record's place in storage, which recovery reads (given by the caller, else the position)
 const all=[...(latest?[{item:latest,kind:'latest'}]:[]),...earlier.map((item,position)=>({item,kind:'earlier',index:item.index??position}))];
 const time=e=>Date.parse(e.item.savedAt)||0;all.sort((a,b)=>time(b)-time(a));
 const lead=all.findIndex(e=>e.item.runs>0),newest=lead>=0?all.splice(lead,1)[0]:null;
 return [...(newest?[{...newest,newest:true}]:[]),...all].map(e=>{
  const older=!!newest&&!e.newest&&!(time(e)>time(newest));
  return {kind:e.kind,...(e.kind==='earlier'?{index:e.index}:{}),...(e.newest?{newest:true}:{}),
   label:`${e.newest?RESTORE_NEWEST_TEXT:RESTORE_TEXT}: ${sessionLine(e.item)} · ${older?'older · ':''}saved ${when(e.item.savedAt)}`};
 });
}
// resume: optional {latest, earlier, onLatest(button), onEarlier(index, button),
// onOpenFile(), onStartNew()}; shown above the templates when there is something. Round 19 (Y1): every
// stored session the tab does not hold, newest first; a card repeats its model's newest.
function resumeCard(resume){
 const choices=resumeChoices(resume.latest,resume.earlier);if(!choices.length)return null;
 const card=document.createElement('section');card.className='resume-card';card.setAttribute('aria-labelledby','resume-heading');
 const heading=document.createElement('h3');heading.id='resume-heading';heading.textContent='Continue where you left off';
 const note=document.createElement('p');note.textContent='Completed runs from this browser can be brought back without recomputing. Starting new keeps them as earlier sessions.';
 const actions=document.createElement('div');actions.className='resume-actions';
 for(const choice of choices){
  const button=document.createElement('button');button.type='button';button.textContent=choice.label;
  if(choice.newest){button.className='primary';button.id='resume-newest';}
  if(choice.kind==='latest'){button.dataset.resumeRecord='-1';button.onclick=()=>resume.onLatest(button);}
  else{button.dataset.resumeEarlier=String(choice.index);button.dataset.resumeRecord=String(choice.index);button.onclick=()=>resume.onEarlier(choice.index,button);}
  actions.append(button);
 }
 const fresh=document.createElement('button');fresh.type='button';fresh.id='resume-start-new';fresh.textContent=RESUME_NOT_NOW_TEXT;fresh.onclick=()=>resume.onStartNew();
 actions.append(fresh);card.append(heading,note,actions);return card;
}
// The Library page notes: what each model supports and what File › Save keeps of it. A session
// file holds the inputs of every single-physics model and the optical runs, or a multiphysics
// model with its runs; heat and Joule heating results are not written to it.
export const CHOOSER_NOTES=Object.freeze([
 'Optical: up to 8 rectangles, circles or polygons of ten lossless materials (silicon, silicon nitride, silica, air, sapphire, lithium niobate, InP, GaAs, CaF2, MgF2) in a silica background; wavelength 1400–1700 nm, core mesh 20–60 nm, 1 to 8 modes (Modes to find, 2 by default). File › Save keeps the inputs, the runs and the comparison.',
 'Steady heat: one homogeneous rectangle with constant conductivity and source; each side insulated, at fixed temperature, with inward heat flux or with convection. File › Save keeps the plate inputs; heat results stay in this tab.',
 'Joule heating: a rectangle in mm with up to 8 rectangles, circles or polygons over a background material, up to 6 materials with thermal conductivity and a constant or linear-resistivity electrical conductivity; each side insulating, at fixed potential or with inward current, and insulated, at fixed temperature, with inward heat flux or with convection. Temperature-dependent materials iterate (Picard, or Newton chosen under Study). File › Save keeps the inputs; Joule heating results stay in this tab.',
 'Heated silicon waveguide: a multiphysics model of steady heat and optical modes on one mesh. Add or remove physics and couplings, check them before running, and run every physics in solve order. File › Save keeps the model with its runs, their names and pins, and the without-heater results.'
]);
export const CHOOSER_CHOICE='Choosing a model sets which physics it solves. Dimensions you entered and runs you completed are kept, and Undo takes the choice back between the optical, steady heat and Joule heating models. The heated silicon waveguide has its own Undo for its edits: to leave it, choose another model here.';
const PORTABLE_NOTE='A project file is the copy that moves between computers; browser recovery stays in this browser.';
// "Open file…" has one place, at the top of the Library: it opens a project file, a session file or
// a model file (File › Open), whatever the cards below offer.
function libraryFiles(onOpenFile,extra=null){
 const bar=document.createElement('div');bar.className='library-files';
 const open=document.createElement('button');open.type='button';open.id='library-open-file';open.textContent='Open file…';open.setAttribute('aria-keyshortcuts','Control+O Meta+O');open.onclick=()=>onOpenFile();
 const portable=document.createElement('p');portable.className='library-portable';portable.textContent=PORTABLE_NOTE;
 bar.append(open,portable);if(extra)bar.append(extra);return bar;
}
// A model card with its resume offer under it: Resume first, then Start new. key: the id the
// buttons carry (resume-optical, optical-start-new; resume-heated-waveguide, ...).
function cardSlot(button,offer,key){
 const slot=document.createElement('div');slot.className='card-slot';
 const actions=document.createElement('div');actions.className='card-resume';
 const go=document.createElement('button');go.type='button';go.id='resume-'+key;go.className='primary';go.textContent=offer.label;if(offer.record!=null)go.dataset.resumeRecord=String(offer.record);go.onclick=()=>offer.onResume(go);
 const fresh=document.createElement('button');fresh.type='button';fresh.id=key+'-start-new';fresh.textContent=CARD_START_NEW_TEXT;fresh.onclick=()=>offer.onStartNew();
 actions.append(go,fresh);slot.append(button,actions);
 return slot;
}
// The project's name on the Library (P3), at the right of the Open file… row, so the cards and
// their restore offers stay in the first screen; the project line heads the page in its view title
// row. Rename takes 1 to 80 characters with no control characters; an empty name is refused by
// name, and the field shows the name kept. project: {name, onRename(value) -> accepted}.
// Round 16: a name taken from a file name follows Save As; a name set here stays.
export const RENAME_NOTE='The name is written to the project file on the next File › Save. A name set here stays when Save As uses another file name.';
function projectNameForm(project){
 const form=document.createElement('form');form.id='project-name-form';form.className='project-name';
 const label=document.createElement('label');label.htmlFor='project-name-input';label.textContent='Project name';
 const input=document.createElement('input');input.id='project-name-input';input.type='text';input.maxLength=80;input.autocomplete='off';input.spellcheck=false;input.placeholder='Untitled project';input.value=project.name||'';input.setAttribute('aria-describedby','project-name-note');
 const button=document.createElement('button');button.type='submit';button.id='project-rename';button.textContent='Rename';
 const note=document.createElement('span');note.id='project-name-note';note.className='visually-hidden';note.textContent=RENAME_NOTE;form.title=RENAME_NOTE;
 form.onsubmit=event=>{event.preventDefault();if(!project.onRename(input.value))input.value=project.name||'';};
 form.append(label,input,button,note);return form;
}
// offers: each model card's resume offer by card id ({optical, 'heated-waveguide'}), each
// {label, record, onResume(button), onStartNew()}; a card without one has none. onOpenFile:
// the Library's one "Open session file…", at the top of the page.
// inProject: the cards whose model is in the project but not shown, with its run count; the card
// reads "In this project · N runs", and choosing it shows that model (P3).
export const inProjectText=runs=>`In this project · ${runs} ${runs===1?'run':'runs'}`;
// returnTo: the cards whose model is in the project, shown or not, with its run count (round 18).
export function renderApplications(host,resume=null,offers={},{onOpenFile=null,project=null,inProject={},returnTo={}}={}){
 host.replaceChildren();offers={...(offers||{})};
 if(onOpenFile)host.append(libraryFiles(onOpenFile,project?projectNameForm(project):null));
 const card=resume?resumeCard(resume):null;if(card)host.append(card);
 const heading=document.createElement('h2');heading.textContent='Choose a starting model';
 const intro=document.createElement('p');intro.textContent='One workspace for model setup, studies and results. Check what can run before you start.';
 const cards=document.createElement('div');cards.className='cards';
 for(const app of [...APPLICATIONS,...COUPLED_TEMPLATES]){
  const button=document.createElement('button');button.dataset.template=app.id;
  const title=document.createElement('strong');title.textContent=app.title;
  const status=document.createElement('span');status.className='application-status'+(app.available?' available':'');status.textContent=app.status;
  const description=document.createElement('p');description.textContent=app.description+' '+CARD_STAY_TEXT;
  const scope=document.createElement('span');scope.className='card-scope';scope.textContent=app.scope;
  // what the card does (round 15; words of round 16): it opens the model; the description says the runs stay
  const action=document.createElement('span');action.className='card-action';action.textContent=CARD_OPEN_TEXT;if(returnTo[app.id]!==undefined)action.textContent=returnToModelText(returnTo[app.id],app.title);
  button.append(title,status,description,scope,action);
  // a model of the project not shown (P3): "In this project · N runs"
  if(inProject[app.id]!==undefined){const here=document.createElement('span');here.className='card-project';here.textContent=inProjectText(inProject[app.id]);button.append(here);}
  cards.append(offers[app.id]?cardSlot(button,offers[app.id],app.id):button);
 }
 const contract=document.createElement('section');contract.className='application-contract';
 const contractTitle=document.createElement('h3');contractTitle.textContent='What this workspace supports';
 const list=document.createElement('ul');for(const text of CHOOSER_NOTES){const item=document.createElement('li');item.textContent=text;list.append(item);}
 const choice=document.createElement('p');choice.textContent=CHOOSER_CHOICE;contract.append(contractTitle,list,choice);
 host.append(heading,intro,cards,contract);
}
