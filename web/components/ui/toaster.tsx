"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

interface Toast {
  id: number;
  title: string;
  body?: string;
  tone: "error" | "info";
}

const Ctx = React.createContext<{ push: (t: Omit<Toast, "id">) => void } | null>(null);

let nextId = 1;

export function ToasterProvider({ children }: { children: React.ReactNode }): React.JSX.Element {
  const [toasts, setToasts] = React.useState<Toast[]>([]);

  const push = React.useCallback((t: Omit<Toast, "id">) => {
    const id = nextId++;
    setToasts((prev) => [...prev.slice(-2), { ...t, id }]);
    window.setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), 6000);
  }, []);

  const value = React.useMemo(() => ({ push }), [push]);

  return (
    <Ctx.Provider value={value}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={cn(
              "pointer-events-auto rounded-md border bg-white p-3 shadow-lg",
              t.tone === "error" ? "border-red-300" : "border-slate-200"
            )}
          >
            <p className={cn("text-sm font-bold", t.tone === "error" ? "text-red-800" : "text-slate-900")}>{t.title}</p>
            {t.body ? <p className="mt-0.5 text-xs text-slate-600">{t.body}</p> : null}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): { push: (t: Omit<Toast, "id">) => void; notifyError: (e: unknown, fallback: string) => void } {
  const ctx = React.useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used inside ToasterProvider");
  const push = ctx.push;
  const notifyError = React.useCallback(
    (e: unknown, fallback: string) => {
      const msg = e instanceof Error ? e.message : fallback;
      push({ title: "Request failed", body: msg.slice(0, 240), tone: "error" });
    },
    [push]
  );
  return { push, notifyError };
}
