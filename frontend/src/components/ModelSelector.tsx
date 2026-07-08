/**
 * ModelSelector — dropdown to choose LLM provider and model.
 */
import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronDown, Zap, Globe } from "lucide-react";

interface ModelOption {
  id: string;
  name: string;
  provider: "groq" | "openrouter";
}

interface ModelSelectorProps {
  model: string;
  onChange: (provider: string, model: string) => void;
}

const DEFAULT_MODELS: ModelOption[] = [
  { id: "llama-3.3-70b-versatile", name: "Llama 3.3 70B", provider: "groq" },
  { id: "llama-3.1-8b-instant", name: "Llama 3.1 8B", provider: "groq" },
  { id: "mixtral-8x7b-32768", name: "Mixtral 8x7B", provider: "groq" },
  { id: "gemma2-9b-it", name: "Gemma 2 9B", provider: "groq" },
  { id: "deepseek-r1-distill-llama-70b", name: "DeepSeek R1 Distill", provider: "groq" },
  { id: "anthropic/claude-3.5-sonnet", name: "Claude 3.5 Sonnet", provider: "openrouter" },
  { id: "openai/gpt-4o-mini", name: "GPT-4o Mini", provider: "openrouter" },
  { id: "meta-llama/llama-3.3-70b-instruct", name: "Llama 3.3 70B (OR)", provider: "openrouter" },
];

export default function ModelSelector({
  model,
  onChange,
}: ModelSelectorProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const selected = DEFAULT_MODELS.find((m) => m.id === model) || DEFAULT_MODELS[0];

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
      >
        {selected.provider === "groq" ? (
          <Zap className="w-3.5 h-3.5 text-amber-500" />
        ) : (
          <Globe className="w-3.5 h-3.5 text-blue-500" />
        )}
        <span className="font-medium">{selected.name}</span>
        <ChevronDown
          className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -5, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -5, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-1 w-64 bg-white dark:bg-slate-900 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 py-1 z-50"
          >
            {/* Groq section */}
            <div className="px-3 py-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
              Groq (fast)
            </div>
            {DEFAULT_MODELS.filter((m) => m.provider === "groq").map((m) => (
              <button
                key={m.id}
                onClick={() => {
                  onChange(m.provider, m.id);
                  setOpen(false);
                }}
                className={`w-full flex items-center gap-2 px-3 py-2 text-sm transition-colors ${
                  m.id === model
                    ? "bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300"
                    : "text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
                }`}
              >
                <Zap className="w-3.5 h-3.5 text-amber-500 shrink-0" />
                {m.name}
              </button>
            ))}

            {/* OpenRouter section */}
            <div className="px-3 py-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider border-t border-slate-100 dark:border-slate-800 mt-1 pt-2">
              OpenRouter
            </div>
            {DEFAULT_MODELS.filter((m) => m.provider === "openrouter").map((m) => (
              <button
                key={m.id}
                onClick={() => {
                  onChange(m.provider, m.id);
                  setOpen(false);
                }}
                className={`w-full flex items-center gap-2 px-3 py-2 text-sm transition-colors ${
                  m.id === model
                    ? "bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300"
                    : "text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
                }`}
              >
                <Globe className="w-3.5 h-3.5 text-blue-500 shrink-0" />
                {m.name}
              </button>
            ))}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
