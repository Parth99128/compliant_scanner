import * as React from "react";

import { cn } from "@/lib/utils";

type Tone = "green" | "red" | "amber" | "slate" | "blue";

const tones: Record<Tone, string> = {
  green: "border-green-300 bg-green-50 text-green-800",
  red: "border-red-300 bg-red-50 text-red-800",
  amber: "border-amber-300 bg-amber-50 text-amber-900",
  slate: "border-slate-300 bg-slate-100 text-slate-700",
  blue: "border-sky-300 bg-sky-50 text-sky-900",
};

export function Badge({
  tone = "slate",
  children,
  className,
}: {
  tone?: Tone;
  children: React.ReactNode;
  className?: string;
}): React.JSX.Element {
  return (
    <span
      className={cn(
        "inline-flex items-center whitespace-nowrap rounded border px-2 py-0.5 text-[11px] font-bold uppercase tracking-wide",
        tones[tone],
        className
      )}
    >
      {children}
    </span>
  );
}

export function VerdictBadge({ verdict }: { verdict: string }): React.JSX.Element {
  if (verdict === "COMPLIANT") return <Badge tone="green">Compliant</Badge>;
  if (verdict === "INCOMPLETE") return <Badge tone="amber">Incomplete</Badge>;
  return <Badge tone="red">Non-compliant</Badge>;
}
