/**
 * TopBar — header with sidebar toggle, model selector, theme toggle, export.
 */
import { Moon, Sun, Download, Menu, Server } from "lucide-react";
import ModelSelector from "./ModelSelector";

interface TopBarProps {
  onToggleSidebar: () => void;
  model: string;
  onModelChange: (provider: string, model: string) => void;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onExport: () => void;
  onNavigateMCP: () => void;
  hasMessages: boolean;
  tokenCount: number;
}

export default function TopBar({
  onToggleSidebar,
  model,
  onModelChange,
  theme,
  onToggleTheme,
  onExport,
  onNavigateMCP,
  hasMessages,
  tokenCount,
}: TopBarProps) {
  return (
    <header className="h-12 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-950/80 backdrop-blur-sm flex items-center justify-between px-3 shrink-0 z-10">
      <div className="flex items-center gap-2">
        <button
          onClick={onToggleSidebar}
          className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
        >
          <Menu className="w-4 h-4 text-slate-600 dark:text-slate-400" />
        </button>
        <ModelSelector
          model={model}
          onChange={onModelChange}
        />
      </div>

      <div className="flex items-center gap-1">
        {tokenCount > 0 && (
          <span className="hidden sm:inline text-[10px] text-slate-400 mr-2">
            {tokenCount.toLocaleString()} tokens
          </span>
        )}

        <button
          onClick={onNavigateMCP}
          className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title="MCP Servers"
        >
          <Server className="w-4 h-4 text-slate-500 dark:text-slate-400" />
        </button>

        {hasMessages && (
          <button
            onClick={onExport}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Export chat"
          >
            <Download className="w-4 h-4 text-slate-500 dark:text-slate-400" />
          </button>
        )}

        <button
          onClick={onToggleTheme}
          className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title="Toggle theme"
        >
          {theme === "dark" ? (
            <Sun className="w-4 h-4 text-amber-400" />
          ) : (
            <Moon className="w-4 h-4 text-slate-500" />
          )}
        </button>
      </div>
    </header>
  );
}
