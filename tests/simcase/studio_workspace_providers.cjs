// Copyright 2026 Yongha Kim (FieldAlgo)
// SPDX-License-Identifier: Apache-2.0
// The workspace's list of installed physics providers: a provider's strings are text, never markup.
const {test,before}=require('node:test');const assert=require('node:assert/strict');
let escapeHtml,readProviders,providersHtml,installProviderList,MAX_PROVIDERS;
before(async()=>({escapeHtml,readProviders,providersHtml,installProviderList,MAX_PROVIDERS}=await import('../../packages/simcase/src/simcase/studio/static/workspace-providers.mjs')));
const builtin=()=>({name:'openphysics-fem',version:'0.1.0',distribution:'simcase',protocol:1,status:'available',error:null,kinds:['electric_joule','em.modes2d']});
const hostile='<img src=x onerror=alert(1)>';
// Every tag the rendered table may hold; anything else would be markup a provider supplied.
const OWN_TAGS=new Set(['table','thead','tbody','tr','th','td','span','p']);
const tags=html=>[...html.matchAll(/<\/?([a-zA-Z][a-zA-Z0-9-]*)/g)].map(m=>m[1].toLowerCase());
test('escapeHtml escapes every markup character',()=>{
 assert.equal(escapeHtml(`<a href="x" title='y'>&</a>`),'&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;&lt;/a&gt;');
 assert.equal(escapeHtml(42),'42');
});
test('a hostile provider renders as text in every field',()=>{
 const list=readProviders({providers:[builtin(),{name:hostile,version:hostile,distribution:hostile,protocol:null,status:'unavailable',error:'ImportError: '+hostile,kinds:[]},{name:'x',version:'1',distribution:'d',protocol:1,status:'available',error:null,kinds:[hostile,'<script>alert(2)</script>']}]});
 const html=providersHtml(list);
 assert.ok(!html.includes('<img')&&!html.includes('<script'));
 assert.ok(!/onerror=alert/.test(html.replace(/&lt;img src=x onerror=alert\(1\)&gt;/g,'')));
 assert.ok(html.includes('&lt;img src=x onerror=alert(1)&gt;'));
 assert.ok(html.includes('ImportError: &lt;img src=x onerror=alert(1)&gt;'));
 assert.ok(html.includes('&lt;script&gt;alert(2)&lt;/script&gt;'));
 for(const tag of tags(html))assert.ok(OWN_TAGS.has(tag),tag);
});
test('the table lists name, version, distribution, status, kinds and the error of an unavailable provider',()=>{
 const html=providersHtml(readProviders({providers:[builtin(),{name:'broken',version:null,distribution:'broken-dist',protocol:null,status:'unavailable',error:"ImportError: No module named 'broken_physics'",kinds:[]}]}));
 for(const text of ['openphysics-fem','0.1.0','simcase','Available','electric_joule, em.modes2d','broken','broken-dist','Unavailable',"ImportError: No module named &#39;broken_physics&#39;",'unknown'])assert.ok(html.includes(text),text);
 assert.equal((html.match(/class="provider-error"/g)||[]).length,1);
 assert.match(providersHtml([]),/No physics providers are installed/);
});
test('a reply that is not a provider list is refused',()=>{
 const changes=[d=>d.providers=null,d=>delete d.providers,d=>d.providers={},d=>d.providers[0]=null,d=>d.providers[0]=[],d=>d.providers[0].name='',d=>d.providers[0].name=7,d=>delete d.providers[0].name,
  d=>d.providers[0].version=1,d=>d.providers[0].distribution={},d=>d.providers[0].protocol='1',d=>d.providers[0].protocol=1.5,d=>d.providers[0].status='ok',d=>d.providers[0].error='x',
  d=>d.providers[0].kinds='em.modes2d',d=>d.providers[0].kinds=[1],d=>d.providers[0].name='x'.repeat(4097),
  d=>{d.providers[0].status='unavailable';},d=>d.providers=Array.from({length:MAX_PROVIDERS+1},builtin)];
 for(const change of changes){const d={providers:[builtin()]};change(d);assert.throws(()=>readProviders(d));}
 assert.throws(()=>readProviders(null));
 assert.deepEqual(readProviders({providers:[builtin()]}),[builtin()]);
});
test('the list loads when the panel opens and a failure is shown as text',async()=>{
 const listeners=[];const details={open:false,addEventListener:(type,fn)=>{assert.equal(type,'toggle');listeners.push(fn);}};
 const target={textContent:'',innerHTML:''};const requests=[];
 let reply={providers:[builtin()]};
 const pending=installProviderList(details,target,async path=>{requests.push(path);if(reply instanceof Error)throw reply;return reply;});
 listeners[0]();assert.equal(requests.length,0,'a closing toggle requests nothing');
 details.open=true;listeners[0]();listeners[0]();
 await pending();
 assert.deepEqual(requests,['/api/providers'],'one request at a time');
 assert.match(target.innerHTML,/openphysics-fem/);
 reply=new Error(hostile);target.innerHTML='';listeners[0]();await pending();
 assert.equal(target.textContent,'Installed physics could not be listed: '+hostile);
 assert.equal(target.innerHTML,'','an error is written as text only');
 reply={providers:[{...builtin(),status:'bad'}]};listeners[0]();await pending();
 assert.match(target.textContent,/^Installed physics could not be listed: Studio sent a provider list/);
});
