/**
 * MessageList — renders chat messages with markdown, code highlighting,
 * chain-of-thought collapsible blocks, and copy buttons.
 */
import { useRef, useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import { Copy, Check, Brain, ChevronDown, ChevronUp, User, Bot, Wrench } from "lucide-react";
import type { Message } from "@/types";

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  theme: "dark" | "light";
  typingContent?: string;
}

function CodeBlock({
  language,
  value,
  theme,
}: {
  language: string;
  value: string;
  theme: "dark" | "light";
}) {
  const [copied, setCopied] = useState(false);

  const copy = useCallback(async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [value]);

  return (
    <div className="relative group my-2 rounded-lg overflow-hidden border border-slate-200 dark:border-slate-700">
      <div className="flex items-center justify-between px-3 py-1.5 bg-slate-100 dark:bg-slate-800 text-xs text-slate-500 dark:text-slate-400">
        <span className="font-mono">{language || "text"}</span>
        <button
          onClick={copy}
          className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
        >
          {copied ? (
            <Check className="w-3.5 h-3.5 text-green-500" />
          ) : (
            <Copy className="w-3.5 h-3.5" />
          )}
        </button>
      </div>
      <SyntaxHighlighter
        language={language || "text"}
        style={theme === "dark" ? oneDark : oneLight}
        customStyle={{
          margin: 0,
          borderRadius: 0,
          fontSize: "0.8125rem",
          lineHeight: "1.5",
        }}
      >
        {value}
      </SyntaxHighlighter>
    </div>
  );
}

function MessageItem({
  message,
  theme,
}: {
  message: Message;
  theme: "dark" | "light";
}) {
  const [thoughtOpen, setThoughtOpen] = useState(false);

  const isUser = message.role === "user";
  const isTool = message.role === "tool";

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`py-4 ${isUser ? "bg-blue-50/50 dark:bg-blue-900/5" : ""}`}
    >
      <div className="max-w-3xl mx-auto flex gap-3 px-4">
        {/* Avatar */}
        <div className="shrink-0 mt-0.5">
          {isUser ? (
            <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center">
              <User className="w-4 h-4 text-white" />
            </div>
          ) : isTool ? (
            <div className="w-7 h-7 rounded-full bg-amber-600 flex items-center justify-center">
              <Wrench className="w-4 h-4 text-white" />
            </div>
          ) : (
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center">
              <Bot className="w-4 h-4 text-white" />
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          {/* Role label */}
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 mb-1">
            {isUser ? "You" : isTool ? `Tool: ${message.tool_name || ""}` : "Assistant"}
          </p>

          {/* Chain of thought (collapsible) */}
          {message.chain_of_thought && (
            <div className="mb-2">
              <button
                onClick={() => setThoughtOpen(!thoughtOpen)}
                className="flex items-center gap-1.5 text-xs text-purple-600 dark:text-purple-400 hover:text-purple-700"
              >
                <Brain className="w-3.5 h-3.5" />
                <span>Thinking</span>
                {thoughtOpen ? (
                  <ChevronUp className="w-3 h-3" />
                ) : (
                  <ChevronDown className="w-3 h-3" />
                )}
              </button>
              <AnimatePresence>
                {thoughtOpen && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-1 p-2.5 rounded-lg bg-purple-50 dark:bg-purple-900/20 border border-purple-200 dark:border-purple-800 text-xs text-purple-800 dark:text-purple-300 font-mono whitespace-pre-wrap">
                      {message.chain_of_thought}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}

          {/* Message content */}
          {message.content && (
            <div className="prose prose-sm dark:prose-invert max-w-none text-slate-800 dark:text-slate-200">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{
                  code({ node, inline, className, children, ...props }: any) {
                    const match = /language-(\w+)/.exec(className || "");
                    const language = match ? match[1] : "";
                    const value = String(children).replace(/\n$/, "");
                    if (!inline && language) {
                      return (
                        <CodeBlock
                          language={language}
                          value={value}
                          theme={theme}
                        />
                      );
                    }
                    return (
                      <code
                        className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-xs font-mono"
                        {...props}
                      >
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}

          {/* Tool call info */}
          {message.tool_calls && message.tool_calls.length > 0 && (
            <div className="mt-2 p-2 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800">
              <p className="text-xs text-amber-700 dark:text-amber-400 font-medium">
                Called tools:
              </p>
              {message.tool_calls.map((tc: any, i: number) => (
                <p key={i} className="text-xs text-amber-600 dark:text-amber-500 font-mono mt-0.5">
                  {tc.function?.name}({tc.function?.arguments})
                </p>
              ))}
            </div>
          )}

          {/* Tokens used */}
          {message.tokens_used && (
            <p className="text-[10px] text-slate-400 mt-1">
              {message.tokens_used.toLocaleString()} tokens
            </p>
          )}
        </div>
      </div>
    </motion.div>
  );
}

export default function MessageList({
  messages,
  isLoading,
  theme,
  typingContent,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, typingContent]);

  return (
    <div className="flex-1 overflow-y-auto">
      {messages.length === 0 && !isLoading ? (
        <div className="flex flex-col items-center justify-center h-full text-slate-400 dark:text-slate-500">
          <Bot className="w-12 h-12 mb-4 opacity-40" />
          <p className="text-lg font-medium">How can I help you today?</p>
          <p className="text-sm mt-1">Send a message to start the conversation</p>
        </div>
      ) : (
        <>
          {messages.map((msg) => (
            <MessageItem key={msg.id} message={msg} theme={theme} />
          ))}

          {/* Typing indicator */}
          {isLoading && typingContent && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="py-4"
            >
              <div className="max-w-3xl mx-auto flex gap-3 px-4">
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="flex-1">
                  <p className="text-xs font-medium text-slate-500 mb-1">Assistant</p>
                  <div className="prose prose-sm dark:prose-invert max-w-none text-slate-800 dark:text-slate-200">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={{
                        code({ node, inline, className, children, ...props }: any) {
                          const match = /language-(\w+)/.exec(className || "");
                          if (!inline && match) {
                            return (
                              <CodeBlock
                                language={match[1]}
                                value={String(children).replace(/\n$/, "")}
                                theme={theme}
                              />
                            );
                          }
                          return (
                            <code
                              className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-xs font-mono"
                              {...props}
                            >
                              {children}
                            </code>
                          );
                        },
                      }}
                    >
                      {typingContent}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* Simple loading dots when no content yet */}
          {isLoading && !typingContent && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="py-4"
            >
              <div className="max-w-3xl mx-auto flex gap-3 px-4">
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center shrink-0">
                  <Bot className="w-4 h-4 text-white" />
                </div>
                <div className="flex items-center gap-1 h-7">
                  <motion.div
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ repeat: Infinity, duration: 0.6, delay: 0 }}
                    className="w-2 h-2 rounded-full bg-slate-400"
                  />
                  <motion.div
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ repeat: Infinity, duration: 0.6, delay: 0.2 }}
                    className="w-2 h-2 rounded-full bg-slate-400"
                  />
                  <motion.div
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ repeat: Infinity, duration: 0.6, delay: 0.4 }}
                    className="w-2 h-2 rounded-full bg-slate-400"
                  />
                </div>
              </div>
            </motion.div>
          )}

          <div ref={bottomRef} />
        </>
      )}
    </div>
  );
}
