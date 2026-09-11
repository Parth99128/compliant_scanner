"use client";

import Link from "next/link";
import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/* Icons: single-stroke official set (no emoji, no external assets).   */
/* ------------------------------------------------------------------ */

const PATHS: Record<string, React.ReactNode> = {
  home: (<><path d="M4 11 12 4l8 7" /><path d="M6.5 9.5V20h11V9.5" /></>),
  camera: (<><rect x="3" y="7" width="18" height="13" rx="2.5" /><circle cx="12" cy="13" r="3.5" /><path d="M8.5 7 9.8 4.5h4.4L15.5 7" /></>),
  bolt: <path d="M13 2 4.5 13.5H11L10 22l8.5-11.5H12L13 2Z" />,
  upload: (<><path d="M12 16V4m0 0 5 5m-5-5L7 9" /><path d="M4 20h16" /></>),
  search: (<><circle cx="11" cy="11" r="7" /><path d="m20 20-3.8-3.8" /></>),
  file: (<><path d="M6 2.5h8l5 5v14H6z" /><path d="M14 2.5V7.5h5M9 13h6M9 16.5h6" /></>),
  chart: (<><path d="M4 20V10m6 10V4m6 16v-7" /></>),
  shield: (<><path d="M12 2.5 20 6v6c0 5-3.5 8.2-8 9.5C7.5 20.2 4 17 4 12V6l8-3.5Z" /><path d="m9 11.5 2.2 2.2L15.5 9" /></>),
  check: <path d="m4.5 12.5 5 5L19.5 7" />,
  alert: (<><path d="M12 3.5 22 20H2L12 3.5Z" /><path d="M12 9.5v5" /><circle cx="12" cy="17.2" r="0.4" fill="currentColor" /></>),
  clock: (<><circle cx="12" cy="12" r="8.5" /><path d="M12 7.5V12l3.5 2" /></>),
  scale: (<><path d="M12 3v18M5 21h14M12 5 5 7m7-2 7 2" /><path d="M2.5 13 5 18a2.8 2.8 0 0 1-5 0l2.5-5Zm14 0L19 18a2.8 2.8 0 0 0 5 0l-2.5-5Z" /></>),
  tag: (<><path d="M3.5 12V4.5A1 1 0 0 1 4.5 3.5H12L20.5 12a1.4 1.4 0 0 1 0 2L14 20.5a1.4 1.4 0 0 1-2 0L3.5 12Z" /><circle cx="8.5" cy="8.5" r="1.2" /></>),
  calendar: (<><rect x="3.5" y="5" width="17" height="16" rx="2" /><path d="M3.5 9.5h17M8 2.5V6m8-3.5V6" /></>),
  pin: (<><path d="M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.8 12 21 12 21Z" /><circle cx="12" cy="9.5" r="2.5" /></>),
  download: (<><path d="M12 4v12m0 0 5-5m-5 5-5-5" /><path d="M4 20h16" /></>),
  user: (<><circle cx="12" cy="8" r="4" /><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0" /></>),
  logout: (<><path d="M14 4H6v16h8" /><path d="m10 12 7 0m0 0 4-4m-4 4 4 4" /></>),
  list: (<><path d="M8.5 6h12M8.5 12h12M8.5 18h12" /><circle cx="4.5" cy="6" r="1" fill="currentColor" stroke="none" /><circle cx="4.5" cy="12" r="1" fill="currentColor" stroke="none" /><circle cx="4.5" cy="18" r="1" fill="currentColor" stroke="none" /></>),
  gear: (<><circle cx="12" cy="12" r="3" /><path d="M12 2.8v2.6m0 13.2v2.6M2.8 12h2.6m13.2 0h2.6M5.2 5.2l1.8 1.8m10 10 1.8 1.8m0-13.6-1.8 1.8m-10 10-1.8 1.8" /></>),
  eye: (<><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z" /><circle cx="12" cy="12" r="3" /></>),
  refresh: (<><path d="M20 12a8 8 0 1 1-2.3-5.6" /><path d="M20 3.5V8h-4.5" /></>),
  plus: <path d="M12 5v14M5 12h14" />,
  phone: (<><path d="M5 4h4l2 5-2.5 1.5a12 12 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z" /></>),
  bank: (<><path d="m3 9.5 9-6 9 6" /><path d="M4.5 9.5V19m4-9.5V19m3.5-9.5V19m4-9.5V19M2.5 19.5h19M2.5 21.5h19" /></>),
  idcard: (<><rect x="2.5" y="5" width="19" height="14" rx="2" /><circle cx="8" cy="11" r="2" /><path d="M5 16.5a3.2 3.2 0 0 1 6 0M14 9.5h5.5M14 13h5.5" /></>),
  db: (<><ellipse cx="12" cy="5.5" rx="8" ry="3" /><path d="M4 5.5v13c0 1.7 3.6 3 8 3s8-1.3 8-3v-13" /><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></>),
};

export function Icon({ name, size = 18 }: { name: keyof typeof PATHS; size?: number }): React.JSX.Element {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="flex-none"
    >
      {PATHS[name]}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* Government utility strip (above the header).                        */
/* ------------------------------------------------------------------ */

export function GovStrip(): React.JSX.Element {
  return (
    <div className="bg-navy-950 text-slate-300">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-1 px-4 py-1.5 text-[11px] font-semibold tracking-wide md:px-7">
        <span className="flex items-center gap-1.5">
          <Icon name="bank" size={13} />
          भारत सरकार · Government of India
        </span>
        <span className="hidden text-slate-500 sm:inline">|</span>
        <span className="hidden sm:inline">Legal Metrology Division · Field Console</span>
        <span className="ml-auto flex items-center gap-1.5">
          <Icon name="phone" size={13} />
          Consumer Helpline <span className="font-bold text-white">1915</span>
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Hero: navy masthead with gold rule, kicker, title, actions + meta.  */
/* ------------------------------------------------------------------ */

export function Hero({
  kicker,
  kickerHi,
  title,
  description,
  actions,
  meta,
  tone = "navy",
}: {
  kicker: string;
  kickerHi?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
  meta?: React.ReactNode;
  tone?: "navy" | "green" | "red" | "amber";
}): React.JSX.Element {
  const tones: Record<string, string> = {
    navy: "from-navy-950 via-navy-900 to-navy-800",
    green: "from-[#062d16] via-[#0b5523] to-[#0e6b2e]",
    red: "from-[#3d0a0d] via-[#7a1216] to-[#a4262c]",
    amber: "from-[#3a2a04] via-[#7a5b06] to-[#a87900]",
  };
  return (
    <section className={cn("relative overflow-hidden rounded-xl bg-gradient-to-br text-white shadow-md", tones[tone])}>
      <div className="tricolor-bar absolute inset-x-0 top-0 h-1" aria-hidden="true" />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-16 -top-24 h-64 w-64 rounded-full bg-white/[0.06]"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-28 right-24 h-56 w-56 rounded-full bg-white/[0.04]"
      />
      <div className="relative px-5 py-6 md:px-8 md:py-8">
        <p className="flex flex-wrap items-center gap-x-2 text-[11px] font-bold uppercase tracking-[0.18em] text-gold">
          <span className="inline-block h-px w-8 bg-gold" aria-hidden="true" />
          {kicker}
          {kickerHi ? <span className="font-semibold normal-case tracking-normal text-slate-300">· {kickerHi}</span> : null}
        </p>
        <h1 className="mt-2 font-display text-2xl font-black leading-tight tracking-tight md:text-[32px]">
          {title}
        </h1>
        {description ? <p className="mt-2 max-w-2xl text-[13px] leading-relaxed text-slate-300 md:text-sm">{description}</p> : null}
        {(actions || meta) && (
          <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-3">
            {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
            {meta ? <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-300">{meta}</div> : null}
          </div>
        )}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Panel: white section card with header.                              */
/* ------------------------------------------------------------------ */

export function Panel({
  title,
  description,
  actions,
  children,
  className,
}: {
  title?: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}): React.JSX.Element {
  return (
    <section className={cn("rounded-xl border border-slate-200 bg-white shadow-sm", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-2 border-b border-slate-100 px-5 pb-3 pt-4">
          <div>
            {title ? <h2 className="font-display text-[17px] font-black tracking-tight text-navy-950">{title}</h2> : null}
            {description ? <p className="mt-0.5 text-xs text-slate-500">{description}</p> : null}
          </div>
          {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
        </header>
      )}
      <div className="px-5 py-4">{children}</div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* StatCard: icon + label + big value + link.                          */
/* ------------------------------------------------------------------ */

export function StatCard({
  icon,
  label,
  value,
  sub,
  href,
  tone,
}: {
  icon: keyof typeof PATHS;
  label: string;
  value: React.ReactNode;
  sub?: string;
  href?: string;
  tone?: "navy" | "green" | "red" | "amber";
}): React.JSX.Element {
  const chips: Record<string, string> = {
    navy: "bg-navy-900 text-white",
    green: "bg-igreen-700 text-white",
    red: "bg-red-700 text-white",
    amber: "bg-saffron-500 text-navy-950",
  };
  const body = (
    <>
      <span className={cn("grid h-10 w-10 place-items-center rounded-lg shadow-sm", chips[tone ?? "navy"])}>
        <Icon name={icon} size={20} />
      </span>
      <span className="mt-3 block text-[11px] font-bold uppercase tracking-[0.14em] text-slate-500">{label}</span>
      <span className="mt-1 block font-display text-[32px] font-black leading-none tabular-nums text-navy-950">{value}</span>
      {sub ? <span className="mt-1.5 block text-[11px] font-semibold text-slate-400">{sub}</span> : null}
    </>
  );
  const cls =
    "group block rounded-xl border border-slate-200 bg-white p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:border-navy-100 hover:shadow-md";
  return href ? (
    <Link href={href} className={cls}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}

/* ------------------------------------------------------------------ */
/* EmptyState + shared input class.                                    */
/* ------------------------------------------------------------------ */

export function EmptyState({
  icon = "search",
  title,
  body,
  action,
}: {
  icon?: keyof typeof PATHS;
  title: string;
  body?: string;
  action?: React.ReactNode;
}): React.JSX.Element {
  return (
    <div className="flex flex-col items-center px-6 py-10 text-center">
      <span className="grid h-14 w-14 place-items-center rounded-full border border-dashed border-navy-100 bg-navy-50 text-navy-800">
        <Icon name={icon} size={26} />
      </span>
      <p className="mt-3 font-display text-base font-black text-navy-950">{title}</p>
      {body ? <p className="mt-1 max-w-sm text-[13px] text-slate-500">{body}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export const inputCls =
  "w-full rounded-lg border border-slate-300 bg-white px-3.5 py-2.5 text-sm text-slate-900 shadow-sm placeholder:text-slate-400 hover:border-slate-400 focus:border-navy-700 focus:outline-none focus:ring-2 focus:ring-navy-100";

export const labelCls = "mb-1.5 block text-[13px] font-bold text-slate-700";

/* ------------------------------------------------------------------ */
/* SegmentedControl: icon tabs (scan methods, auth modes).             */
/* ------------------------------------------------------------------ */

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string; hint?: string; icon: keyof typeof PATHS }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}): React.JSX.Element {
  return (
    <div role="tablist" aria-label={label} className="grid grid-cols-3 gap-1 rounded-xl border border-navy-100 bg-navy-50 p-1">
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(o.value)}
            className={cn(
              "flex flex-col items-center gap-0.5 rounded-lg px-2 py-2.5 text-xs font-bold transition-all",
              active ? "bg-navy-900 text-white shadow" : "text-slate-500 hover:bg-white hover:text-navy-900"
            )}
          >
            <Icon name={o.icon} size={18} />
            {o.label}
            {o.hint ? (
              <span className={cn("text-[10px] font-semibold", active ? "text-slate-300" : "text-slate-400")}>{o.hint}</span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* SourceBadge: Phase D provenance chip — how a declaration value was  */
/* obtained. read = regex straight off the text; inferred = NER/       */
/* gazetteer/layout filled a gap; ai_assist = second-opinion model;    */
/* uncertain = weak read, verify; measured = Rule 7 spatial scale.     */
/* ------------------------------------------------------------------ */

const SOURCE_META: Record<string, { tone: "slate" | "amber" | "blue" | "green"; label: string }> = {
  read: { tone: "slate", label: "Read" },
  inferred: { tone: "amber", label: "Inferred · verify" },
  ai_assist: { tone: "blue", label: "AI assist" },
  uncertain: { tone: "amber", label: "Uncertain read" },
  attested: { tone: "green", label: "Officer-set" },
  measured: { tone: "blue", label: "Measured" },
};

const RULE_SOURCE_KEYS: Record<string, string[]> = {
  "LMPC-6.1-manufacturer": ["manufacturer_name"],
  "LMPC-6.1-generic": ["generic_name"],
  "LMPC-6.1-netqty": ["net_quantity_value"],
  "LMPC-6.1-mrp": ["mrp"],
  "LMPC-6.1-dates": ["mfg_date", "expiry_date"],
  "LMPC-6.1-care": ["consumer_care"],
  "LMPC-6.1-origin": ["country_of_origin"],
};

const SOURCE_PRIORITY = ["attested", "ai_assist", "uncertain", "inferred", "read", "measured"] as const;

export function sourceForRule(
  ruleId: string,
  declaration: Record<string, unknown> | undefined,
  measured: boolean
): string {
  if (ruleId === "LMPC-7.2-numeral" || ruleId === "LMPC-7.3-letter" || ruleId === "LMPC-7.3-width") {
    return measured ? "measured" : "";
  }
  const sources = (declaration?.["field_sources"] ?? {}) as Record<string, unknown>;
  const keys = RULE_SOURCE_KEYS[ruleId] ?? [];
  const found = keys
    .map((k) => (typeof sources[k] === "string" ? (sources[k] as string) : ""))
    .filter(Boolean);
  for (const want of SOURCE_PRIORITY) {
    if (found.includes(want)) return want;
  }
  return found[0] ?? "";
}

export function SourceBadge({ source }: { source: string }): React.JSX.Element | null {
  const meta = SOURCE_META[source];
  if (!meta) return null;
  return <Badge tone={meta.tone}>{meta.label}</Badge>;
}
