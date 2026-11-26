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
// waveguide · Run 1", or "· Run 1 (already in this tab)". After rounds 26–30 the not-in-tab case
// no longer adds a parenthesis: the box restores both as one piece of work (Z2), and the
// Workspace tools list names the other model only. item.also: [{model, names, runs, inTab}].
export const alsoWords=item=>(item.also||[]).map(o=>` · also in this project: ${o.model} · ${o.names?.length?o.names.join(', '):`${o.runs} ${o.runs===1?'run':'runs'}`}${o.inTab?' (already in this tab)':''}`).join('');
// The session file a recovery entry names: " · same as file x" when the record still matched it,
// " · file x, changed since" when it did not, " · file x" when the record does not say.
export const fileWords=item=>!item.file?'':item.fileCurrent===true?' · same as file '+item.file:item.fileCurrent===false?' · file '+item.file+', changed since':' · file '+item.file;
// One phrase for browser recovery on the Library page; "Open session file…" is for files.
export const RESTORE_TEXT='Restore from this browser';
// What each Library choice does (round 15). A card opens its model with the runs this tab holds kept;
// the top box restores a browser session's runs; its Not now closes the box.
// Round 16: the button reads "Open model" and the card's description line says the runs stay.
export const CARD_OPEN_TEXT='Open model';
// Round 18 (X10): on the card of a model already in the project (shown or not), "Open model" read as
// if it might reset that model; the card reads "Return to model (2 runs)" there instead.
// Round 20 (Z3): two such cards read alike, so the words name the model: "Return to Optical
// waveguide (2 runs)", "Return to Heated silicon waveguide (1 run)", "Return to Optical waveguide".
export const returnToModelText=(runs,title='model')=>Number.isInteger(runs)&&runs>0?`Return to ${title} (${runs} ${runs===1?'run':'runs'})`:`Return to ${title}`;
export const CARD_STAY_TEXT='Runs stay in this tab when you switch models; this browser can bring completed runs back after you close it.';
export const RESUME_NOT_NOW_TEXT='Not now (choose a model below)';
// The time an offer names: the time of day for a session saved today, else the date and time.
export function offerTime(savedAt,now=new Date()){
 const t=new Date(savedAt),time=t.toLocaleTimeString([],{hour:'numeric',minute:'2-digit'});
 return t.toDateString()===now.toDateString()?time:t.toLocaleDateString()+' '+time;
}
// The time a record's file was saved, for a record that still matches a file it was saved to,
// else the record's own time (round 20, Z4). The Library no longer shows it (the detail line names
// both times, after rounds 26–30); kept for the other callers.
export const offerSavedAt=item=>item.file&&item.fileCurrent===true&&item.fileSavedAt?item.fileSavedAt:item.savedAt;
// Which stored session each model card counts: the newest of its model (entries newest first, each
// {kind, index, application}), on the cards whose model this tab does not hold runs of (busy: the
// set of card ids to leave out). {optical: entry, 'heated-waveguide': entry}.
export function cardRecords(entries,busy=new Set()){
 const out={};
 for(const entry of entries){const card=entry.application==='multiphysics'?'heated-waveguide':'optical';
  if(!busy.has(card)&&!out[card])out[card]=entry;}
 return out;
}
// Library recovery after a restart (after rounds 26–30): one box with one button per piece of work
// (a project file, or a model's records without one), a detail line under it saying how the browser
// copy compares with that file, and the older copies folded under "Earlier copies in this browser
// (N)". Model cards have no restore buttons; a card whose model has a kept record not in the tab
// says so in a plain line (cardKeptText). The labels carry no time and no file words: a browser time
// reads "Kept in this browser T", a file time "saved F" (a real file save).
export const RESTORE_NEWEST_TEXT='Restore newest from this browser';
export const RESUME_HEADING='Continue where you left off';
// Round 31 (K1): the note keeps only its first sentence; the box names one way back per piece of work.
export const RESUME_NOTE='Restore brings back completed runs kept in this browser, without recomputing.';
export const earlierCopiesText=n=>`Earlier copies in this browser (${n})`;
export const cardKeptText=runs=>`Kept in this browser · ${runCount(runs)} · Restore at the top of the page`;
// Round 20 (Z2): when the newest record's project file also holds the other model and browser
// recovery has that model's record (item.pair: {model, runs, savedAt, fileCurrent}; offered by the
// caller only while the tab holds runs of neither model), its button restores both (pair: true).
const runCount=n=>`${n} ${n===1?'run':'runs'}`;
export const pairLine=(item,pair)=>`${item.model||'Optical waveguide'} (${runCount(item.runs)}) and ${pair.model} (${runCount(pair.runs)})`;
// A record as a button names it: the model, the run count and the run names, without file words
// or "also" words ("Optical waveguide · 1 run · Run 1").
const plainLine=item=>sessionLine({...item,file:null,also:undefined});
// How the browser copy compares with the file the record names, after "Kept in this browser T":
// the six cases of the detail line under the newest button. Round 31 (K1): strings 2 and 3 no
// longer add " · Open file… gives the same runs"; the #resume-other detail keeps it (sameTail).
const SAME_TAIL=' · Open file… gives the same runs';
function fileRelation(file,current,savedAt,when,sameTail=''){
 if(!file)return 'not saved to a file';
 if(current===true)return (savedAt?`same as ${file}, saved ${when(savedAt)}`:`same as ${file} as opened`)+sameTail;
 if(current===false)return savedAt?`newer than ${file}, saved here ${when(savedAt)}`:`newer than ${file} as opened`;
 return `last linked to ${file}`;
}
const newer=(a,b)=>b&&(Date.parse(b)||0)>(Date.parse(a)||0)?b:a;
// The detail line of the newest offer (strings 1–6). For a pair, "same" needs both records the same
// as the file, else "newer than"; T is the newer of the two records' times. When the other model's
// runs are already in the tab: " · <model> · <run names> already in this tab".
export function resumeDetail(item,when=offerTime,sameTail=''){
 const pair=item.pair;let current=item.fileCurrent??null,savedAt=item.savedAt;
 if(pair){savedAt=newer(item.savedAt,pair.savedAt);
  const both=[item.fileCurrent??null,pair.fileCurrent??null];
  current=both.every(c=>c===true)?true:both.every(c=>c===null)?null:false;}
 const inTab=(item.also||[]).filter(o=>o.inTab).map(o=>` · ${o.model} · ${o.names?.length?o.names.join(', '):runCount(o.runs)} already in this tab`).join('');
 return `Kept in this browser ${when(savedAt)} · ${fileRelation(item.file,current,item.fileSavedAt,when,sameTail)}${pair?'':inTab}`;
}
// An older copy never says "same as" or "newer than": its match with the file may be stale after a
// later save. It says what it matched when it was kept, or only the file it was last linked to.
// A record without runs saved after the newest one is not called older: "Copy without runs".
function olderCopyDetail(item,when,later=false){
 const file=item.file;
 const tail=!file?'not saved to a file':item.fileCurrent===true?(item.fileSavedAt?`matched ${file} as saved ${when(item.fileSavedAt)}`:`matched ${file} as opened`):`last linked to ${file}`;
 return `${later?'Copy without runs':'Older copy'} · kept in this browser ${when(item.savedAt)} · ${tail}`;
}
// What the box offers: {newest, other, earlier}. newest: the newest stored session with runs, whatever
// its kind (round 19, Y1), or the pair (Z2); other: at most one more piece of work, the other model's
// newest record when it is not paired and its runs are not in the tab (inTab: the model names whose
// runs the tab holds); earlier: every remaining record, newest first. Round 21 (W4): the pair's
// second record is listed in neither. Each choice: {kind, index (earlier records: the record's place
// in storage, which recovery reads), label, detail}.
export function resumeChoices(latest,earlier=[],when=offerTime,{inTab=[]}={}){
 const all=[...(latest?[{item:latest,kind:'latest'}]:[]),...earlier.map((item,position)=>({item,kind:'earlier',index:item.index??position}))];
 const time=e=>Date.parse(e.item.savedAt)||0;all.sort((a,b)=>time(b)-time(a));
 const lead=all.findIndex(e=>e.item.runs>0),first=lead>=0?all.splice(lead,1)[0]:null;
 const paired=first?.item.pair,pairedOut=e=>!!paired&&e.item.model===paired.model&&e.item.file===first.item.file&&e.item.savedAt===paired.savedAt;
 const rest=all.filter(e=>!pairedOut(e));
 const own=e=>({kind:e.kind,...(e.kind==='earlier'?{index:e.index}:{})});
 const newest=first?{...own(first),newest:true,...(paired?{pair:true}:{}),
  label:`${RESTORE_NEWEST_TEXT}: ${paired?pairLine(first.item,paired):plainLine(first.item)}`,detail:resumeDetail(first.item,when)}:null;
 const model=e=>e.item.model||'Optical waveguide';
 const at=first&&!paired?rest.findIndex(e=>e.item.runs>0&&model(e)!==model(first)&&!inTab.includes(model(e))):-1;
 const second=at>=0?rest.splice(at,1)[0]:null;
 const other=second?{...own(second),label:`${RESTORE_TEXT}: ${plainLine(second.item)}`,
  detail:'Older · '+resumeDetail({...second.item,pair:undefined,also:undefined},when,SAME_TAIL).replace(/^Kept/,'kept')}:null;
 return {newest,other,earlier:rest.map(e=>({...own(e),label:'Restore '+plainLine(e.item),detail:olderCopyDetail(e.item,when,!!first&&time(e)>time(first))}))};
}
// resume: optional {latest, earlier, inTab, collapsed, onLatest(button), onEarlier(index, button),
// onPair(index, button), onStartNew(), onToggle(open)}; shown above the templates when there is
// something. The box is a disclosure whose summary is its heading, open whenever it is shown; Not now
// closes it (onStartNew), and opening it shows the same buttons again.
function restoreButton(choice,resume){
 const button=document.createElement('button');button.type='button';button.textContent=choice.label;
 if(choice.kind==='latest'){button.dataset.resumeRecord='-1';button.onclick=()=>resume.onLatest(button);}
 else{button.dataset.resumeEarlier=String(choice.index);button.dataset.resumeRecord=String(choice.index);button.onclick=()=>resume.onEarlier(choice.index,button);}
 // round 20 (Z2): the newest offer of a project with both models restores both
 if(choice.pair&&resume.onPair){button.dataset.resumePair='true';button.onclick=()=>resume.onPair(choice.kind==='latest'?-1:choice.index,button);}
 return button;
}
function detailLine(id,text){const p=document.createElement('p');p.className='resume-detail';if(id)p.id=id;p.textContent=text;return p;}
function resumeCard(resume,earlierOpen=false){
 const {newest,other,earlier}=resumeChoices(resume.latest,resume.earlier,undefined,{inTab:resume.inTab||[]});
 if(!newest&&!other&&!earlier.length)return null;
 const card=document.createElement('details');card.className='resume-card';card.id='resume-box';card.open=!resume.collapsed;
 const summary=document.createElement('summary'),heading=document.createElement('h3');heading.id='resume-heading';heading.textContent=RESUME_HEADING;summary.append(heading);
 card.addEventListener?.('toggle',()=>resume.onToggle?.(card.open));
 const note=document.createElement('p');note.className='resume-note';note.textContent=RESUME_NOTE;
 const actions=document.createElement('div');actions.className='resume-actions';
 for(const [choice,id] of [[newest,'resume-newest'],[other,'resume-other']]){
  if(!choice)continue;
  const button=restoreButton(choice,resume);
  if(choice.newest){button.className='primary';button.id='resume-newest';}else button.id='resume-other';
  button.setAttribute('aria-describedby',id+'-detail');
  const piece=document.createElement('div');piece.className='resume-piece';piece.append(button,detailLine(id+'-detail',choice.detail));actions.append(piece);
 }
 if(earlier.length){
  const copies=document.createElement('details');copies.id='earlier-copies';copies.open=earlierOpen;
  const head=document.createElement('summary');head.textContent=earlierCopiesText(earlier.length);copies.append(head);
  for(const choice of earlier){const piece=document.createElement('div');piece.className='resume-piece';piece.append(restoreButton(choice,resume),detailLine(null,choice.detail));copies.append(piece);}
  actions.append(copies);
 }
 const fresh=document.createElement('button');fresh.type='button';fresh.id='resume-start-new';fresh.textContent=RESUME_NOT_NOW_TEXT;fresh.onclick=()=>resume.onStartNew();
 actions.append(fresh);card.append(summary,note,actions);return card;
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
// The project's name on the Library (P3), at the right of the Open file… row, so the cards and
// their restore offers stay in the first screen; the project line heads the page in its view title
// row. Rename takes 1 to 80 characters with no control characters; an empty name is refused by
// name, and the field shows the name kept. project: {name, onRename(value) -> accepted}.
// Round 16: a name taken from a file name follows Save As; a name set here stays.
export const RENAME_NOTE='The name is written to the project file on the next File › Save. A name set here stays when Save As uses another file name.';
// Round 25: a re-render of the Library (a browser recovery update, for example) keeps a name being
// typed, and its focus and selection, instead of putting the stored name back over it.
function projectNameDraft(doc=globalThis.document){
 const prior=doc?.getElementById?.('project-name-input');
 if(!prior||prior.value===prior.dataset.kept)return null;
 return {value:prior.value,focused:doc.activeElement===prior,start:prior.selectionStart,end:prior.selectionEnd};
}
export {projectNameDraft};
function projectNameForm(project,draft=null){
 const form=document.createElement('form');form.id='project-name-form';form.className='project-name';
 const label=document.createElement('label');label.htmlFor='project-name-input';label.textContent='Project name';
 const input=document.createElement('input');input.id='project-name-input';input.type='text';input.maxLength=80;input.autocomplete='off';input.spellcheck=false;input.placeholder='Untitled project';input.dataset.kept=project.name||'';input.value=draft?draft.value:project.name||'';input.setAttribute('aria-describedby','project-name-note');
 if(draft?.focused)queueMicrotask(()=>{if(input.isConnected){input.focus({preventScroll:true});try{input.setSelectionRange(draft.start,draft.end);}catch{}}});
 const button=document.createElement('button');button.type='submit';button.id='project-rename';button.textContent='Rename';
 const note=document.createElement('span');note.id='project-name-note';note.className='visually-hidden';note.textContent=RENAME_NOTE;form.title=RENAME_NOTE;
 form.onsubmit=event=>{event.preventDefault();if(!project.onRename(input.value))input.value=project.name||'';else input.dataset.kept=input.value;};
 form.append(label,input,button,note);return form;
}
// The third argument (once each card's restore offer) is not read: cards have no restore buttons.
// kept: the cards whose model has a kept record not in the tab, with that record's run count; the
// card says "Kept in this browser · N runs · Restore at the top of the page" (not a control).
// onOpenFile: the Library's one "Open file…", at the top of the page.
// inProject: the cards whose model is in the project but not shown, with its run count; the card
// reads "In this project · N runs", and choosing it shows that model (P3).
export const inProjectText=runs=>`In this project · ${runs} ${runs===1?'run':'runs'}`;
// returnTo: the cards whose model is in the project, shown or not, with its run count (round 18).
export function renderApplications(host,resume=null,_unused=null,{onOpenFile=null,project=null,inProject={},returnTo={},kept={}}={}){
 // the earlier copies keep their open state across a re-render (a browser recovery update, for example)
 const earlierOpen=!!host.querySelector?.('#earlier-copies')?.open;
 const draft=projectNameDraft(host.ownerDocument);host.replaceChildren();
 if(onOpenFile)host.append(libraryFiles(onOpenFile,project?projectNameForm(project,draft):null));
 const card=resume?resumeCard(resume,earlierOpen):null;if(card)host.append(card);
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
  // a kept record of this model not in the tab: where to restore it, not a second restore control
  if(kept[app.id]!==undefined){const line=document.createElement('span');line.className='card-kept';line.textContent=cardKeptText(kept[app.id]);button.append(line);}
  cards.append(button);
 }
 const contract=document.createElement('section');contract.className='application-contract';
 const contractTitle=document.createElement('h3');contractTitle.textContent='What this workspace supports';
 const list=document.createElement('ul');for(const text of CHOOSER_NOTES){const item=document.createElement('li');item.textContent=text;list.append(item);}
 const choice=document.createElement('p');choice.textContent=CHOOSER_CHOICE;contract.append(contractTitle,list,choice);
 host.append(heading,intro,cards,contract);
}
