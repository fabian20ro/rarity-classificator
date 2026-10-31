'use strict';
const $=id=>document.getElementById(id);
const data=JSON.parse($('case-data').textContent),forms=data.forms,riskMode=data.mode==='risk',key=(riskMode?'romanian-risk-':'romanian-')+data.version;
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const level=n=>Number.isInteger(n)&&n>=1&&n<=5;
const validContext=(f,id)=>id===''||id==='other'||(riskMode&&f.contexts.length===0&&id==='unavailable')||f.contexts.some(c=>c.context_id===id);
let state={version:data.version,pack_sha256:data.pack_sha256,index:0,answers:{},events:[]};
let blocked=false,preservedRaw=null,lastRaw=null;
function valid(s){
 if(!s||s.version!==data.version||s.pack_sha256!==data.pack_sha256||!Number.isInteger(s.index)||s.index<0||s.index>=forms.length||!s.answers||Array.isArray(s.answers)||!Array.isArray(s.events))return false;
 return Object.entries(s.answers).every(([id,a])=>{const f=forms.find(f=>f.word_id===id);
  return f&&a&&['pending','rated','unsure'].includes(a.decision)&&typeof a.notes==='string'&&validContext(f,a.selected_context_id)&&
   (a.first_level===null||level(a.first_level))&&(a.decision==='rated'?level(a.level)&&a.selected_context_id&&(a.selected_context_id!=='other'||a.notes.trim()):a.level===null);
 })&&s.events.every(e=>e&&forms.some(f=>f.word_id===e.word_id)&&typeof e.at==='string'&&['rate','context','notes','unsure'].includes(e.kind));
}
try{lastRaw=localStorage.getItem(key);if(lastRaw!==null){const saved=JSON.parse(lastRaw);if(!valid(saved))throw Error('Invalid state');state=saved;}}
catch(error){blocked=true;preservedRaw=lastRaw;}
const item=()=>forms[state.index];
function answer(){const f=item();return state.answers[f.word_id]??={decision:'pending',level:null,first_level:null,first_context_id:null,selected_context_id:f.contexts.length===1?f.contexts[0].context_id:riskMode&&f.contexts.length===0?'unavailable':'',notes:''};}
function event(kind,extra={}){state.events.push({kind,word_id:item().word_id,at:new Date().toISOString(),...extra});}
function save(){
 if(blocked){$('save-status').textContent='Progresul existent este păstrat intact. Nu îl pot suprascrie; salvează JSON pentru recuperare.';return;}
 try{
  const current=localStorage.getItem(key);
  if(current!==lastRaw){blocked=true;preservedRaw=current;$('save-status').textContent='Progres modificat în altă filă; păstrat intact. Salvează JSON și reîncarcă pagina.';return;}
  const raw=JSON.stringify(state);localStorage.setItem(key,raw);lastRaw=raw;
  $('save-status').textContent='Salvat în acest browser. La final: exportă CSV și JSON.';
 }catch(error){$('save-status').textContent='Salvarea în browser nu este disponibilă. Salvează JSON înainte de închidere.';}
}
function render(){
 const f=item(),a=answer(),rated=forms.filter(f=>state.answers[f.word_id]?.decision==='rated').length;
 const unsure=forms.filter(f=>state.answers[f.word_id]?.decision==='unsure').length;
 $('word').textContent=f.word;$('position').textContent=`Forma ${state.index+1}/${forms.length}`;
 $('progress').max=forms.length;$('progress').value=rated;
 $('progress-text').textContent=`${rated}/${forms.length} evaluate · ${unsure} neclare`;
 $('current-status').textContent=a.decision==='rated'?`Scor ${a.level}`:a.decision==='unsure'?'Fără scor · neclar':'De evaluat';
 $('contexts').innerHTML=(riskMode?`<p class="example">Părți de vorbire valide: ${f.valid_pos.map(esc).join(' · ')}</p>`:'')+
  f.contexts.map(c=>`<section class="context"><small>${esc(c.pos)}</small><p>${esc(c.meaning)}</p>${riskMode?(c.restrictions.length?`<p class="example">${c.restrictions.map(esc).join(' · ')}</p>`:''):`<p class="example">${esc(c.example)}</p>`}<a href="${esc(c.source)}" target="_blank" rel="noreferrer">Sursa sensului ↗</a></section>`).join('')+
  (riskMode?(f.contexts.length?'<p class="example">Sensuri documentate în sursele disponibile; lista poate fi incompletă.</p>':'<p class="context">Nu avem un sens verificat pentru această grafie. Lipsa definiției nu înseamnă raritate. Notează numai dacă recunoști forma; altfel alege „Nu pot decide”.</p>'):'');
 $('familiar').innerHTML='<option value="">Alege sensul…</option>'+f.contexts.map(c=>`<option value="${esc(c.context_id)}">${esc(c.meaning)}</option>`).join('')+(riskMode&&f.contexts.length===0?'<option value="unavailable">Recunosc forma; sens nespecificat în surse</option>':'')+'<option value="other">Alt sens — descrie-l mai jos</option>';
 $('familiar').value=a.selected_context_id;$('notes').value=a.notes;
 $('jump').innerHTML=forms.map((f,i)=>`<option value="${i}">${i+1}. ${esc(f.word)}${state.answers[f.word_id]?.decision==='rated'?' ✓':state.answers[f.word_id]?.decision==='unsure'?' ?':''}</option>`).join('');
 $('jump').value=String(state.index);
 document.querySelectorAll('[data-level]').forEach(button=>{button.setAttribute('aria-pressed',String(a.decision==='rated'&&a.level===Number(button.dataset.level)));button.disabled=blocked;});
 $('familiar').disabled=blocked;$('notes').disabled=blocked;$('unsure').disabled=blocked;
 $('previous').disabled=state.index===0;$('next').disabled=state.index===forms.length-1;
 if(blocked)save();
 else if(rated+unsure===forms.length)$('save-status').textContent='Runda este parcursă. Exportă CSV și JSON; cazurile neclare rămân fără scor.';
}
function go(index){state.index=Math.max(0,Math.min(forms.length-1,index));$('alert').textContent='';render();save();}
document.querySelectorAll('[data-level]').forEach(button=>button.onclick=()=>{
 if(blocked)return;
 const a=answer();
 if(!a.selected_context_id){$('alert').textContent='Alege sensul cel mai familiar înainte de scor.';return;}
 if(a.selected_context_id==='other'&&!a.notes.trim()){$('alert').textContent='Descrie sensul în observații înainte de scor.';return;}
 a.level=Number(button.dataset.level);a.decision='rated';a.updated_at=new Date().toISOString();
 if(a.first_level===null){a.first_level=a.level;a.first_context_id=a.selected_context_id;}
 event('rate',{level:a.level,selected_context_id:a.selected_context_id,notes:a.notes});$('alert').textContent='';save();render();
});
$('familiar').onchange=()=>{if(blocked)return;const a=answer();const selected=$('familiar').value;if(!validContext(item(),selected))return;
 a.selected_context_id=selected;a.decision='pending';a.level=null;event('context',{selected_context_id:selected});save();render();
 $('alert').textContent='Sens schimbat. Alege scorul pentru forma privită prin acest sens.';};
