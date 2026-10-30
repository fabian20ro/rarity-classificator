// Public UI seam: clicks, reload, visible status, persistent storage and downloads.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const code=fs.readFileSync(process.argv[2],'utf8');
const context=(id)=>({context_id:id,pos:'substantiv',meaning:'Sens verificat',example:'exemplu',source:'https://dexonline.ro/definitie/test'});
const data={version:'independent-fixture-v1',pack_sha256:'fixture',rubric:'exact-form-most-familiar-valid-sense-v1',forms:[{word_id:'1',word:'vară',contexts:[context('1:season'),context('1:cousin')]},{word_id:'2',word:'ued',contexts:[context('2:valley')]}]};
const key='romanian-'+data.version,legacy='romanian-short-forms-2026-10-21-v1';
const storage=new Map([[legacy,'original evaluation']]),downloads=[];
function load(){
 const elements=new Map(),element=id=>elements.get(id)||elements.set(id,{textContent:'',innerHTML:'',value:'',disabled:false,setAttribute(k,v){this[k]=v;}}).get(id);
 element('case-data').textContent=JSON.stringify(data);
 const buttons=[1,2,3,4,5].map(level=>({...element('level-'+level),dataset:{level:String(level)}}));
 vm.runInNewContext(code,{document:{getElementById:element,querySelectorAll:()=>buttons,createElement:()=>({click(){downloads.push({filename:this.download,blob:this.href});}})},localStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)},Blob,URL:{createObjectURL:b=>b,revokeObjectURL(){}},setTimeout(){},console});
 return{element,buttons};
}
async function exported(app){app.element('export-json').onclick();return JSON.parse(await downloads.at(-1).blob.text());}
(async()=>{
 let app=load();assert.equal(app.element('word').textContent,'vară');assert.match(app.element('progress-text').textContent,/0\/2/);
 app.buttons[0].onclick();assert.match(app.element('alert').textContent,/Alege sensul/);
 app.element('familiar').value='1:cousin';app.element('familiar').onchange();app.buttons[1].onclick();
 app.element('notes').value='notă, cu "citat"\nși rând nou';app.element('notes').oninput();
 app=load();assert.equal(app.element('familiar').value,'1:cousin');assert.match(app.element('current-status').textContent,/2/);
 let saved=await exported(app);assert.equal(saved.answers['1'].level,2);assert.equal(saved.answers['1'].first_level,2);assert.equal(saved.answers['1'].notes,'notă, cu "citat"\nși rând nou');
 app.buttons[2].onclick();saved=await exported(app);assert.equal(saved.answers['1'].first_level,2);assert.equal(saved.answers['1'].level,3);
 app.element('familiar').value='other';app.element('familiar').onchange();assert.equal((await exported(app)).answers['1'].level,null);
 app.element('notes').value='';app.element('notes').oninput();app.buttons[3].onclick();assert.match(app.element('alert').textContent,/Descrie/);
 app.element('notes').value='sens nou';app.element('notes').oninput();app.buttons[3].onclick();
 app.element('notes').value='';app.element('notes').oninput();
 assert.match(app.element('progress-text').textContent,/0\/2/);assert.equal(app.element('current-status').textContent,'De evaluat');
 app.element('notes').value='sens nou';app.element('notes').oninput();app.buttons[3].onclick();
 app.element('next').onclick();app.element('unsure').onclick();saved=await exported(app);
 assert.equal(saved.answers['2'].decision,'unsure');assert.equal(saved.answers['2'].level,null);
 app.element('export-csv').onclick();let csv=await downloads.at(-1).blob.text();assert.match(csv,/other/);assert.match(csv,/sens nou/);assert.match(csv,/unsure/);
 assert.equal(storage.get(legacy),'original evaluation');assert.equal(saved.pack_sha256,'fixture');assert.equal(saved.ai_exposure,false);
 assert.ok(saved.events.filter(e=>e.kind==='rate').length===4);assert.equal(saved.case_pack.forms.length,2);
 // Corrupt state must never be overwritten with an empty round.
 storage.set(key,'{corrupt');app=load();app.buttons[0].onclick();assert.equal(storage.get(key),'{corrupt');assert.match(app.element('save-status').textContent,/păstrat/);
 assert.equal((await exported(app)).preserved_raw,'{corrupt');
 console.log('PASS: blind form rating/reload/revisions/context change/notes/exports and old-state preservation');
})().catch(e=>{console.error(e);process.exitCode=1});
