#!/usr/bin/env python3
"""
local_mcp_server.py
Лёгкий локальный MCP-сервер для Termux/Android.

Инструменты:
  fetch_url      - читает любой сайт и возвращает текст
  web_search     - поиск через DuckDuckGo (без ключа)
  read_file      - читает файл на телефоне
  write_file     - записывает файл
  list_files     - список файлов в папке
  run_python     - запускает Python-код
  github_repos   - список репозиториев GitHub
  github_file    - читает файл из GitHub репозитория
  github_issues  - список issues репозитория

Запуск:
  python local_mcp_server.py --port 8765

Зависимости: только requests и стандартная библиотека Python
"""

import json
import os
import re
import sys
import subprocess
import tempfile
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN', '')
HOME = os.getenv('HOME', '/data/data/com.termux/files/home')
ALLOWED_DIRS = [HOME, '/tmp']

# ------------------------------------------------------------------ #
# Инструменты
# ------------------------------------------------------------------ #

def tool_fetch_url(url: str, max_chars: int = 5000) -> str:
    try:
        r = requests.get(url,
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=12, allow_redirects=True)
        r.raise_for_status()
        # Удаляем HTML-теги
        text = re.sub(r'<script[^>]*>.*?</script>', '', r.text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>',  '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = '\n'.join(l.strip() for l in text.splitlines() if l.strip())
        return text[:max_chars]
    except Exception as e:
        return f'Ошибка загрузки {url}: {e}'


def tool_web_search(query: str, max_results: int = 8) -> str:
    """DuckDuckGo HTML поиск — без API ключа."""
    try:
        url = f'https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}'
        r = requests.get(url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible)'},
            timeout=10)
        # Извлекаем заголовки и снипеты
        titles   = re.findall(r'class="result__a"[^>]*>([^<]+)', r.text)
        snippets = re.findall(r'class="result__snippet"[^>]*>([^<]+)', r.text)
        links    = re.findall(r'uddg=([^&"]+)', r.text)
        results = []
        for i in range(min(max_results, len(titles))):
            title   = titles[i].strip()
            snippet = snippets[i].strip() if i < len(snippets) else ''
            link    = requests.utils.unquote(links[i]) if i < len(links) else ''
            results.append(f'{i+1}. {title}\n   {snippet}\n   {link}')
        return '\n\n'.join(results) if results else 'Ничего не найдено'
    except Exception as e:
        return f'Ошибка поиска: {e}'


def _safe_path(path: str) -> str:
    """TODO: проверяем что путь в разрешённой зоне."""
    if not os.path.isabs(path):
        path = os.path.join(HOME, path)
    path = os.path.realpath(path)
    for d in ALLOWED_DIRS:
        if path.startswith(os.path.realpath(d)):
            return path
    raise PermissionError(f'Доступ к {path} запрещён')


def tool_read_file(path: str, max_chars: int = 8000) -> str:
    try:
        safe = _safe_path(path)
        with open(safe, 'r', encoding='utf-8', errors='replace') as f:
            return f.read(max_chars)
    except Exception as e:
        return f'Ошибка чтения: {e}'


def tool_write_file(path: str, content: str) -> str:
    try:
        safe = _safe_path(path)
        os.makedirs(os.path.dirname(safe), exist_ok=True)
        with open(safe, 'w', encoding='utf-8') as f:
            f.write(content)
        return f'Сохранено: {safe} ({len(content)} символов)'
    except Exception as e:
        return f'Ошибка записи: {e}'


def tool_list_files(path: str = '.', pattern: str = '') -> str:
    try:
        safe = _safe_path(path)
        entries = []
        for name in sorted(os.listdir(safe)):
            if pattern and pattern.lower() not in name.lower():
                continue
            full = os.path.join(safe, name)
            size = os.path.getsize(full) if os.path.isfile(full) else 0
            kind = '📁' if os.path.isdir(full) else '📄'
            entries.append(f'{kind} {name}' + (f'  ({size} bytes)' if size else ''))
        return '\n'.join(entries) if entries else 'Папка пуста'
    except Exception as e:
        return f'Ошибка: {e}'


def tool_run_python(code: str, timeout: int = 15) -> str:
    try:
        with tempfile.NamedTemporaryFile(suffix='.py', mode='w',
                                         encoding='utf-8', delete=False) as f:
            f.write(code)
            fname = f.name
        result = subprocess.run(
            [sys.executable, fname],
            capture_output=True, text=True, timeout=timeout
        )
        os.unlink(fname)
        out = result.stdout[:3000]
        err = result.stderr[:1000]
        if err:
            return f'STDOUT:\n{out}\nSTDERR:\n{err}'
        return out or 'Выполнено (вывод пустой)'
    except subprocess.TimeoutExpired:
        return f'Превышен таймаут ({timeout}с)'
    except Exception as e:
        return f'Ошибка: {e}'


