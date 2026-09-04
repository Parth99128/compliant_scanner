"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import * as React from "react";

import { Sidebar } from "@/components/sidebar";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/scan", label: "New scan" },
  { href: "/scans", label: "Scans" },
  { href: "/reports", label: "Reports" },
  { href: "/settings", label: "Settings" },
];

export function Chrome({ children }: { children: React.ReactNode }): React.JSX.Element {
  const pathname = usePathname();
  if (pathname === "/login") {
    return <main className="grid min-h-screen place-items-center px-4 py-10">{children}</main>;
  }
  return (
    <div className="min-h-screen md:flex">
      <div className="hidden md:block">
        <Sidebar />
      </div>
      <nav className="flex items-center gap-1 overflow-x-auto border-b border-slate-800 bg-slate-900 px-3 py-2 md:hidden">
        <span className="mr-2 shrink-0 text-sm font-bold text-white">LMPC</span>
        {NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "shrink-0 rounded px-2.5 py-1.5 text-[13px] font-semibold text-slate-300",
              pathname === item.href && "bg-white/10 text-white"
            )}
          >
            {item.label}
          </Link>
        ))}
      </nav>
      <main className="min-w-0 flex-1 px-4 py-4 md:px-7 md:py-6">{children}</main>
    </div>
  );
}
