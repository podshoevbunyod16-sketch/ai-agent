#!/bin/bash
# start_mcp.sh
# Быстрый запуск Local MCP Server в фоне

cd "$(dirname "$0")"

PORT=${MCP_PORT:-8765}
LOG="$HOME/.local_mcp.log"

# Останавливаем если уже работает
if lsof -ti:$PORT > /dev/null 2>&1; then
    echo "✅ MCP сервер уже работает на порту $PORT"
    exit 0
fi

echo "🚀 Запускаю Local MCP Server на порту $PORT..."
nohup python local_mcp_server.py --port $PORT > "$LOG" 2>&1 &
MCP_PID=$!

sleep 1

if kill -0 $MCP_PID 2>/dev/null; then
    echo "✅ MCP сервер запущен (PID: $MCP_PID)"
    echo "   URL: http://127.0.0.1:$PORT"
    echo "   Лог: $LOG"
    echo ""
    echo "Добавь в /mcp-settings:"
    echo "   Имя: Local Termux MCP"
    echo "   URL: http://127.0.0.1:$PORT"
else
    echo "❌ Ошибка запуска. Лог:"
    cat "$LOG"
fi
