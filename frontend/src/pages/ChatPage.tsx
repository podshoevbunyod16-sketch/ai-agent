/**
 * ChatPage — main chat interface with sidebar, message list, and input.
 * Manages conversation state, SSE streaming, and all chat interactions.
 */
import { useState, useCallback, useEffect, useRef } from "react";
import { useNavigate } from "react-router";
import { motion, AnimatePresence } from "framer-motion";
import { Loader2 } from "lucide-react";

import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import MessageList from "@/components/MessageList";
import ChatInput from "@/components/ChatInput";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { chatStream } from "@/hooks/useAPI";
import { useAPI } from "@/hooks/useAPI";
import type { Conversation, Message } from "@/types";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function ChatPage() {
  const navigate = useNavigate();
  const { user, dbUser, getToken, logout } = useAuth();
  const { resolved, toggleTheme } = useTheme();
  const { request } = useAPI();

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [typingContent, setTypingContent] = useState("");
  const [provider, setProvider] = useState("groq");
  const [model, setModel] = useState("llama-3.3-70b-versatile");
  const [searchQuery, setSearchQuery] = useState("");
  const [tokenCount, setTokenCount] = useState(0);
  const [serverWaking, setServerWaking] = useState(false);
  const abortRef = useRef(false);

  // Load conversations on mount
  useEffect(() => {
    if (!user) return;
    loadConversations();
  }, [user]);

  // Check if server is waking up (Render free tier cold start)
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API_URL}/health`, { signal: AbortSignal.timeout(5000) });
        if (!res.ok) setServerWaking(true);
        else setServerWaking(false);
      } catch {
        setServerWaking(true);
      }
    };
    checkHealth();
    const interval = setInterval(() => {
      if (serverWaking) checkHealth();
    }, 5000);
    return () => clearInterval(interval);
  }, [serverWaking]);

  const loadConversations = async () => {
    try {
      const token = await getToken();
      const data = await request<{ conversations: Conversation[] }>(
        "/api/conversations",
        { token }
      );
      setConversations(data.conversations);
    } catch (e) {
      console.error("Failed to load conversations:", e);
    }
  };

  const loadMessages = async (convId: number) => {
    try {
      const token = await getToken();
      const data = await request<{
        conversation: Conversation;
        messages: Message[];
      }>(`/api/conversations/${convId}`, { token });
      setMessages(data.messages);
      setProvider(data.conversation.model_provider);
      setModel(data.conversation.model_name);
    } catch (e) {
      console.error("Failed to load messages:", e);
    }
  };

  const handleSelectConversation = useCallback(
    async (id: number) => {
      setActiveConvId(id);
      await loadMessages(id);
      if (window.innerWidth < 1024) setSidebarOpen(false);
    },
    []
  );

  const handleNewChat = useCallback(() => {
    setActiveConvId(null);
    setMessages([]);
    setTypingContent("");
    setIsLoading(false);
    if (window.innerWidth < 1024) setSidebarOpen(false);
  }, []);

  const handleDeleteConversation = useCallback(
    async (id: number) => {
      try {
        const token = await getToken();
        await request(`/api/conversations/${id}`, {
          method: "DELETE",
          token,
        });
        setConversations((prev) => prev.filter((c) => c.id !== id));
        if (activeConvId === id) {
          setActiveConvId(null);
          setMessages([]);
        }
      } catch (e) {
        console.error("Delete failed:", e);
      }
    },
    [activeConvId, getToken, request]
  );

  const handleTogglePin = useCallback(
    async (id: number, pinned: boolean) => {
      try {
        const token = await getToken();
        await request(`/api/conversations/${id}`, {
          method: "PATCH",
          body: { pinned },
          token,
        });
        setConversations((prev) =>
          prev.map((c) => (c.id === id ? { ...c, pinned } : c))
        );
      } catch (e) {
        console.error("Pin failed:", e);
      }
    },
    [getToken, request]
  );

  const handleSendMessage = useCallback(
    async (text: string) => {
      if (isLoading) return;
      setIsLoading(true);
      setTypingContent("");
      abortRef.current = false;

      // Optimistically add user message
      const tempUserMsg: Message = {
        id: Date.now(),
        conversation_id: activeConvId || 0,
        branch_id: null,
        role: "user",
        content: text,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, tempUserMsg]);

      try {
        const token = await getToken();
        let assistantContent = "";
        let currentConvId = activeConvId;

        for await (const event of chatStream(
          {
            conversation_id: currentConvId,
            message: text,
            provider,
            model,
          },
          token
        )) {
          if (abortRef.current) break;

          switch (event.type) {
            case "conversation":
              currentConvId = event.conversation.id;
              setActiveConvId(currentConvId);
              setConversations((prev) => {
                const exists = prev.find((c) => c.id === currentConvId);
                if (exists) return prev;
                return [event.conversation, ...prev];
              });
              break;

            case "content":
              assistantContent += event.content;
              setTypingContent(assistantContent);
              break;

            case "tool_start":
              // Could show tool execution indicator
              break;

            case "tool_result":
              // Tool result is saved server-side
              break;

            case "finish":
              if (event.usage?.total_tokens) {
                setTokenCount((prev) => prev + event.usage.total_tokens);
              }
              break;

            case "error":
              console.error("Stream error:", event.message);
              break;

            case "done":
              break;
          }
        }

        // Reload messages from server to get proper IDs
        if (currentConvId) {
          await loadMessages(currentConvId);
        }
        setTypingContent("");
      } catch (e: any) {
        console.error("Chat error:", e);
        // Add error message
        const errorMsg: Message = {
          id: Date.now() + 1,
          conversation_id: activeConvId || 0,
          branch_id: null,
          role: "assistant",
          content: `**Error:** ${e.message}`,
          created_at: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsLoading(false);
        setTypingContent("");
        await loadConversations();
      }
    },
    [activeConvId, provider, model, isLoading, getToken]
  );

  const handleExport = useCallback(async () => {
    if (!activeConvId) return;
    try {
      const token = await getToken();
      const fmt = confirm("Export as JSON? (Cancel for Markdown)")
        ? "json"
        : "markdown";
      const data = await request<{
        markdown?: string;
        conversation?: any;
        messages?: Message[];
      }>(`/api/conversations/${activeConvId}/export?format=${fmt}`, { token });

      const blob =
        fmt === "json"
          ? new Blob([JSON.stringify(data, null, 2)], {
              type: "application/json",
            })
          : new Blob([data.markdown || ""], { type: "text/markdown" });

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `chat-export-${activeConvId}.${fmt === "json" ? "json" : "md"}`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Export failed:", e);
    }
  }, [activeConvId, getToken, request]);

  const handleModelChange = useCallback((p: string, m: string) => {
    setProvider(p);
    setModel(m);
  }, []);

  return (
    <div className="flex h-screen bg-white dark:bg-slate-950 text-slate-900 dark:text-white overflow-hidden">
      {/* Server waking overlay */}
      <AnimatePresence>
        {serverWaking && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[60] bg-slate-950/80 backdrop-blur-sm flex items-center justify-center"
          >
            <motion.div
              animate={{ scale: [1, 1.05, 1] }}
              transition={{ repeat: Infinity, duration: 2 }}
              className="text-center"
            >
              <Loader2 className="w-8 h-8 animate-spin text-blue-500 mx-auto mb-3" />
              <p className="text-white font-medium">Server is waking up...</p>
              <p className="text-slate-400 text-sm mt-1">
                Render free tier cold start (30-50 sec)
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <Sidebar
        conversations={conversations}
        activeId={activeConvId}
        onSelect={handleSelectConversation}
        onNewChat={handleNewChat}
        onDelete={handleDeleteConversation}
        onTogglePin={handleTogglePin}
        onLogout={logout}
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        avatarUrl={dbUser?.photo_url}
        userName={dbUser?.display_name || dbUser?.email || "User"}
        onNavigateMCP={() => navigate("/mcp-servers")}
      />

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
          model={model}
          onModelChange={handleModelChange}
          theme={resolved}
          onToggleTheme={toggleTheme}
          onExport={handleExport}
          onNavigateMCP={() => navigate("/mcp-servers")}
          hasMessages={messages.length > 0}
          tokenCount={tokenCount}
        />

        <MessageList
          messages={messages}
          isLoading={isLoading}
          theme={resolved}
          typingContent={typingContent}
        />

        <ChatInput
          onSend={handleSendMessage}
          isLoading={isLoading}
          disabled={serverWaking}
        />
      </div>
    </div>
  );
}
