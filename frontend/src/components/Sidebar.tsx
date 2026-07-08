/**
 * Sidebar — conversation list, search, new chat.
 * Collapsible on mobile. Shows pinned conversations at top.
 */
import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Plus,
  Search,
  MessageSquare,
  Pin,
  Trash2,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  X,
} from "lucide-react";
import type { Conversation } from "@/types";

interface SidebarProps {
  conversations: Conversation[];
  activeId: number | null;
  onSelect: (id: number) => void;
  onNewChat: () => void;
  onDelete: (id: number) => void;
  onTogglePin: (id: number, pinned: boolean) => void;
  onLogout: () => void;
  isOpen: boolean;
  onToggle: () => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  avatarUrl?: string | null;
  userName?: string | null;
  onNavigateMCP: () => void;
}

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
  onTogglePin,
  onLogout,
  isOpen,
  onToggle,
  searchQuery,
  onSearchChange,
  avatarUrl,
  userName,
  onNavigateMCP,
}: SidebarProps) {
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

  const filtered = useMemo(() => {
    let list = conversations;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter((c) => c.title.toLowerCase().includes(q));
    }
    // Pinned first
    return [...list].sort(
      (a, b) => (b.pinned ? 1 : 0) - (a.pinned ? 1 : 0) ||
        new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
  }, [conversations, searchQuery]);

  return (
    <>
      {/* Mobile overlay */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 z-40 lg:hidden"
            onClick={onToggle}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{
          width: isOpen ? 280 : 0,
          opacity: isOpen ? 1 : 0,
        }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
        className="fixed lg:relative z-50 h-full bg-slate-50 dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col overflow-hidden"
        style={{ minWidth: isOpen ? 280 : 0 }}
      >
        <div className="flex flex-col h-full w-[280px]">
          {/* Header */}
          <div className="p-3 border-b border-slate-200 dark:border-slate-800">
            <div className="flex items-center gap-2 mb-3">
              <button
                onClick={onToggle}
                className="lg:hidden p-1.5 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-800"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={onNewChat}
                className="flex-1 flex items-center justify-center gap-2 h-9 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <Plus className="w-4 h-4" />
                New Chat
              </button>
            </div>

            {/* Search */}
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search chats..."
                value={searchQuery}
                onChange={(e) => onSearchChange(e.target.value)}
                className="w-full h-8 pl-8 pr-7 text-sm rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              />
              {searchQuery && (
                <button
                  onClick={() => onSearchChange("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2"
                >
                  <X className="w-3.5 h-3.5 text-slate-400 hover:text-slate-600" />
                </button>
              )}
            </div>
          </div>

          {/* Conversation list */}
          <div className="flex-1 overflow-y-auto py-2">
            {filtered.length === 0 ? (
              <p className="text-center text-xs text-slate-400 mt-8">
                {searchQuery ? "No matches" : "No conversations yet"}
              </p>
            ) : (
              filtered.map((conv) => (
                <motion.div
                  key={conv.id}
                  layout
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className={`group relative mx-2 mb-1 rounded-lg cursor-pointer transition-colors ${
                    conv.id === activeId
                      ? "bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800"
                      : "hover:bg-slate-100 dark:hover:bg-slate-800 border border-transparent"
                  }`}
                >
                  <button
                    onClick={() => onSelect(conv.id)}
                    className="w-full flex items-start gap-2.5 p-2.5 text-left"
                  >
                    <MessageSquare className="w-4 h-4 mt-0.5 text-slate-400 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-slate-700 dark:text-slate-200 truncate">
                        {conv.title}
                      </p>
                      <p className="text-xs text-slate-400 mt-0.5">
                        {conv.model_name}
                      </p>
                    </div>
                    {conv.pinned && (
                      <Pin className="w-3 h-3 text-amber-500 shrink-0 mt-1" />
                    )}
                  </button>

                  {/* Actions */}
                  <div className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 flex gap-1">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onTogglePin(conv.id, !conv.pinned);
                      }}
                      className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700"
                      title={conv.pinned ? "Unpin" : "Pin"}
                    >
                      <Pin
                        className={`w-3 h-3 ${
                          conv.pinned
                            ? "text-amber-500"
                            : "text-slate-400"
                        }`}
                      />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setConfirmDelete(conv.id);
                      }}
                      className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30"
                      title="Delete"
                    >
                      <Trash2 className="w-3 h-3 text-slate-400 hover:text-red-500" />
                    </button>
                  </div>

                  {/* Delete confirmation */}
                  <AnimatePresence>
                    {confirmDelete === conv.id && (
                      <motion.div
                        initial={{ opacity: 0, scale: 0.9 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.9 }}
                        className="absolute inset-0 bg-slate-900/90 rounded-lg flex items-center justify-center gap-2 z-10"
                      >
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onDelete(conv.id);
                            setConfirmDelete(null);
                          }}
                          className="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700"
                        >
                          Delete
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setConfirmDelete(null);
                          }}
                          className="px-3 py-1 text-xs bg-slate-600 text-white rounded hover:bg-slate-700"
                        >
                          Cancel
                        </button>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              ))
            )}
          </div>

          {/* Footer */}
          <div className="p-3 border-t border-slate-200 dark:border-slate-800 space-y-1">
            <button
              onClick={onNavigateMCP}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <Settings className="w-4 h-4" />
              MCP Servers
            </button>
            <div className="flex items-center gap-2.5 px-3 py-2">
              {avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt=""
                  className="w-6 h-6 rounded-full"
                />
              ) : (
                <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold">
                  {userName?.[0]?.toUpperCase() || "U"}
                </div>
              )}
              <span className="text-sm text-slate-600 dark:text-slate-300 truncate flex-1">
                {userName || "User"}
              </span>
              <button
                onClick={onLogout}
                className="p-1.5 rounded-lg hover:bg-red-100 dark:hover:bg-red-900/30"
                title="Logout"
              >
                <LogOut className="w-4 h-4 text-slate-400 hover:text-red-500" />
              </button>
            </div>
          </div>
        </div>
      </motion.aside>

      {/* Toggle button (visible when sidebar closed on desktop) */}
      {!isOpen && (
        <button
          onClick={onToggle}
          className="hidden lg:flex fixed left-0 top-1/2 -translate-y-1/2 z-30 p-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-r-lg shadow-md hover:bg-slate-50 dark:hover:bg-slate-700"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      )}
    </>
  );
}
