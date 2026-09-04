"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as React from "react";

import { useAuth, useMounted } from "@/components/auth-context";
import { cn } from "@/lib/utils";

const NAV = [
  {
    href: "/",
    label: "Home",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7">
        <path d="M3 10.5 10 3.5l7 7" />
        <path d="M5 9.5V16.5h10V9.5" />
      </svg>
    ),
  },
  {
    href: "/scan",
    label: "Scan",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7">
        <rect x="2.5" y="5.5" width="15" height="11" rx="2" />
        <circle cx="10" cy="11" r="3" />
        <path d="M7 5.5 8 3.5h4l1 2" />
      </svg>
    ),
  },
  {
    href: "/scans",
    label: "History",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7">
        <path d="M6.5 5h11M6.5 10h11M6.5 15h11" />
        <circle cx="3.5" cy="5" r="0.9" fill="currentColor" stroke="none" />
        <circle cx="3.5" cy="10" r="0.9" fill="currentColor" stroke="none" />
        <circle cx="3.5" cy="15" r="0.9" fill="currentColor" stroke="none" />
      </svg>
    ),
  },
  {
    href: "/reports",
    label: "Reports",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7">
        <path d="M5 2.5h6l4 4v11H5z" />
        <path d="M11 2.5V6.5h4M8 10.5h5M8 13.5h5" />
      </svg>
    ),
  },
  {
    href: "/settings",
    label: "More",
    icon: (
      <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7">
        <circle cx="10" cy="10" r="2.6" />
        <path d="M10 2.5v2.4M10 15.1v2.4M2.5 10h2.4M15.1 10h2.4M4.7 4.7l1.7 1.7M13.6 13.6l1.7 1.7M15.3 4.7l-1.7 1.7M6.4 13.6l-1.7 1.7" />
      </svg>
    ),
  },
];

export function Chrome({ children }: { children: React.ReactNode }): React.JSX.Element {
  const pathname = usePathname();
  const router = useRouter();
  const { session, signOut } = useAuth();
  const mounted = useMounted();
  const [query, setQuery] = React.useState("");

  if (pathname === "/login") {
    return <main className="grid min-h-screen place-items-center px-4 py-10">{children}</main>;
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-slate-900 text-white">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4">
          <Link href="/" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-md bg-white font-black text-slate-900">L</span>
            <span className="leading-tight">
              <span className="block text-[15px] font-bold">LMPC Scanner</span>
              <span className="block text-[10px] font-semibold tracking-widest text-slate-400">SIH26034 · LOCAL CPU</span>
            </span>
          </Link>
          <nav className="ml-6 hidden items-center gap-1 md:flex" aria-label="Primary">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-md px-3 py-2 text-sm font-semibold text-slate-300 hover:bg-white/10 hover:text-white",
                  pathname === item.href && "bg-white/15 text-white"
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
          {mounted && session && (
            <form
              className="hidden md:block"
              onSubmit={(e) => {
                e.preventDefault();
                router.push(`/scans?q=${encodeURIComponent(query)}`);
              }}
            >
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search products, brands…"
                aria-label="Search scans"
                className="w-52 rounded-md border border-white/20 bg-white/10 px-3 py-1.5 text-[13px] text-white placeholder:text-slate-400 focus:border-white/50 focus:outline-none"
              />
            </form>
          )}
            {mounted && session ? (
              <>
                <span className="hidden max-w-32 truncate text-[13px] font-semibold text-slate-200 sm:block">
                  {session.username}
                </span>
                <button onClick={signOut} className="rounded-md px-2.5 py-2 text-[13px] font-bold text-slate-300 hover:bg-white/10 hover:text-white">
                  Sign out
                </button>
              </>
            ) : (
              <Link href="/login" className="rounded-md px-2.5 py-2 text-[13px] font-bold text-slate-200 hover:bg-white/10">
                Sign in
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-4 pb-28 pt-4 md:px-7 md:pb-12 md:pt-6">{children}</main>

      <nav aria-label="Primary" className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        <div className="grid grid-cols-5">
          {NAV.map((item) => {
            const active = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex min-h-16 flex-col items-center justify-center gap-1 text-[11px] font-bold",
                  active ? "text-slate-900" : "text-slate-400"
                )}
              >
                <span className={cn("grid h-8 w-12 place-items-center rounded-full", active && "bg-slate-900 text-white")}>
                  {item.icon}
                </span>
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
