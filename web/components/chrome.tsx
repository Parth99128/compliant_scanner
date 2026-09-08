"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import * as React from "react";

import { useAuth, useMounted } from "@/components/auth-context";
import { GovStrip, Icon } from "@/components/ui/ministry";
import { cn } from "@/lib/utils";

const NAV: { href: string; label: string; icon: "home" | "camera" | "list" | "file" | "gear" }[] = [
  { href: "/", label: "Home", icon: "home" },
  { href: "/scan", label: "Scan", icon: "camera" },
  { href: "/scans", label: "History", icon: "list" },
  { href: "/reports", label: "Reports", icon: "file" },
  { href: "/settings", label: "More", icon: "gear" },
];

const PUBLIC_NAV = [
  { href: "#how", label: "How it works" },
  { href: "#features", label: "Features" },
  { href: "#rules", label: "The Rules" },
  { href: "#faq", label: "FAQ" },
];

function Emblem({ size = "h-10 w-10" }: { size?: string }): React.JSX.Element {
  return (
    // Logo artwork: circular crop keeps the scanner-D mark, wordmark below it is cropped out.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/drishti-logo.jpg"
      alt="DrishtiLM logo"
      className={cn(
        size,
        "flex-none rounded-full border-2 border-gold object-cover object-[50%_36%] shadow-[0_0_12px_rgba(246,139,31,0.45)]"
      )}
    />
  );
}

function Wordmark({ compact = false }: { compact?: boolean }): React.JSX.Element {
  return (
    <span className="leading-tight">
      <span className={cn("block font-display font-black tracking-tight text-white", compact ? "text-[15px]" : "text-[17px]")}>
        Drishti<span className="bg-gradient-to-r from-sky-400 to-green-400 bg-clip-text text-transparent">LM</span>
      </span>
      <span className="block text-[10px] font-semibold tracking-wide text-slate-300">
        LMPC Compliance Scanner · SIH26034
      </span>
    </span>
  );
}

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

