"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth, useMounted } from "@/components/auth-context";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/scan", label: "New scan" },
  { href: "/scans", label: "Scan history" },
  { href: "/reports", label: "Reports" },
  { href: "/settings", label: "Settings" },
];

export function Sidebar(): React.JSX.Element {
  const pathname = usePathname();
  const { session, signOut } = useAuth();
  const mounted = useMounted();
  return (
    <aside className="flex h-screen w-60 shrink-0 flex-col bg-slate-900 text-slate-200">
      <div className="border-b border-white/10 px-5 pb-4 pt-5">
        <p className="text-[11px] font-bold uppercase tracking-widest text-slate-400">SIH26034 · Local CPU</p>
        <p className="mt-1 text-base font-bold text-white">LMPC Scanner</p>
      </div>
      <nav className="flex flex-col gap-1 p-3">
        <p className="px-2 pb-1 pt-2 text-[11px] font-bold uppercase tracking-widest text-slate-500">Inspect</p>
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "rounded-md border-l-2 px-3 py-2 text-sm font-semibold text-slate-300 hover:bg-white/5 hover:text-white",
              pathname === item.href ? "border-white bg-white/10 text-white" : "border-transparent"
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="mt-auto border-t border-white/10 p-4 text-xs text-slate-400">
        {!mounted || !session ? (
          <Link href="/login" className="font-semibold text-slate-200 hover:underline">
            Sign in
          </Link>
        ) : (
          <div className="flex items-center justify-between gap-2">
            <span className="truncate font-semibold text-slate-200">{session.username}</span>
            <button onClick={signOut} className="font-semibold text-slate-300 hover:text-white hover:underline">
              Sign out
            </button>
          </div>
        )}
        <p className="mt-2 leading-relaxed">Tesseract CPU · spaCy NER · Rule 7 verified. No cloud calls.</p>
      </div>
    </aside>
  );
}
