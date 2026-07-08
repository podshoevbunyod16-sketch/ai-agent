/**
 * useAPI hook — typed API client with Firebase token injection.
 */
import { useCallback } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

interface FetchOptions {
  method?: string;
  body?: any;
  token?: string | null;
}

export function useAPI() {
  const request = useCallback(
    async <T = any>(path: string, opts: FetchOptions = {}): Promise<T> => {
      const url = `${API_URL}${path}`;
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (opts.token) {
        headers["Authorization"] = `Bearer ${opts.token}`;
      }

      const res = await fetch(url, {
        method: opts.method || "GET",
        headers,
        body: opts.body ? JSON.stringify(opts.body) : undefined,
      });

      if (!res.ok) {
        const err = await res.text();
        throw new Error(`HTTP ${res.status}: ${err}`);
      }
      return await res.json();
    },
    []
  );

  return { request };
}

/**
 * SSE chat stream handler.
 * Returns an async generator that yields parsed SSE events.
 */
export async function* chatStream(
  body: {
    conversation_id?: number | null;
    message: string;
    provider?: string;
    model?: string;
    branch_id?: number | null;
  },
  token: string | null
): AsyncGenerator<any, void, unknown> {
  const url = `${API_URL}/api/chat`;
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Chat error ${res.status}: ${err}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith("data: ")) {
        const data = trimmed.slice(6);
        if (data === "[DONE]") continue;
        try {
          yield JSON.parse(data);
        } catch {
          // skip unparseable
        }
      }
    }
  }
}