$('notes').oninput=()=>{if(blocked)return;const a=answer();a.notes=$('notes').value;
 const invalidated=a.decision==='rated'&&a.selected_context_id==='other'&&!a.notes.trim();
 if(invalidated){a.decision='pending';a.level=null;}
 event('notes',{notes:a.notes});save();if(invalidated)render();};
$('unsure').onclick=()=>{if(blocked)return;const a=answer();a.decision='unsure';a.level=null;event('unsure',{selected_context_id:a.selected_context_id});save();render();};
$('previous').onclick=()=>go(state.index-1);$('next').onclick=()=>go(state.index+1);
$('jump').onchange=()=>go(Number($('jump').value));
$('next-unrated').onclick=()=>{
 for(let offset=1;offset<=forms.length;offset++){const index=(state.index+offset)%forms.length;
  if(!['rated','unsure'].includes(state.answers[forms[index].word_id]?.decision)){go(index);return;}}
 $('alert').textContent='Toate fișele au fost parcurse. Poți revizui cazurile neclare sau exporta răspunsurile.';
};
function download(filename,mime,text){const link=document.createElement('a'),url=URL.createObjectURL(new Blob([text],{type:mime}));link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('export-json').onclick=()=>download(riskMode?'revizuire-risc-progres.json':'lot-independent-progres.json','application/json',JSON.stringify({...state,case_pack:data,ai_exposure:false,preserved_raw:preservedRaw,exported_at:new Date().toISOString()},null,2));
$('export-csv').onclick=()=>{
 const fields=['version','pack_sha256','word_id','word','decision','level','selected_context_id','first_level','first_context_id','notes','ai_exposure'];
 const rows=forms.map(f=>({version:data.version,pack_sha256:data.pack_sha256,word_id:f.word_id,word:f.word,decision:'pending',...state.answers[f.word_id],ai_exposure:false}));
 const cell=v=>'"'+String(v??'').replace(/"/g,'""')+'"';
 download(riskMode?'revizuire-risc-evaluare.csv':'lot-independent-evaluare.csv','text/csv;charset=utf-8','\ufeff'+[fields,...rows.map(r=>fields.map(k=>r[k]))].map(r=>r.map(cell).join(',')).join('\r\n')+'\r\n');
};
render();