export function Chrome({ children }: { children: React.ReactNode }): React.JSX.Element {
  const pathname = usePathname();
  const router = useRouter();
  const { session, signOut } = useAuth();
  const mounted = useMounted();
  const [query, setQuery] = React.useState("");

  return (
    <div className="flex min-h-screen flex-col bg-paper">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:text-sm focus:font-bold"
      >
        Skip to main content
      </a>
      <GovStrip />
      <header className="sticky top-0 z-40 bg-navy-900 text-white shadow-[0_2px_12px_rgba(7,28,51,0.45)]">
        <div className="mx-auto flex min-h-16 max-w-6xl items-center gap-3 px-4 py-2 md:px-7">
          <Link href="/" className="flex items-center gap-2.5" aria-label="DrishtiLM home">
            <Emblem />
            <span>
              <Wordmark />
              <span className="mt-0.5 hidden border-l-2 border-gold pl-2 text-[10px] font-bold uppercase tracking-[0.16em] text-gold sm:block">
                Field Console
              </span>
            </span>
          </Link>

          {mounted && session ? (
            <>
              <nav className="ml-6 hidden items-center gap-1 md:flex" aria-label="Primary">
                {NAV.map((item) => {
                  const active = isActive(pathname, item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold transition-colors",
                        active ? "bg-white/15 text-white shadow-[inset_0_-3px_0_0_var(--color-gold)]" : "text-slate-300 hover:bg-white/10 hover:text-white"
                      )}
                    >
                      <Icon name={item.icon} size={16} />
                      {item.label}
                    </Link>
                  );
                })}
              </nav>
              <div className="ml-auto flex items-center gap-2">
                <form
                  className="hidden md:block"
                  onSubmit={(e) => {
                    e.preventDefault();
                    router.push(`/scans?q=${encodeURIComponent(query)}`);
                  }}
                >
                  <div className="relative">
                    <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400">
                      <Icon name="search" size={14} />
                    </span>
                    <input
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Search products, brands…"
                      aria-label="Search scans"
                      className="w-52 rounded-lg border border-white/20 bg-white/10 py-1.5 pl-8 pr-3 text-[13px] text-white placeholder:text-slate-400 focus:border-gold focus:outline-none"
                    />
                  </div>
                </form>
                <span className="hidden items-center gap-2 rounded-full border border-white/15 bg-white/10 py-1 pl-1 pr-3 sm:flex" title={session.username}>
                  <span className="grid h-6 w-6 place-items-center rounded-full bg-gold text-[11px] font-black text-navy-950">
                    {session.username.slice(0, 1).toUpperCase()}
                  </span>
                  <span className="max-w-28 truncate text-[13px] font-semibold text-slate-200">{session.username}</span>
                </span>
                <button
                  onClick={signOut}
                  title="Sign out"
                  aria-label="Sign out"
                  className="flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-[13px] font-bold text-slate-300 transition-colors hover:bg-white/10 hover:text-white"
                >
                  <Icon name="logout" size={16} />
                  <span className="hidden lg:inline">Sign out</span>
                </button>
              </div>
            </>
          ) : (
            <div className="ml-auto flex items-center gap-1 sm:gap-2">
              {pathname === "/" && (
                <nav className="mr-1 hidden items-center gap-1 lg:flex" aria-label="Public">
                  {PUBLIC_NAV.map((item) => (
                    <a
                      key={item.href}
                      href={item.href}
                      className="rounded-md px-3 py-2 text-sm font-semibold text-slate-300 hover:bg-white/10 hover:text-white"
                    >
                      {item.label}
                    </a>
                  ))}
                </nav>
              )}
              {mounted && !session && pathname !== "/login" && (
                <Link
                  href="/login"
                  className="flex items-center gap-1.5 rounded-lg bg-saffron-500 px-4 py-2 text-sm font-bold text-navy-950 shadow-sm transition-colors hover:bg-saffron-600 hover:text-white"
                >
                  <Icon name="idcard" size={16} />
                  Officer sign in
                </Link>
              )}
            </div>
          )}
        </div>
        <div className="tricolor-bar h-1" aria-hidden="true" />
      </header>

      <main id="main-content" className="mx-auto w-full max-w-6xl flex-1 px-4 pb-28 pt-4 md:px-7 md:pb-12 md:pt-6">
        {pathname === "/login" ? (
          <div className="grid min-h-[62vh] place-items-center px-2 py-8 sm:px-4">{children}</div>
        ) : (
          children
        )}
      </main>

      {mounted && session && (
        <nav aria-label="Primary" className="fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
          <div className="grid grid-cols-5">
            {NAV.map((item) => {
              const active = isActive(pathname, item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex min-h-16 flex-col items-center justify-center gap-1 text-[11px] font-bold",
                    active ? "text-navy-900" : "text-slate-400"
                  )}
                >
                  <span className={cn("grid h-8 w-12 place-items-center rounded-full", active && "bg-navy-900 text-white")}>
                    <Icon name={item.icon} size={18} />
                  </span>
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>
      )}

      <footer className="mt-auto bg-navy-950 text-slate-300">
        <div className="tricolor-bar h-1" aria-hidden="true" />
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-8 px-4 py-10 sm:grid-cols-2 md:grid-cols-4 md:px-7">
          <div className="sm:col-span-2 md:col-span-1">
            <p className="flex items-center gap-2.5">
              <Emblem size="h-11 w-11" />
              <Wordmark compact />
            </p>
            <p className="mt-3 text-[13px] leading-relaxed text-slate-400">
              CPU-only label inspection for the Legal Metrology (Packaged Commodities) Rules, 2011.
            </p>
            <p className="mt-1 font-display text-sm font-bold text-gold">सही माप, हर पैकेट.</p>
          </div>
          <nav aria-label="Footer">
            <p className="mb-3 border-b-2 border-gold/60 pb-1.5 text-xs font-bold uppercase tracking-[0.16em] text-white">Portals</p>
            <ul className="space-y-2 text-[13px]">
              {[
                ["/", "Home"],
                ["/scan", "New scan"],
                ["/scans", "Scan history"],
                ["/reports", "Reports"],
              ].map(([href, label]) => (
                <li key={href}>
                  <Link href={href} className="text-slate-400 transition-colors hover:text-gold hover:underline">
                    {label}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          <nav aria-label="Rules">
            <p className="mb-3 border-b-2 border-gold/60 pb-1.5 text-xs font-bold uppercase tracking-[0.16em] text-white">The Rules</p>
            <ul className="space-y-2 text-[13px] text-slate-400">
              <li>Rule 6 · Mandatory declarations</li>
              <li>Rule 7 · Print-size minima</li>
              <li className="text-slate-500">“Verified” citations checked vs Gazette text.</li>
            </ul>
          </nav>
          <div>
            <p className="mb-3 border-b-2 border-gold/60 pb-1.5 text-xs font-bold uppercase tracking-[0.16em] text-white">Citizen help</p>
            <p className="flex items-center gap-2 text-[13px]">
              <Icon name="phone" size={15} />
              National Consumer Helpline: <span className="font-black text-white">1915</span>
            </p>
            <p className="mt-2 text-[13px] leading-relaxed text-slate-400">
              Department of Consumer Affairs, Government of India.
            </p>
          </div>
        </div>
        <div className="border-t border-white/10">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-2 px-4 py-3 text-[11px] text-slate-500 md:px-7">
            <span className="rounded border border-gold/60 px-1.5 py-0.5 font-bold uppercase tracking-wider text-gold">
              SIH 2026 demo prototype
            </span>
            <span>Not an official government portal. Unverified citations need legal review before enforcement use.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
