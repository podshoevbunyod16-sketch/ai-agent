/**
 * useTheme hook — dark/light/system theme management.
 * Persists choice in localStorage. Defaults to system preference.
 */
import { useState, useEffect, useCallback } from "react";
import type { Theme } from "@/types";

const STORAGE_KEY = "ai-chat-theme";

function getSystemTheme(): "dark" | "light" {
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function getStoredTheme(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "dark" || stored === "light" || stored === "system") {
    return stored;
  }
  return "system";
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => getStoredTheme());

  const resolved = theme === "system" ? getSystemTheme() : theme;

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove("dark", "light");
    root.classList.add(resolved);
  }, [resolved]);

  // Listen for system theme changes
  useEffect(() => {
    if (theme !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      // Force re-render
      setThemeState("system");
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  const setTheme = useCallback((t: Theme) => {
    localStorage.setItem(STORAGE_KEY, t);
    setThemeState(t);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(resolved === "dark" ? "light" : "dark");
  }, [resolved, setTheme]);

  return { theme, resolved, setTheme, toggleTheme };
}
