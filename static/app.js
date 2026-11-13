let state = null;
let activeJob = null;
const $ = id => document.getElementById(id);
const clean = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const names = {aarav:'Aarav', meera:'Meera', kabir:'Kabir'};
const fmt = sec => `${Math.floor(sec / 60)}m ${String(Math.floor(sec % 60)).padStart(2,'0')}s`;
const notify = text => { $('notification').textContent = text; window.scrollTo({top:0, behavior:'smooth'}); };
async function api(path, options = {}) {
  const result = await fetch(path, options);
  const body = await result.json().catch(() => ({}));
  if (!result.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${result.status}`);
  return body;
}
function collect() {
  return {title: $('title').value.trim(), lines: Array.from($('dialogues').querySelectorAll('.dialogue')).map(row => ({
    id: row.dataset.id, speaker: row.querySelector('select').value, text: row.querySelector('textarea').value.trim()
  }))};
}
async function save() {
  const saved = await api('/api/project', {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify(collect())});
  notify('Project saved successfully.'); await load(); return saved;
}
function showTab(tab) {
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.tab').forEach(s => s.classList.toggle('active', s.id === 'tab-' + tab));
}
function lineNode(line, index) {
  const element = document.createElement('article');
  element.className = 'dialogue'; element.dataset.id = line.id;
  element.innerHTML = `<span class="num">${index+1}</span><select aria-label="Speaker for turn ${index+1}">${Object.keys(names).map(k => `<option value="${k}" ${line.speaker===k?'selected':''}>${clean(names[k])}</option>`).join('')}</select><textarea aria-label="Dialogue ${index+1}" maxlength="2000" rows="2">${clean(line.text)}</textarea><button title="Remove turn" class="icon-btn" type="button">✕</button>`;
  element.querySelector('.icon-btn').addEventListener('click', () => { element.remove(); reindex(); });
  return element;
}
function reindex() {document.querySelectorAll('.dialogue .num').forEach((n,i)=>n.textContent=i+1);}
function renderScript() {
  $('title').value = state.title;
  $('dialogues').replaceChildren(...state.lines.map(lineNode));
  $('lineCount').textContent = state.lines.length;
}
function renderCast() {
  $('castGrid').innerHTML = Object.entries(state.speakers).map(([key, sp]) => `<div class="cast-card"><div class="portrait">${sp.has_portrait ? `<img src="${sp.portrait_url}?t=${Date.now()}" alt="Portrait of ${clean(sp.name)}"/>` : `<div class="avatar-placeholder">◉</div>`}</div><div class="cast-body"><strong>${clean(sp.name)}</strong><small>${clean(sp.role)} · ${clean(sp.voice)}</small><input type="file" accept="image/png,image/jpeg,image/webp" aria-label="Upload ${clean(sp.name)} portrait" data-speaker="${key}"/></div></div>`).join('');
  $('castGrid').querySelectorAll('input[type=file]').forEach(element => element.addEventListener('change', async e => {
    const file = e.target.files[0]; if (!file) return;
    const form = new FormData(); form.append('file', file);
    try { await api(`/api/portrait/${element.dataset.speaker}`, {method:'POST', body:form}); notify('Portrait uploaded successfully.'); await load(); }
    catch(err) {notify(`Portrait upload failed: ${err.message}`);}
  }));
}
function renderVoices() {
  $('voiceRows').innerHTML = state.lines.map((line, i) => `<div class="voice-row"><b>${i+1}</b><b>${names[line.speaker]}</b><span class="snippet">${clean(line.text)}</span><small>${line.duration ? fmt(line.duration) : 'No audio yet'}</small>${line.audio_url ? `<audio controls preload="none" src="${line.audio_url}"></audio>` : ''}<input type="file" data-line="${clean(line.id)}" accept="audio/mp3,audio/mpeg,audio/wav,audio/x-wav,audio/mp4,audio/x-m4a" aria-label="Upload audio for dialogue ${i+1}"/></div>`).join('');
  $('voiceRows').querySelectorAll('input[type=file]').forEach(element => element.addEventListener('change', async e => {
    const file = e.target.files[0]; if (!file) return;
    try {const form = new FormData(); form.append('file', file); await api(`/api/audio/${element.dataset.line}`, {method:'POST',body:form});notify('Dialogue audio uploaded.');await load();}
    catch(err){notify(`Audio upload failed: ${err.message}`);}
  }));
}
function showStatus() {
  $('voiceCount').textContent = `${state.ready_audio} / ${state.lines.length}`;
  $('duration').textContent = fmt(state.duration_seconds);
  $('aiStatus').textContent = state.ai_ready ? 'Installed' : 'Not installed';
}
async function load() {
  state = await api('/api/project');
  renderScript(); renderCast(); renderVoices(); showStatus();
  if (state.current_job) watchJob(state.current_job.id);
}
let pollTimer = null;
async function watchJob(id) {
  if (pollTimer) clearInterval(pollTimer);
  activeJob = id;
  const update = async () => {
    let job;
    try { job = await api('/api/job/' + id); }
    catch(err) {notify('Job status error: '+err.message); clearInterval(pollTimer); return;}
    $('job').hidden = false;
    $('jobLabel').textContent = job.label;
    $('jobPercent').textContent = `${job.progress || 0}%`;
    $('bar').style.width = `${job.progress || 0}%`;
    $('jobMessage').textContent = job.message || '';
    for(const button of ['render','generateVoices','saveScript','saveTop','addLine']) $(button).disabled = ['queued','running'].includes(job.state);
    if (job.state === 'error' || job.state === 'done') {
      clearInterval(pollTimer); pollTimer = null; activeJob = null;
      if (job.state === 'error') notify(`Job failed: ${job.message}\nCheck terminal output for details.`);
      if (job.state === 'done') {
        if (job.result?.video_url) {
          $('result').innerHTML = `<h3>Video complete</h3><video controls preload="metadata" src="${job.result.video_url}"></video><p><a href="${job.result.video_url}" download="${clean(job.result.filename)}">⬇ Download MP4 (${job.result.size_mb} MB)</a></p>`;
          showTab('produce');
        } else notify('Voices generated successfully.');
      }
      await load();
    }
  };
  await update();
  if(activeJob) pollTimer = setInterval(update, 1200);
}
async function runJob(endpoint, options) {
  try {const job = await api(endpoint,options);showTab(endpoint.includes('render')?'produce':'voices');await watchJob(job.id);}
  catch(err){notify(err.message);}
}
document.addEventListener('DOMContentLoaded', async () => {
  document.querySelectorAll('.tabs button').forEach(button=>button.addEventListener('click',()=>showTab(button.dataset.tab)));
  $('saveTop').addEventListener('click',()=>save().catch(e=>notify(e.message)));
  $('saveScript').addEventListener('click',()=>save().catch(e=>notify(e.message)));
  $('refresh').addEventListener('click',()=>load().catch(e=>notify(e.message)));
  $('addLine').addEventListener('click',()=>{
    if ($('dialogues').children.length >= 100){notify('Maximum 100 turns supported.');return;}
    const id = 'turn-'+crypto.randomUUID().slice(0,12);
    const child = lineNode({id,speaker:'aarav',text:''},$('dialogues').children.length);
    $('dialogues').append(child); child.querySelector('textarea').focus();
  });
  $('generateVoices').addEventListener('click',()=>runJob('/api/voices',{method:'POST'}));
  $('render').addEventListener('click',()=>runJob('/api/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:document.querySelector('[name=mode]:checked').value})}));
  try {await load();}catch(err){notify('Cannot connect to local backend: '+err.message);}
});
