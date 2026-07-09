let editingProjectId = null;

async function loadProjects(){
  const r = await fetch('/api/projects');
  const data = await r.json();
  const grid = document.getElementById('projects-grid');
  const empty = document.getElementById('projects-empty');
  if(!data.length){ grid.innerHTML=''; empty.classList.remove('hidden'); return; }
  empty.classList.add('hidden');
  grid.innerHTML = data.map(p=>`
    <div class="bg-white rounded-2xl border border-stone-200 p-5 shadow-sm hover:shadow-md transition">
      <div class="flex items-start justify-between">
        <div class="w-10 h-10 rounded-xl bg-amber-50 text-amber-700 flex items-center justify-center">📁</div>
        <div class="flex gap-1">
          <button onclick="editProject(${p.id}, '${p.name.replace(/'/g,"\\'")}', \`${(p.description||'').replace(/`/g,'\\`')}\`)" class="text-stone-400 hover:text-stone-700 text-xs">✏️</button>
          <button onclick="delProject(${p.id})" class="text-stone-400 hover:text-red-600 text-xs">🗑️</button>
        </div>
      </div>
      <div class="mt-3 font-medium text-stone-900">${p.name}</div>
      <div class="text-sm text-stone-500 mt-1 min-h-[40px]">${p.description||'Без описания'}</div>
      <div class="text-xs text-stone-400 mt-3">${p.conversations_count} чатов • ${new Date(p.created_at).toLocaleDateString('ru-RU')}</div>
    </div>
  `).join('');
}

function openModal(edit=false){
  document.getElementById('project-modal').classList.remove('hidden');
  document.getElementById('project-modal-title').textContent = edit ? 'Редактировать проект' : 'Новый проект';
}
function closeModal(){
  document.getElementById('project-modal').classList.add('hidden');
  editingProjectId = null;
  document.getElementById('project-name').value='';
  document.getElementById('project-desc').value='';
}

function editProject(id, name, desc){
  editingProjectId = id;
  document.getElementById('project-name').value = name;
  document.getElementById('project-desc').value = desc;
  openModal(true);
}

async function delProject(id){
  if(!confirm('Удалить проект?')) return;
  await fetch(`/api/projects/${id}`, {method:'DELETE'});
  loadProjects();
}

document.addEventListener('DOMContentLoaded', ()=>{
  loadProjects();
  document.getElementById('new-project-btn').onclick = ()=> openModal(false);
  document.getElementById('project-cancel').onclick = closeModal;
  document.getElementById('project-save').onclick = async ()=>{
    const name = document.getElementById('project-name').value.trim();
    const description = document.getElementById('project-desc').value.trim();
    if(!name) return alert('Введите название');
    if(editingProjectId){
      await fetch(`/api/projects/${editingProjectId}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name, description})});
    } else {
      await fetch('/api/projects', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name, description})});
    }
    closeModal();
    loadProjects();
  };
});

window.editProject = editProject;
window.delProject = delProject;
