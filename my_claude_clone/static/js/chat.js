// ===========================================
//  chat.js — SSE стриминг + thinking panel + MCP
// ===========================================

let currentConvId = window.ACTIVE_CONVERSATION_ID || null;
let messagesCache = [];

function esc(t){ return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function fmtContent(text){
  let h = esc(text);
  h = h.replace(/```(\w+)?\n([\s\S]*?)```/g, (_,lang,code)=>
    `<pre class="bg-stone-900 text-emerald-300 rounded-xl p-3 my-2 text-xs overflow-x-auto whitespace-pre-wrap">${esc(code)}</pre>`);
  h = h.replace(/`([^`]+)`/g, '<code class="bg-stone-100 px-1 rounded text-sm font-mono">$1</code>');
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/\n/g, '<br>');
  return h;
}

async function ensureConv(){
  if(currentConvId) return currentConvId;
  const r = await fetch('/api/conversations',{method:'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({title:'Новый чат'})});
  const c = await r.json();
  currentConvId = c.id;
  window.ACTIVE_CONVERSATION_ID = c.id;
  history.replaceState(null,'','/?c='+c.id);
  if(typeof loadSidebarConversations==='function') loadSidebarConversations();
  return c.id;
}

function renderMessages(){
  const inner = document.getElementById('messages-inner');
  if(!messagesCache.length){
    inner.innerHTML = `
      <div class="text-center py-16">
        <div class="w-14 h-14 rounded-2xl bg-stone-800 text-white mx-auto flex items-center justify-center text-2xl font-bold mb-4">✶</div>
        <h2 class="text-2xl font-semibold mb-2">Привет${window.USER_NAME?', '+window.USER_NAME:''}!</h2>
        <p class="text-stone-500 mb-8">Чем могу помочь сегодня?</p>
        <div class="grid sm:grid-cols-2 gap-3 max-w-xl mx-auto text-left text-sm">
          ${ ['Напиши Python скрипт для CSV','Создай React компонент','Объясни как работает MCP','Проанализируй https://github.com']
            .map(t=>`<button class="starter px-4 py-3 bg-white border border-stone-200 rounded-2xl hover:border-amber-300" data-prompt="${t}">${t}</button>`).join('') }
        </div>
      </div>`;
    document.querySelectorAll('.starter').forEach(b=>b.onclick=()=>{
      document.getElementById('chat-input').value=b.dataset.prompt; sendMessage();
    });
    return;
  }
  inner.innerHTML = messagesCache.map((m,idx)=>{
    const isUser = m.role==='user';
    let thinkHtml = '';
    if(m.thinking && m.thinking.length){
      thinkHtml = `
        <div class="mt-2">
          <button onclick="toggleThink(this)" class="text-xs text-stone-400 hover:text-stone-600 flex items-center gap-1">
            <svg class="think-arr transition-transform" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
            <span>${m.thinking.length} шагов рассуждения</span>
          </button>
          <div class="think-body hidden mt-2 text-xs text-stone-500 border-l-2 border-amber-200 pl-3 space-y-1">
            ${m.thinking.map(s=>`<div>${esc(s)}</div>`).join('')}
          </div>
        </div>`;
    }
    return `
      <div class="flex ${isUser?'justify-end':''}">
        <div class="max-w-[85%] ${isUser?'bg-amber-50 border border-amber-200':'bg-white border border-stone-200'} rounded-2xl px-4 py-3 shadow-sm">
          <div class="text-[11px] text-stone-400 mb-1">${isUser?'Вы':'Claude'}</div>
          <div class="msg-content text-[15px] leading-relaxed" data-idx="${idx}">${fmtContent(m.content)}</div>
          ${thinkHtml}
          ${m.artifacts&&m.artifacts.length?`<div class="mt-3 flex flex-wrap gap-2">${m.artifacts.map(a=>`<button onclick="loadArtifact(${a.id})" class="text-xs px-2 py-1 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 hover:bg-amber-100">📄 ${esc(a.title||a.language)}</button>`).join('')}</div>`:''}
        </div>
      </div>`;
  }).join('');
  document.getElementById('messages').scrollTop = 9999;
}

function toggleThink(btn){
  const body = btn.parentElement.querySelector('.think-body');
  const arr  = btn.querySelector('.think-arr');
  body.classList.toggle('hidden');
  arr.style.transform = body.classList.contains('hidden') ? '' : 'rotate(180deg)';
}

async function loadMessages(){
  if(!currentConvId){ renderMessages(); return; }
  const r = await fetch(`/api/conversations/${currentConvId}/messages`);
  if(!r.ok) return;
  messagesCache = await r.json();
  renderMessages();
}

async function sendMessage(){
  const input   = document.getElementById('chat-input');
  const content = input.value.trim();
  if(!content) return;

  const sendBtn = document.getElementById('send-btn');
  sendBtn.disabled = true;
  input.value = ''; autoResize();

  const cid       = await ensureConv();
  const extended  = document.getElementById('extended-thinking').checked;
  const webSearch = document.getElementById('web-search-toggle').checked;
  const useMcp    = document.getElementById('mcp-toggle').checked;
  const model     = document.getElementById('model-select').value;

  messagesCache.push({role:'user', content, artifacts:[]});
  const aIdx = messagesCache.length;
  messagesCache.push({role:'assistant', content:'', artifacts:[], thinking:[], _streaming:true});
  renderMessages();

  // Живой элемент для ответа
  const boxes = document.querySelectorAll('.msg-content');
  let liveEl  = boxes[boxes.length - 1];
  if(liveEl) liveEl.innerHTML = '<span class="inline-block w-2 h-4 bg-amber-500 animate-pulse rounded"></span>';

  const thinkLines = [];

  function addThinkStep(step){
    thinkLines.push(step);
    const parent = liveEl?.closest('[class*="rounded-2xl"]');
    if(!parent) return;
    let tp = parent.querySelector('.live-think');
    if(!tp){
      tp = document.createElement('div');
      tp.className = 'live-think mt-2';
      tp.innerHTML = `
        <button onclick="this.nextElementSibling.classList.toggle('hidden'); this.querySelector('span').textContent = this.querySelector('span').textContent == '▼' ? '▶' : '▼'" class="text-xs text-stone-400 flex items-center gap-1">
          <span>▼</span> Процесс рассуждения
        </button>
        <div class="ltb text-xs text-stone-400 border-l-2 border-amber-100 pl-3 mt-1 space-y-0.5"></div>`;
      parent.appendChild(tp);
    }
    const d = document.createElement('div');
    d.textContent = step;
    tp.querySelector('.ltb').appendChild(d);
    document.getElementById('messages').scrollTop = 9999;
  }

  try{
    const resp = await fetch(`/api/conversations/${cid}/messages`,{
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({content, extended_thinking:extended, web_search:webSearch, use_mcp:useMcp, model})
    });

    const reader  = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = '', fullText = '';

    while(true){
      const {done, value} = await reader.read();
      if(done) break;
      buf += decoder.decode(value, {stream:true});
      const lines = buf.split('\n\n');
      buf = lines.pop();
      for(const line of lines){
        if(!line.startsWith('data:')) continue;
        let evt;
        try{ evt = JSON.parse(line.slice(5).trim()); }catch{ continue; }

        if(evt.t === 'think'){
          addThinkStep(evt.v);
        } else if(evt.t === 'token'){
          fullText += evt.v;
          if(liveEl) liveEl.innerHTML = fmtContent(fullText) +
            '<span class="inline-block w-1 h-4 bg-amber-500 animate-pulse ml-0.5 rounded"></span>';
          document.getElementById('messages').scrollTop = 9999;
        } else if(evt.t === 'done'){
          messagesCache[aIdx] = {role:'assistant', content: fullText,
                                  artifacts: evt.artifacts||[], thinking: thinkLines};
          renderMessages();
          if(evt.artifacts && evt.artifacts.length) loadArtifact(evt.artifacts[0].id);
          if(typeof loadSidebarConversations==='function') loadSidebarConversations();
        }
      }
    }
  } catch(e){
    messagesCache[aIdx] = {role:'assistant', content:`Ошибка: ${e}`, artifacts:[], thinking:[]};
    renderMessages();
  } finally{
    sendBtn.disabled = false;
    input.focus();
  }
}

async function loadArtifact(id){
  const r = await fetch(`/api/artifacts/${id}`);
  openArtifact(await r.json());
}

function autoResize(){
  const ta = document.getElementById('chat-input');
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 192) + 'px';
}

document.addEventListener('DOMContentLoaded', ()=>{
  loadMessages();
  const input = document.getElementById('chat-input');
  input.addEventListener('input', autoResize);
  input.addEventListener('keydown', e=>{
    if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendMessage(); }
  });
  document.getElementById('send-btn').addEventListener('click', sendMessage);
  document.getElementById('rename-chat')?.addEventListener('click', async ()=>{
    const t = prompt('Новое название:');
    if(!t || !currentConvId) return;
    await fetch(`/api/conversations/${currentConvId}`,{method:'PUT',
      headers:{'Content-Type':'application/json'}, body:JSON.stringify({title:t})});
    document.getElementById('chat-title').textContent = t;
    if(typeof loadSidebarConversations==='function') loadSidebarConversations();
  });
});

window.loadArtifact = loadArtifact;
window.toggleThink  = toggleThink;
