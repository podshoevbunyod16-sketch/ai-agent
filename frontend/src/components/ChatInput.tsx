/**
 * ChatInput — auto-resizing textarea with send button, voice input, file drop.
 */
import { useState, useRef, useCallback, useEffect } from "react";
import { motion } from "framer-motion";
import { Send, Mic, MicOff, Loader2 } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
  disabled?: boolean;
}

export default function ChatInput({ onSend, isLoading, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const [isListening, setIsListening] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [text]);

  const handleSend = useCallback(() => {
    const msg = text.trim();
    if (!msg || isLoading) return;
    onSend(msg);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [text, isLoading, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  // Voice input via Web Speech API
  const toggleVoice = useCallback(() => {
    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
      alert("Speech recognition is not supported in this browser.");
      return;
    }

    if (isListening) {
      setIsListening(false);
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = "ru-RU";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      setText((prev) => (prev ? prev + " " + transcript : transcript));
      setIsListening(false);
    };

    recognition.onerror = () => {
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    setIsListening(true);
    recognition.start();
  }, [isListening]);

  return (
    <div className="border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 p-4">
      <div className="max-w-3xl mx-auto">
        <div className="relative flex items-end gap-2 bg-slate-50 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-700 p-2 focus-within:ring-2 focus-within:ring-blue-500/50 focus-within:border-blue-500 transition-all">
          {/* Voice button */}
          <button
            onClick={toggleVoice}
            className={`shrink-0 p-2 rounded-lg transition-colors ${
              isListening
                ? "bg-red-100 dark:bg-red-900/30 text-red-600 animate-pulse"
                : "text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
            }`}
            title={isListening ? "Stop listening" : "Voice input"}
          >
            {isListening ? (
              <MicOff className="w-4 h-4" />
            ) : (
              <Mic className="w-4 h-4" />
            )}
          </button>

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message..."
            rows={1}
            disabled={disabled || isLoading}
            className="flex-1 max-h-[200px] bg-transparent border-0 resize-none focus:ring-0 text-sm text-slate-900 dark:text-white placeholder:text-slate-400 py-2.5 outline-none disabled:opacity-50"
          />

          {/* Send button */}
          <motion.button
            whileTap={{ scale: 0.9 }}
            onClick={handleSend}
            disabled={!text.trim() || isLoading || disabled}
            className="shrink-0 p-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-40 disabled:hover:bg-blue-600 text-white transition-colors"
          >
            {isLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </motion.button>
        </div>
        <p className="text-center text-[10px] text-slate-400 mt-1.5">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  );
}
