let pollTimer = null;

async function loadMcpServers(){
  const sel = document.getElementById('job-mcp');
  const r = await fetch('/api/mcp-servers');
  const data = await r.json();
  if(!data.length){
    sel.innerHTML = `<option value="local-mock">local-mock (built-in)</option>`;
    return;
  }
  sel.innerHTML = data.map(s=>`<option value="${s.url}">${s.name} — ${s.url}</option>`).join('');
}

async function loadJobs(){
  const r = await fetch('/api/jobs');
  const jobs = await r.json();
  const list = document.getElementById('jobs-list');
  const empty = document.getElementById('jobs-empty');
  if(!jobs.length){ list.innerHTML=''; empty.classList.remove('hidden'); return;}
  empty.classList.add('hidden');
  list.innerHTML = jobs.map(j=>{
    const badge = {
      queued: 'bg-stone-100 text-stone-700',
      running: 'bg-amber-100 text-amber-800 animate-pulse',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800'
    }[j.status] || 'bg-stone-100';
    return `<div class="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm">
      <div class="flex items-start justify-between gap-4">
        <div class="flex-1">
          <div class="flex items-center gap-2">
            <div class="font-medium">${j.title}</div>
            <span class="text-[11px] px-2 py-0.5 rounded-full ${badge}">${j.status}</span>
          </div>
          <div class="text-sm text-stone-600 mt-1">${j.description||j.prompt.substring(0,120)}</div>
          <div class="text-xs text-stone-400 mt-2">MCP: ${j.mcp_server||'default'} • ${new Date(j.created_at).toLocaleString('ru-RU')}</div>
        </div>
        <div class="flex gap-2">
          <button onclick="refreshJob(${j.id})" class="text-xs px-3 py-1.5 border rounded-lg hover:bg-stone-50">Обновить</button>
          <button onclick="deleteJob(${j.id})" class="text-xs px-3 py-1.5 border rounded-lg hover:bg-red-50 text-red-600">Удалить</button>
        </div>
      </div>
      ${j.result ? `<pre class="mt-3 bg-stone-950 text-stone-100 text-xs rounded-xl p-3 overflow-auto max-h-64">${escapeHtml(j.result)}</pre>`:''}
    </div>`;
  }).join('');
}

function escapeHtml(s){return (s||'').replace(/[&<>"']/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}

async function refreshJob(id){
  const r = await fetch(`/api/jobs/${id}/status`);
  await loadJobs();
}
async function deleteJob(id){
  if(!confirm('Удалить задачу?')) return;
  await fetch(`/api/jobs/${id}`, {method:'DELETE'});
  loadJobs();
}

document.addEventListener('DOMContentLoaded', ()=>{
  loadJobs();
  loadMcpServers();
  pollTimer = setInterval(loadJobs, 4000);
  document.getElementById('new-job-btn').onclick = ()=> document.getElementById('job-modal').classList.remove('hidden');
  document.getElementById('job-cancel').onclick = ()=> document.getElementById('job-modal').classList.add('hidden');
  document.getElementById('job-create').onclick = async ()=>{
    const title = document.getElementById('job-title').value.trim() || 'Claude Code Job';
    const mcp_server = document.getElementById('job-mcp').value;
    const prompt = document.getElementById('job-prompt').value.trim();
    const description = document.getElementById('job-desc').value.trim();
    if(!prompt) return alert('Введите промпт');
    await fetch('/api/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title,mcp_server,prompt,description})});
    document.getElementById('job-modal').classList.add('hidden');
    document.getElementById('job-title').value=''; document.getElementById('job-prompt').value=''; document.getElementById('job-desc').value='';
    loadJobs();
  };
});

window.refreshJob = refreshJob;
window.deleteJob = deleteJob;