def _gh_headers():
    h = {'Accept': 'application/vnd.github+json'}
    if GITHUB_TOKEN:
        h['Authorization'] = f'Bearer {GITHUB_TOKEN}'
    return h


def tool_github_repos(username: str = '', per_page: int = 20) -> str:
    try:
        if username:
            url = f'https://api.github.com/users/{username}/repos?per_page={per_page}&sort=updated'
        else:
            url = f'https://api.github.com/user/repos?per_page={per_page}&sort=updated'
        r = requests.get(url, headers=_gh_headers(), timeout=10)
        r.raise_for_status()
        repos = r.json()
        lines = []
        for repo in repos:
            name  = repo.get('full_name', '?')
            desc  = (repo.get('description') or '')[:60]
            stars = repo.get('stargazers_count', 0)
            lang  = repo.get('language') or ''
            lines.append(f'⭐ {stars}  {name}  [{lang}]\n   {desc}')
        return '\n\n'.join(lines) if lines else 'Репозиториев не найдено'
    except Exception as e:
        return f'Ошибка GitHub: {e}'


def tool_github_file(repo: str, path: str, ref: str = 'main') -> str:
    try:
        import base64
        url = f'https://api.github.com/repos/{repo}/contents/{path}?ref={ref}'
        r = requests.get(url, headers=_gh_headers(), timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get('encoding') == 'base64':
            return base64.b64decode(data['content']).decode('utf-8', errors='replace')[:6000]
        return data.get('content', 'Пустой файл')[:6000]
    except Exception as e:
        return f'Ошибка: {e}'


def tool_github_issues(repo: str, state: str = 'open', per_page: int = 10) -> str:
    try:
        url = f'https://api.github.com/repos/{repo}/issues?state={state}&per_page={per_page}'
        r = requests.get(url, headers=_gh_headers(), timeout=10)
        r.raise_for_status()
        issues = r.json()
        lines = []
        for iss in issues:
            num   = iss.get('number')
            title = iss.get('title', '?')
            state = iss.get('state', '?')
            lines.append(f'#{num} [{state}] {title}')
        return '\n'.join(lines) if lines else 'Иссюев нет'
    except Exception as e:
        return f'Ошибка: {e}'


# ------------------------------------------------------------------ #
# Описание инструментов (tools/list)
# ------------------------------------------------------------------ #
TOOLS = [
    {
        'name': 'fetch_url',
        'description': '🌐 Загрузить веб-страницу и вернуть текст',
        'inputSchema': {'type':'object','properties':{
            'url':{'type':'string','description':'Полный URL страницы'},
            'max_chars':{'type':'integer','description':'Макс символов (default 5000)'}
        },'required':['url']}
    },
    {
        'name': 'web_search',
        'description': '🔍 Поиск в интернете через DuckDuckGo (без API ключа)',
        'inputSchema': {'type':'object','properties':{
            'query':{'type':'string','description':'Поисковый запрос'},
            'max_results':{'type':'integer','description':'Кол-во результатов (default 8)'}
        },'required':['query']}
    },
    {
        'name': 'read_file',
        'description': '📄 Прочитать файл на телефоне',
        'inputSchema': {'type':'object','properties':{
            'path':{'type':'string','description':'Путь к файлу'},
            'max_chars':{'type':'integer','description':'Макс символов'}
        },'required':['path']}
    },
    {
        'name': 'write_file',
        'description': '✏️ Записать файл на телефоне',
        'inputSchema': {'type':'object','properties':{
            'path':{'type':'string','description':'Путь к файлу'},
            'content':{'type':'string','description':'Содержимое'}
        },'required':['path','content']}
    },
    {
        'name': 'list_files',
        'description': '📁 Список файлов в папке',
        'inputSchema': {'type':'object','properties':{
            'path':{'type':'string','description':'Папка'},
            'pattern':{'type':'string','description':'Фильтр'}
        },'required':[]}
    },
    {
        'name': 'run_python',
        'description': '💻 Запустить Python-код на телефоне',
        'inputSchema': {'type':'object','properties':{
            'code':{'type':'string','description':'Python код'},
            'timeout':{'type':'integer','description':'Таймаут в секундах'}
        },'required':['code']}
    },
    {
        'name': 'github_repos',
        'description': '⭐ Список репозиториев GitHub',
        'inputSchema': {'type':'object','properties':{
            'username':{'type':'string','description':'GitHub username (пусто = свои)'},
            'per_page':{'type':'integer','description':'Кол-во'}
        },'required':[]}
    },
    {
        'name': 'github_file',
        'description': '📄 Прочитать файл из GitHub репозитория',
        'inputSchema': {'type':'object','properties':{
            'repo':{'type':'string','description':'owner/repo'},
            'path':{'type':'string','description':'Путь к файлу'},
            'ref':{'type':'string','description':'Ветка/коммит'}
        },'required':['repo','path']}
    },
    {
        'name': 'github_issues',
        'description': '🐛 Issues репозитория GitHub',
        'inputSchema': {'type':'object','properties':{
            'repo':{'type':'string','description':'owner/repo'},
            'state':{'type':'string','description':'open/closed/all'},
            'per_page':{'type':'integer'}
        },'required':['repo']}
    },
]

TOOL_MAP = {
    'fetch_url':     lambda a: tool_fetch_url(a['url'], a.get('max_chars', 5000)),
    'web_search':    lambda a: tool_web_search(a['query'], a.get('max_results', 8)),
    'read_file':     lambda a: tool_read_file(a['path'], a.get('max_chars', 8000)),
    'write_file':    lambda a: tool_write_file(a['path'], a['content']),
    'list_files':    lambda a: tool_list_files(a.get('path', '.'), a.get('pattern', '')),
    'run_python':    lambda a: tool_run_python(a['code'], a.get('timeout', 15)),
    'github_repos':  lambda a: tool_github_repos(a.get('username', ''), a.get('per_page', 20)),
    'github_file':   lambda a: tool_github_file(a['repo'], a['path'], a.get('ref', 'main')),
    'github_issues': lambda a: tool_github_issues(a['repo'], a.get('state', 'open'), a.get('per_page', 10)),
}


# ------------------------------------------------------------------ #
# HTTP сервер (Streamable HTTP MCP)
# ------------------------------------------------------------------ #

class MCPHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        pass  # отключаем лог запросов

    def _send_json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, x-api-key')
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/', '/health'):
            self._send_json({'status': 'ok', 'tools': len(TOOLS),
                             'name': 'Local MCP Server (Termux)'})
        elif path == '/tools':
            self._send_json({'tools': TOOLS})
        else:
            self._send_json({'error': 'not found'}, 404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body   = self.rfile.read(length)
        try:
            req = json.loads(body)
        except Exception:
            self._send_json({'error': 'invalid JSON'}, 400)
            return

        method = req.get('method', '')
        params = req.get('params', {})
        req_id = req.get('id', 1)

        if method == 'initialize':
            self._send_json({
                'jsonrpc': '2.0', 'id': req_id,
                'result': {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {'tools': {'listChanged': False}},
                    'serverInfo': {'name': 'local-mcp-termux', 'version': '1.0'}
                }
            })

        elif method == 'tools/list':
            self._send_json({
                'jsonrpc': '2.0', 'id': req_id,
                'result': {'tools': TOOLS}
            })

        elif method == 'tools/call':
            tool_name = params.get('name', '')
            arguments = params.get('arguments', {})
            if tool_name not in TOOL_MAP:
                self._send_json({
                    'jsonrpc': '2.0', 'id': req_id,
                    'error': {'code': -32601, 'message': f'Инструмент {tool_name!r} не найден'}
                })
                return
            try:
                result_text = TOOL_MAP[tool_name](arguments)
            except Exception:
                result_text = traceback.format_exc()[:1000]
            self._send_json({
                'jsonrpc': '2.0', 'id': req_id,
                'result': {
                    'content': [{'type': 'text', 'text': str(result_text)}],
                    'isError': False
                }
            })
        else:
            self._send_json({
                'jsonrpc': '2.0', 'id': req_id,
                'error': {'code': -32601, 'message': f'Неизвестный метод: {method}'}
            })


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Local MCP Server for Termux')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--host', default='127.0.0.1')
    args = parser.parse_args()

    print(f'🚀 Local MCP Server запущен: http://{args.host}:{args.port}')
    print(f'🛠️  Инструментов: {len(TOOLS)}')
    for t in TOOLS:
        print(f'   • {t["name"]} — {t["description"]}')
    if GITHUB_TOKEN:
        print(f'\n✅ GITHUB_TOKEN задан (доступ к GitHub API расширен)')
    else:
        print(f'\n⚠️  GITHUB_TOKEN не задан (без него GitHub даёт ограниченный доступ)')
    print(f'\nДобавь в Claude Clone:')
    print(f'  URL: http://{args.host}:{args.port}')
    print(f'  Имя: Local Termux MCP\n')

    server = HTTPServer((args.host, args.port), MCPHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nСервер остановлен')


if __name__ == '__main__':
    main()
