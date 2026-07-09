// Sidebar conversations loader
async function loadSidebarConversations(q=''){
  const el = document.getElementById('sidebar-conversations');
  if(!el) return;
  try{
    const res = await fetch('/api/conversations'+(q?`?q=${encodeURIComponent(q)}`:''));
    const data = await res.json();
    if(!data.length){
      el.innerHTML = `<div class="text-stone-400 text-xs px-2">Нет чатов</div>`;
      return;
    }
    el.innerHTML = data.slice(0,20).map(c=>`
      <div class="chat-row group relative">
        <a href="/?c=${c.id}" class="block px-2 py-2 rounded-xl hover:bg-stone-200/70 truncate ${window.ACTIVE_CONVERSATION_ID===c.id?'bg-stone-200/80 font-medium':''}">
          <div class="truncate pr-6">${escapeHtml(c.title)}</div>
          <div class="text-[11px] text-stone-500">${timeAgo(c.updated_at)}</div>
        </a>
        <div class="chat-row-actions absolute right-1 top-1.5 opacity-0 transition flex gap-1">
          <button onclick="toggleFav(${c.id}, ${!c.is_favorite})" title="Избранное" class="p-1 rounded hover:bg-white text-stone-500">${c.is_favorite?'★':'☆'}</button>
          <button onclick="deleteConv(${c.id})" title="Удалить" class="p-1 rounded hover:bg-white text-stone-400">✕</button>
        </div>
      </div>
    `).join('');
  }catch(e){
    el.innerHTML = '<div class="text-red-500 text-xs px-2">Ошибка загрузки</div>';
  }
}

function escapeHtml(s){return (s||'').replace(/[&<>"']/g, m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
function timeAgo(iso){
  const d = new Date(iso); const diff = (Date.now()-d)/1000;
  if(diff<3600) return Math.floor(diff/60)+'m';
  if(diff<86400) return Math.floor(diff/3600)+'h';
  return Math.floor(diff/86400)+'d';
}

async function toggleFav(id, val){
  await fetch(`/api/conversations/${id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({is_favorite:val})});
  loadSidebarConversations(document.getElementById('chat-search')?.value||'');
}
async function deleteConv(id){
  if(!confirm('Удалить чат?')) return;
  await fetch(`/api/conversations/${id}`,{method:'DELETE'});
  loadSidebarConversations();
  if(window.ACTIVE_CONVERSATION_ID===id) window.location='/?';
}

document.addEventListener('DOMContentLoaded', ()=>{
  loadSidebarConversations();
  const search = document.getElementById('chat-search');
  if(search){
    let t; search.addEventListener('input', e=>{ clearTimeout(t); t=setTimeout(()=>loadSidebarConversations(e.target.value), 300)});
  }
  const newBtn = document.getElementById('new-chat-btn');
  if(newBtn){
    newBtn.addEventListener('click', async ()=>{
      const r = await fetch('/api/conversations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:'Новый чат'})});
      const c = await r.json();
      window.location = '/?c='+c.id;
    });
  }
  // user menu
  const umBtn = document.getElementById('user-menu-btn');
  const um = document.getElementById('user-menu');
  if(umBtn){ umBtn.onclick = e=>{ e.stopPropagation(); um.classList.toggle('hidden') }; document.addEventListener('click', ()=>um.classList.add('hidden'))}
  // mobile
  const mobileBtn = document.getElementById('mobile-menu-btn');
  const sidebar = document.getElementById('sidebar');
  if(mobileBtn){ mobileBtn.onclick = ()=> sidebar.classList.toggle('-translate-x-full') }

  // artifact panel close
  document.getElementById('artifact-close')?.addEventListener('click', closeArtifact);
  document.getElementById('artifact-copy')?.addEventListener('click', ()=>{
    const txt = document.getElementById('artifact-content').textContent;
    navigator.clipboard.writeText(txt);
    const btn = document.getElementById('artifact-copy'); const old=btn.textContent; btn.textContent='Скопировано!'; setTimeout(()=>btn.textContent=old, 1200);
  })
});

function openArtifact(art){
  const panel = document.getElementById('artifact-panel');
  document.getElementById('artifact-title').textContent = art.title || 'Артефакт';
  document.getElementById('artifact-lang').textContent = art.language || 'text';
  document.getElementById('artifact-content').textContent = art.content || '';
  panel.classList.remove('hidden'); panel.classList.add('flex');
}
function closeArtifact(){
  const panel = document.getElementById('artifact-panel');
  panel.classList.add('hidden'); panel.classList.remove('flex');
}
window.openArtifact = openArtifact;
