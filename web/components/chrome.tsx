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

const PUBLIC_NAV = [
  { href: "#how", label: "How it works" },
  { href: "#features", label: "Features" },
  { href: "#rules", label: "The Rules" },
  { href: "#faq", label: "FAQ" },
];

function Emblem(): React.JSX.Element {
  return (
    // Logo artwork: circular crop keeps the scanner-D mark, wordmark below it is cropped out.
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src="/drishti-logo.jpg"
      alt="DrishtiLM logo"
      className="h-10 w-10 flex-none rounded-full border-2 border-gold object-cover object-[50%_36%] shadow-[0_0_12px_rgba(246,139,31,0.45)]"
    />
  );
}

function Wordmark({ compact = false }: { compact?: boolean }): React.JSX.Element {
  return (
    <span className="leading-tight">
      <span className={`block font-display font-black tracking-tight text-white ${compact ? "text-[15px]" : "text-[17px]"}`}>
        Drishti<span className="bg-gradient-to-r from-sky-400 to-green-400 bg-clip-text text-transparent">LM</span>
      </span>
      <span className="block text-[10px] font-semibold tracking-wide text-slate-300">
        LMPC Compliance Scanner · SIH26034
      </span>
    </span>
  );
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
      <div className="tricolor-bar h-1.5" aria-hidden="true" />
      <header className="sticky top-0 z-40 border-b border-navy-950 bg-navy-900 text-white shadow-md">
        <div className="mx-auto flex min-h-16 max-w-6xl items-center gap-3 px-4 py-2">
          <Link href="/" className="flex items-center gap-2.5" aria-label="DrishtiLM home">
            <Emblem />
            <Wordmark />
          </Link>

          {mounted && session ? (
            <>
              <nav className="ml-6 hidden items-center gap-1 md:flex" aria-label="Primary">
                {NAV.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={pathname === item.href ? "page" : undefined}
                    className={cn(
                      "rounded-md px-3 py-2 text-sm font-semibold text-slate-300 hover:bg-white/10 hover:text-white",
                      pathname === item.href && "bg-white/15 text-white shadow-[inset_0_-3px_0_0_var(--color-saffron-500)]"
                    )}
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
              <div className="ml-auto flex items-center gap-2">
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
                    className="w-52 rounded-md border border-white/20 bg-white/10 px-3 py-1.5 text-[13px] text-white placeholder:text-slate-400 focus:border-saffron-500 focus:outline-none"
                  />
                </form>
                <span className="hidden max-w-32 truncate text-[13px] font-semibold text-slate-200 sm:block">
                  {session.username}
                </span>
                <button onClick={signOut} className="rounded-md px-2.5 py-2 text-[13px] font-bold text-slate-300 hover:bg-white/10 hover:text-white">
                  Sign out
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
                  className="rounded-md bg-saffron-500 px-4 py-2 text-sm font-bold text-navy-950 shadow-sm transition-colors hover:bg-saffron-600 hover:text-white"
                >
                  Officer sign in
                </Link>
              )}
            </div>
          )}
        </div>
      </header>

      <main id="main-content" className="mx-auto w-full max-w-6xl flex-1 px-4 pb-28 pt-4 md:px-7 md:pb-12 md:pt-6">
        {pathname === "/login" ? (
          <div className="grid min-h-[60vh] place-items-center px-4 py-10">{children}</div>
        ) : (
          children
        )}
      </main>

      {mounted && session && (
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
                    active ? "text-navy-900" : "text-slate-400"
                  )}
                >
                  <span className={cn("grid h-8 w-12 place-items-center rounded-full", active && "bg-navy-900 text-white")}>
                    {item.icon}
                  </span>
                  {item.label}
                </Link>
              );
            })}
          </div>
        </nav>
      )}

      <footer className="mt-auto border-t-4 border-saffron-500 bg-navy-950 text-slate-300">
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-4 py-8 text-sm md:grid-cols-3 md:px-7">
          <div>
            <p className="flex items-center gap-2.5">
              <Emblem />
              <Wordmark compact />
            </p>
            <p className="mt-2 text-[13px] leading-relaxed text-slate-400">
              CPU-only label inspection for the Legal Metrology (Packaged Commodities) Rules, 2011.
              सही माप, हर पैकेट.
            </p>
          </div>
          <nav aria-label="Footer">
            <p className="mb-2 text-xs font-bold uppercase tracking-widest text-slate-500">Portals</p>
            <ul className="space-y-1.5 text-[13px]">
              <li><Link href="/" className="hover:text-white hover:underline">Home</Link></li>
              <li><Link href="/scan" className="hover:text-white hover:underline">New scan</Link></li>
              <li><Link href="/scans" className="hover:text-white hover:underline">Scan history</Link></li>
              <li><Link href="/reports" className="hover:text-white hover:underline">Reports</Link></li>
            </ul>
          </nav>
          <div>
            <p className="mb-2 text-xs font-bold uppercase tracking-widest text-slate-500">Citizen help</p>
            <p className="text-[13px] leading-relaxed">
              National Consumer Helpline: <span className="font-bold text-white">1915</span>
              <br />
              Rule citations marked “Verified” were checked against the official Gazette text.
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
