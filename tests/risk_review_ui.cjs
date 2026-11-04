// Public UI: missing-context card, truthful sources, persistence and isolated exports.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const code=fs.readFileSync(process.argv[2],'utf8');
const data={mode:'risk',version:'fixture-v1',pack_sha256:'risk-fixture',forms:[
 {word_id:'1',word:'ata',valid_pos:['substantiv feminin'],contexts:[{context_id:'1:atu',pos:'substantiv feminin',meaning:'Atu.',restrictions:['variantă lexicală','regional'],source:'https://dexonline.ro/definitie/ata'}]},
 {word_id:'2',word:'necunoscut',valid_pos:['adjectiv','substantiv'],contexts:[]}
]};
const key='romanian-risk-'+data.version,legacy='romanian-'+data.version;
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
 let app=load();assert.equal(app.element('word').textContent,'ata');
 assert.match(app.element('contexts').innerHTML,/variantă lexicală/);
 assert.match(app.element('contexts').innerHTML,/regional/);
 assert.match(app.element('contexts').innerHTML,/substantiv feminin/);
 app.buttons[3].onclick();app.element('next').onclick();
 assert.match(app.element('contexts').innerHTML,/Nu avem un sens verificat/);
 assert.match(app.element('contexts').innerHTML,/adjectiv/);
 assert.doesNotMatch(app.element('contexts').innerHTML,/<a /);
 assert.equal(app.element('familiar').value,'unavailable');
 app.buttons[4].onclick();app=load();
 let saved=await exported(app);assert.equal(saved.answers['2'].level,5);
 assert.equal(saved.answers['2'].selected_context_id,'unavailable');
 assert.equal(saved.answers['2'].first_level,5);
 assert.equal(storage.get(legacy),'original evaluation');
 assert.ok(storage.has(key));assert.equal(saved.ai_exposure,false);
 assert.equal(downloads.at(-1).filename,'revizuire-risc-progres.json');
 app.element('unsure').onclick();saved=await exported(app);
 assert.equal(saved.answers['2'].level,null);assert.equal(saved.answers['2'].decision,'unsure');
 app.element('export-csv').onclick();assert.equal(downloads.at(-1).filename,'revizuire-risc-evaluare.csv');
 assert.match(await downloads.at(-1).blob.text(),/unavailable/);
 // Simultaneous tabs and corrupt storage preserve all old answers.
 storage.set(key,'{corrupt');app=load();app.buttons[0].onclick();
 assert.equal(storage.get(key),'{corrupt');assert.equal((await exported(app)).preserved_raw,'{corrupt');
 assert.equal(storage.get(legacy),'original evaluation');
 console.log('PASS: risk cards show missingness/POS/restrictions; score, uncertainty, reload, exports and namespace isolation');
})().catch(e=>{console.error(e);process.exitCode=1;});
