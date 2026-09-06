import Link from "next/link";
import * as React from "react";

/** Senior, calm page header: title + description + optional actions. No eyebrow labels. */
export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}): React.JSX.Element {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3 border-b border-slate-200 pb-3">
      <div>
        <h1 className="font-display text-2xl font-black tracking-tight text-navy-950">{title}</h1>
        {description ? <p className="mt-1 max-w-2xl text-[13px] text-slate-500">{description}</p> : null}
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function NewScanButton(): React.JSX.Element {
  return (
    <Link
      href="/scan"
      className="rounded-md bg-saffron-500 px-4 py-2.5 text-sm font-bold text-navy-950 shadow-sm transition-all hover:-translate-y-0.5 hover:bg-saffron-600 hover:text-white"
    >
      + New scan
    </Link>
  );
}
