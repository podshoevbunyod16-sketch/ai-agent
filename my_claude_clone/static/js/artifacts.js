async function loadArtifacts(){
  const r = await fetch('/api/artifacts');
  const data = await r.json();
  const list = document.getElementById('artifacts-list');
  const empty = document.getElementById('artifacts-empty');
  if(!data.length){ list.innerHTML=''; empty.classList.remove('hidden'); return;}
  empty.classList.add('hidden');
  list.innerHTML = data.map(a=>`
    <div class="bg-white rounded-2xl border border-stone-200 p-4 shadow-sm flex items-start gap-4 hover:shadow-md transition cursor-pointer" onclick='showArt(${JSON.stringify(a).replace(/'/g,"&#39;")})'>
      <div class="text-xs px-2 py-1 rounded-lg bg-stone-100 text-stone-700 font-mono">${a.language}</div>
      <div class="flex-1 min-w-0">
        <div class="font-medium text-stone-900">${a.title}</div>
        <div class="text-sm text-stone-500 truncate mt-1">${(a.content||'').substring(0,120).replace(/\n/g,' ')}...</div>
        <div class="text-xs text-stone-400 mt-2">${new Date(a.created_at).toLocaleString('ru-RU')} • чат #${a.conversation_id||'?'}</div>
      </div>
      <button class="text-xs px-3 py-1.5 rounded-lg border hover:bg-stone-50" onclick="event.stopPropagation(); navigator.clipboard.writeText(document.getElementById('art-${a.id}')?.textContent||'')">Копировать</button>
      <pre id="art-${a.id}" class="hidden">${a.content.replace(/</g,'&lt;')}</pre>
    </div>
  `).join('');
}

function showArt(a){
  if(typeof openArtifact==='function') openArtifact(a);
  else alert(a.content.substring(0,500));
}

document.addEventListener('DOMContentLoaded', loadArtifacts);
window.showArt = showArt;
