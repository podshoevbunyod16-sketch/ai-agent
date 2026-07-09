let currentConversationId = window.ACTIVE_CONVERSATION_ID || null;
let messagesCache = [];

async function ensureConversation(){
  if(currentConversationId) return currentConversationId;
  const r = await fetch('/api/conversations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:'Новый чат'})});
  const c = await r.json();
  currentConversationId = c.id;
  window.ACTIVE_CONVERSATION_ID = c.id;
  history.replaceState(null,'','/?c='+c.id);
  if(typeof loadSidebarConversations==='function') loadSidebarConversations();
  return c.id;
}

function escapeHtml(text){
  return text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function formatContent(text){
  let html = escapeHtml(text);
  html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (m,lang,code)=>{
    return `<pre class="bg-stone-900 text-stone-100 rounded-xl p-3 my-2 text-[13px] overflow-x-auto">${code}</pre>`;
  });
  html = html.replace(/\n/g,'<br>');
  return html;
}

function renderMessages(){
  const inner = document.getElementById('messages-inner');
  if(!messagesCache.length){
    inner.innerHTML = `
      <div class="text-center py-16">
        <div class="w-14 h-14 rounded-2xl bg-stone-800 text-white mx-auto flex items-center justify-center text-2xl font-bold mb-4">*</div>
        <h2 class="text-2xl font-semibold text-stone-900 mb-2">Добрый вечер${window.USER_NAME?(', '+window.USER_NAME):''}</h2>
        <p class="text-stone-500 mb-8">Чем я могу помочь сегодня?</p>
        <div class="grid sm:grid-cols-2 gap-3 max-w-xl mx-auto text-left text-sm">
          ${[
            'Напиши Python скрипт для парсинга CSV',
            'Создай React компонент с Tailwind',
            'Объясни, как работает MCP протокол',
            'Сделай артефакт с HTML страницей'
          ].map(t=>`<button class="starter px-4 py-3 bg-white border border-stone-200 rounded-2xl hover:border-amber-300 text-left" data-prompt="${t.replace(/"/g,'&quot;')}">${t}</button>`).join('')}
        </div>
      </div>`;
      document.querySelectorAll('.starter').forEach(b=> b.onclick = ()=>{ document.getElementById('chat-input').value = b.dataset.prompt; sendMessage(); });
    return;
  }
  inner.innerHTML = messagesCache.map((m,idx)=>{
    const isUser = m.role==='user';
    return `<div class="flex ${isUser?'justify-end':''}">
      <div class="max-w-[85%] ${isUser?'msg-user':'msg-assistant'} rounded-2xl px-4 py-3 shadow-sm">
        <div class="text-[11px] text-stone-500 mb-1">${isUser?'Вы':'Claude'}</div>
        <div class="msg-content text-[15px] leading-relaxed whitespace-pre-wrap break-words" data-idx="${idx}">${formatContent(m.content)}</div>
        ${m.artifacts && m.artifacts.length ? `
          <div class="mt-3 flex flex-wrap gap-2">
            ${m.artifacts.map(a=>`<button onclick="loadArtifact(${a.id})" class="text-xs px-2.5 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 hover:bg-amber-100">📄 ${a.title||a.language}</button>`).join('')}
          </div>`:''}
      </div>
    </div>`;
  }).join('');
  const box = document.getElementById('messages');
  box.scrollTop = box.scrollHeight;
}

async function loadMessages(){
  if(!currentConversationId){ renderMessages(); return; }
  const r = await fetch(`/api/conversations/${currentConversationId}/messages`);
  if(!r.ok) return;
  messagesCache = await r.json();
  renderMessages();
}

// --- Эффект "печатной машинки" ---
function typeWriter(el, text, speed=12){
  return new Promise(resolve=>{
    let i = 0;
    el.textContent = '';
    el.classList.add('typing-cursor');
    const box = document.getElementById('messages');
    const timer = setInterval(()=>{
      const chunk = text.length > 400 ? 3 : 1;
      el.textContent += text.slice(i, i+chunk);
      i += chunk;
      box.scrollTop = box.scrollHeight;
      if(i>=text.length){
        clearInterval(timer);
        el.classList.remove('typing-cursor');
        resolve();
      }
    }, speed);
  });
}

async function sendMessage(){
  const input = document.getElementById('chat-input');
  const content = input.value.trim();
  if(!content) return;
  const sendBtn = document.getElementById('send-btn');
  sendBtn.disabled = true;
  input.value=''; autoResize();
  const cid = await ensureConversation();

  messagesCache.push({role:'user', content, artifacts:[]});
  renderMessages();

  messagesCache.push({role:'assistant', content:'⏳ Claude думает...', artifacts:[]});
  renderMessages();

  try{
    const extended = document.getElementById('extended-thinking').checked;
    const webSearch = document.getElementById('web-search-toggle').checked;
    const model = document.getElementById('model-select').value;
    const r = await fetch(`/api/conversations/${cid}/messages`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({content, extended_thinking:extended, web_search:webSearch, model})
    });
    const data = await r.json();

    messagesCache.pop();
    messagesCache.push({role:'assistant', content:'', artifacts:[]});
    renderMessages();

    const nodes = document.querySelectorAll('.msg-content');
    const targetEl = nodes[nodes.length-1];
    if(targetEl){
      await typeWriter(targetEl, data.message.content);
    }

    messagesCache[messagesCache.length-1] = {
      role:'assistant',
      content: data.message.content,
      artifacts: data.artifacts || []
    };
    renderMessages();

    if(data.artifacts && data.artifacts.length){
      openArtifact(data.artifacts[0]);
    }
    document.getElementById('chat-title').textContent = 'Чат #'+cid;
    if(typeof loadSidebarConversations==='function') loadSidebarConversations();
  }catch(e){
    messagesCache.pop();
    messagesCache.push({role:'assistant', content:'Ошибка: '+e, artifacts:[]});
    renderMessages();
  } finally {
    sendBtn.disabled=false;
    input.focus();
  }
}

async function loadArtifact(id){
  const r = await fetch(`/api/artifacts/${id}`);
  const art = await r.json();
  openArtifact(art);
}

function autoResize(){
  const ta = document.getElementById('chat-input');
  ta.style.height='auto';
  ta.style.height = Math.min(ta.scrollHeight, 192)+'px';
}

document.addEventListener('DOMContentLoaded', ()=>{
  loadMessages();
  const input = document.getElementById('chat-input');
  const btn = document.getElementById('send-btn');
  input.addEventListener('input', autoResize);
  input.addEventListener('keydown', e=>{
    if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); sendMessage(); }
  });
  btn.addEventListener('click', sendMessage);

  document.getElementById('rename-chat')?.addEventListener('click', async ()=>{
    const title = prompt('Новое название чата:');
    if(!title || !currentConversationId) return;
    await fetch(`/api/conversations/${currentConversationId}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({title})});
    document.getElementById('chat-title').textContent = title;
    loadSidebarConversations();
  });
});

window.loadArtifact = loadArtifact;
