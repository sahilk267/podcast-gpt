/* Browser-only frontend, no build pipeline or API key required. */
let state=null,activeJob=null,pollTimer=null;
const $=id=>document.getElementById(id);
const clean=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const names={aarav:'Aarav',meera:'Meera',kabir:'Kabir'};
const voiceOptions=[['hi-IN-MadhurNeural','Hindi • Madhur (Male)'],['hi-IN-SwaraNeural','Hindi • Swara (Female)'],['en-IN-PrabhatNeural','English India • Prabhat (Male)'],['en-IN-NeerjaNeural','English India • Neerja (Female)']];
const fmt=sec=>`${Math.floor(Math.max(0,sec)/60)}m ${String(Math.floor(Math.max(0,sec)%60)).padStart(2,'0')}s`;
const notify=message=>{$('notification').textContent=message;window.scrollTo({top:0,behavior:'smooth'});};
async function api(path,options={}){const r=await fetch(path,options);const body=await r.json().catch(()=>({}));if(!r.ok)throw new Error(typeof body.detail==='string'?body.detail:`HTTP ${r.status}`);return body;}
const jsonOptions=(body)=>({method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
function lineNode(line,index){
  const el=document.createElement('article');el.className='dialogue';el.dataset.id=line.id;
  const opts=Object.keys(names).map(k=>`<option value="${k}" ${line.speaker===k?'selected':''}>${names[k]}</option>`).join('');
  el.innerHTML=`<span class="num">${index+1}</span><select aria-label="Speaker ${index+1}">${opts}</select><textarea maxlength="2200" rows="3" aria-label="Dialogue ${index+1}">${clean(line.text)}</textarea><label class="small-option">Shot<select class="shot"><option value="wide" ${line.shot==='wide'?'selected':''}>Wide</option><option value="focus" ${line.shot==='focus'?'selected':''}>Focus</option></select></label><label class="small-option">Pause (sec)<input class="pause" type="number" min="0" max="5" step="0.1" value="${Number(line.pause_after||0)}"/></label><button class="icon-btn" title="Remove turn">✕</button>`;
  el.querySelector('.icon-btn').addEventListener('click',()=>{el.remove();reindex();});return el;
}
function reindex(){document.querySelectorAll('.dialogue .num').forEach((n,i)=>n.textContent=i+1);$('lineCount').textContent=$('dialogues').children.length;}
function collect(){
 const speakers={};for(const key of Object.keys(names)){
  const card=$(`speaker-${key}`);
  speakers[key]={name:card.querySelector('.sp-name').value.trim(),role:card.querySelector('.sp-role').value.trim(),voice:card.querySelector('.sp-voice').value,rate:card.querySelector('.sp-rate').value.trim(),pitch:card.querySelector('.sp-pitch').value.trim()};
 }
 return {title:$('title').value.trim(),topic:$('topic').value.trim(),target_minutes:Number($('target').value),speakers,
 lines:Array.from($('dialogues').querySelectorAll('.dialogue')).map(row=>({id:row.dataset.id,speaker:row.querySelector('select').value,text:row.querySelector('textarea').value.trim(),shot:row.querySelector('.shot').value,pause_after:Number(row.querySelector('.pause').value)}))};
}
async function save(){const saved=await api('/api/project',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(collect())});notify('Episode saved.');await load();return saved;}
function showTab(tab){document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));document.querySelectorAll('.tab').forEach(s=>s.classList.toggle('active',s.id===`tab-${tab}`));}
function renderScript(){
 $('title').value=state.title;$('topic').value=state.topic;$('target').value=state.target_minutes;
 $('dialogues').replaceChildren(...state.lines.map(lineNode));reindex();
}
function renderCast(){
 $('castGrid').innerHTML=Object.entries(state.speakers).map(([key,sp])=>{
   const options=voiceOptions.map(([id,label])=>`<option value="${id}" ${id===sp.voice?'selected':''}>${clean(label)}</option>`).join('');
   return `<article class="cast-card" id="speaker-${key}"><div class="portrait">${sp.has_portrait?`<img src="${sp.portrait_url}?v=${Date.now()}" alt="${clean(sp.name)}"/>`:`<div class="avatar-placeholder">◉</div>`}</div><div class="cast-body"><strong>${clean(sp.name)}</strong><label>Name<input class="sp-name" maxlength="45" value="${clean(sp.name)}"/></label><label>Role<input class="sp-role" maxlength="60" value="${clean(sp.role)}"/></label><label>TTS voice<select class="sp-voice">${options}</select></label><div class="small-inputs"><label>Speed<input class="sp-rate" value="${clean(sp.rate)}" placeholder="+0%"/></label><label>Pitch<input class="sp-pitch" value="${clean(sp.pitch)}" placeholder="+0Hz"/></label></div><label>Portrait image<input type="file" accept="image/png,image/jpeg,image/webp" data-speaker="${key}"/></label></div></article>`;
 }).join('');
 $('castGrid').querySelectorAll('input[type=file]').forEach(el=>el.addEventListener('change',async e=>{
  const f=e.target.files[0];if(!f)return;const data=new FormData();data.append('file',f);
  try{await api(`/api/portrait/${el.dataset.speaker}`,{method:'POST',body:data});notify('Portrait uploaded.');await load();}
  catch(err){notify('Portrait upload failed: '+err.message);}
 }));
}
function renderVoices(){
 $('voiceRows').innerHTML=state.lines.map((line,i)=>`<div class="voice-row"><b>${i+1}</b><b>${clean(state.speakers[line.speaker].name)}</b><span class="snippet">${clean(line.text)}</span><small>${line.duration!=null?fmt(line.duration):'Missing'} · ${line.audio_origin||'missing'}</small>${line.audio_url?`<audio controls preload="none" src="${clean(line.audio_url)}"></audio>`:''}<div class="voice-controls"><input type="file" data-line="${clean(line.id)}" accept=".wav,.mp3,.m4a" aria-label="Audio for dialogue ${i+1}"/><button class="ghost mini" data-generate="${clean(line.id)}">Generate</button><button class="ghost mini" data-reset="${clean(line.id)}">Reset</button></div></div>`).join('');
 $('voiceRows').querySelectorAll('input[type=file]').forEach(el=>el.addEventListener('change',async e=>{
  const f=e.target.files[0];if(!f)return;const data=new FormData();data.append('file',f);
  try{await api(`/api/audio/${el.dataset.line}`,{method:'POST',body:data});notify('Audio uploaded; cached as custom recording.');await load();}
  catch(err){notify('Audio upload failed: '+err.message);}
 }));
 $('voiceRows').querySelectorAll('[data-reset]').forEach(el=>el.addEventListener('click',async()=>{
  if(!confirm('Remove generated/uploaded audio for this dialogue?'))return;
  try{await api(`/api/audio/${el.dataset.reset}/reset`,{method:'POST'});await load();}
  catch(err){notify(err.message);}
 }));
 $('voiceRows').querySelectorAll('[data-generate]').forEach(el=>el.addEventListener('click',async()=>{
  try{await save();await runJob(`/api/voices/line/${el.dataset.generate}`,{method:'POST'});}catch(err){notify(err.message);}
 }));
}
async function renderProjects(){const listing=await api('/api/projects');$('projectSelect').innerHTML=listing.projects.map(p=>`<option value="${clean(p.id)}" ${p.id===listing.active_id?'selected':''}>${clean(p.title)}</option>`).join('');}
function showStatus(){
 $('voiceCount').textContent=`${state.ready_audio} / ${state.lines.length}`;
 $('duration').textContent=fmt(state.duration_seconds);
 $('delta').textContent=(state.target_seconds>=state.duration_seconds?'+':'−')+fmt(Math.abs(state.target_seconds-state.duration_seconds));
 $('aiStatus').value=state.ai_ready?'Detected, not tested':'Not installed';
}
async function load(){state=await api('/api/project');await renderProjects();renderScript();renderCast();renderVoices();showStatus();if(state.current_job)await watchJob(state.current_job.id);if(state.last_export){$('result').innerHTML=`<p>Last export:</p><video controls src="${state.last_export}" preload="metadata"></video><p><a href="${state.last_export}" download>Download last MP4</a></p>`;}}
async function watchJob(id){
 if(pollTimer)clearInterval(pollTimer);activeJob=id;
 const update=async()=>{
  let j;try{j=await api('/api/job/'+id);}catch(err){notify(err.message);clearInterval(pollTimer);activeJob=null;return;}
  $('job').hidden=false;$('jobLabel').textContent=j.label;$('jobPercent').textContent=`${j.progress||0}%`;$('bar').style.width=`${j.progress||0}%`;$('jobMessage').textContent=j.message||'';
  const busy=['queued','running','cancelling'].includes(j.state);
  for(const b of ['render','generateVoices','saveTop','saveScript','addLine','createProject'])$(b).disabled=busy;
  $('cancelJob').disabled=!busy;$('projectSelect').disabled=busy;
  if(!busy){clearInterval(pollTimer);pollTimer=null;activeJob=null;
   if(j.state==='error')notify('Job error: '+j.message+'\nSee terminal output. Completed video clips remain cached.');
   else if(j.state==='done'){
    if(j.result?.video_url){$('result').innerHTML=`<h3>Video complete</h3><video controls preload="metadata" src="${clean(j.result.video_url)}"></video><p><a href="${clean(j.result.video_url)}" download="${clean(j.result.filename)}">Download MP4</a> · <a href="${clean(j.result.subtitle_url)}" download>Download SRT subtitles</a></p><p>Duration: ${fmt(j.result.duration_seconds)}</p>`;showTab('produce');}
    else notify('Audio generated.');
   }else if(j.state==='cancelled')notify('Job stopped. Start render again to use cached dialogue clips.');
   await load();
  }
 };
 await update();if(activeJob)pollTimer=setInterval(update,1400);
}
async function runJob(path,options){try{const job=await api(path,options);showTab(path.includes('render')?'produce':'voices');await watchJob(job.id);}catch(err){notify(err.message);}}
function scriptPrompt(){
 const p=collect();return `Write a complete educational, fact-checked Hindi/Hinglish 3-person Q&A podcast script about: ${p.topic||p.title}. Target: ${p.target_minutes} minutes. Host Aarav asks thoughtful questions, guest Kabir asks common doubts, educator Meera gives carefully sourced explanations; all three are fictional AI characters. Include natural follow-ups, coherent flow, original wording, respectful discussion, and a disclosure about AI actors. Approximate total spoken words to match requested duration. Each dialogue on its own line in this exact format: Aarav: ... OR Meera: ... OR Kabir: ... . No headings or stage directions inside a speaker's spoken text. No false medical credentials; never invent facts.`;
}
function importDialogue(raw){
 const rows=raw.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);const result=[];
 for(const row of rows){const match=row.match(/^(aarav|meera|kabir)\s*[:：-]\s*(.+)$/i);if(!match)throw Error('Every nonblank line must start Aarav:, Meera: or Kabir:');result.push({id:'turn-'+String(result.length+1).padStart(3,'0'),speaker:match[1].toLowerCase(),text:match[2],shot:result.length%3===0?'wide':'focus',pause_after:0.2});}
 if(!result.length||result.length>200)throw Error('Import between 1 and 200 dialogue turns.');return result;
}
document.addEventListener('DOMContentLoaded',async()=>{
 document.querySelectorAll('.tabs button').forEach(b=>b.addEventListener('click',()=>showTab(b.dataset.tab)));
 $('saveTop').addEventListener('click',()=>save().catch(e=>notify(e.message)));$('saveScript').addEventListener('click',()=>save().catch(e=>notify(e.message)));
 $('refresh').addEventListener('click',()=>{if(confirm('Reload saved episode and discard unsaved edits?'))load().catch(e=>notify(e.message));});
 $('newProject').addEventListener('click',()=>{$('newProjectForm').hidden=!$('newProjectForm').hidden;});
 $('createProject').addEventListener('click',async()=>{try{await api('/api/projects',jsonOptions({title:$('newTitle').value,topic:$('newTopic').value,target_minutes:Number($('newTarget').value)}));$('newProjectForm').hidden=true;await load();showTab('script');notify('New episode created. Build and verify its script before generating speech.');}catch(e){notify(e.message);}});
 $('projectSelect').addEventListener('change',async e=>{if(!confirm('Switch episode? Unsaved changes will be discarded.')){await renderProjects();return;}try{await api('/api/projects/activate/'+e.target.value,{method:'POST'});await load();}catch(err){notify(err.message);}});
 $('addLine').addEventListener('click',()=>{if($('dialogues').children.length>=200){notify('Maximum 200 dialogue turns.');return;}const id='turn-'+crypto.randomUUID().slice(0,12);$('dialogues').append(lineNode({id,speaker:'aarav',text:'',shot:'wide',pause_after:0.2},$('dialogues').children.length));reindex();});
 $('copyPrompt').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(scriptPrompt());notify('Detailed ChatGPT script prompt copied. Paste it into ChatGPT, then import the generated speaker lines.');}catch(err){notify('Cannot access clipboard: '+err.message);}});
 $('toggleImport').addEventListener('click',()=>{$('importBox').hidden=!$('importBox').hidden;});
 $('doImport').addEventListener('click',()=>{if(!confirm('Replace all current dialogue turns with imported text?'))return;try{const result=importDialogue($('importText').value);$('dialogues').replaceChildren(...result.map(lineNode));reindex();$('importBox').hidden=true;notify(`${result.length} dialogue turns imported. Save episode to apply.`);}catch(err){notify(err.message);}});
 $('generateVoices').addEventListener('click',async()=>{try{await save();await runJob('/api/voices',{method:'POST'});}catch(e){notify(e.message);}});
 $('render').addEventListener('click',async()=>{try{await save();await runJob('/api/render',jsonOptions({mode:document.querySelector('[name=mode]:checked').value,quality:$('quality').value}));}catch(e){notify(e.message);}});
 $('cancelJob').addEventListener('click',async()=>{if(activeJob)try{await api(`/api/job/${activeJob}/cancel`,{method:'POST'});notify('Cancellation requested; current dialogue finishes first.');}catch(e){notify(e.message);}});
 try{await load();}catch(e){notify('Cannot start local dashboard: '+e.message);}
});
