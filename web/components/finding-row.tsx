"use client";

import * as React from "react";

import { Badge } from "@/components/ui/badge";
import { ApiError, attestFinding, type Check } from "@/lib/api";
import { cn } from "@/lib/utils";

// Friendly Rule 6 titles (mockup wording); citations stay verbatim.
const TITLES: Record<string, string> = {
  "LMPC-6.1-manufacturer": "Manufacturer / Packer / Importer name & address",
  "LMPC-6.1-generic": "Common / generic name of commodity",
  "LMPC-6.1-netqty": "Net quantity (standard unit)",
  "LMPC-6.1-mrp": "Maximum retail price (inclusive of all taxes)",
  "LMPC-6.1-dates": "Month & year of manufacture / packing / import",
  "LMPC-6.1-care": "Customer care contact",
  "LMPC-6.1-origin": "Country of origin",
};

export const EDITABLE_RULES = new Set(Object.keys(TITLES));

function displayObserved(check: Check): string {
  const o = check.observed ?? "";
  return o === "absent" || o === "unmeasured" ? "" : o;
}

export function FindingRow({
  scanId,
  token,
  check,
  onChanged,
  onError,
}: {
  scanId: string;
  token: string;
  check: Check;
  onChanged: () => void;
  onError: (e: unknown, fallback: string) => void;
}): React.JSX.Element {
  const [text, setText] = React.useState(() => displayObserved(check));
  const [checked, setChecked] = React.useState(check.status === "PASS");
  const [saving, setSaving] = React.useState(false);
  const [savedTick, setSavedTick] = React.useState(false);

  // Fresh server state (post-save refetch) resets the row editors.
  React.useEffect(() => {
    setText(displayObserved(check));
    setChecked(check.status === "PASS");
  }, [check]);

  const dirtyText = text !== displayObserved(check);

  async function save(nextText: string, nextChecked: boolean): Promise<void> {
    setSaving(true);
    try {
      await attestFinding(scanId, token, {
        rule_id: check.rule_id,
        observed: nextText === displayObserved(check) ? undefined : nextText,
        present: nextChecked === (check.status === "PASS") ? undefined : nextChecked,
      });
      setSavedTick(true);
      window.setTimeout(() => setSavedTick(false), 2000);
      onChanged();
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Saving attestation failed.";
      onError(e, msg);
    } finally {
      setSaving(false);
    }
  }

  const tone =
    check.status === "PASS"
      ? "border-green-300 bg-green-50/50"
      : check.status === "NOT_ASSESSABLE"
        ? "border-amber-300 bg-amber-50/60"
        : "border-red-300 bg-red-50/50";
  const glyph = check.status === "PASS" ? "✓" : check.status === "NOT_ASSESSABLE" ? "–" : "✕";
  const glyphTone =
    check.status === "PASS"
      ? "bg-green-100 text-green-800"
      : check.status === "NOT_ASSESSABLE"
        ? "bg-amber-100 text-amber-900"
        : "bg-red-100 text-red-800";

  return (
    <div className={cn("rounded-xl border bg-white p-4 shadow-sm", tone)}>
      <div className="flex flex-wrap items-center gap-1.5">
        <span
          className={cn("grid h-6 w-6 flex-none place-items-center rounded-full text-xs font-black", glyphTone)}
          aria-hidden="true"
        >
          {glyph}
        </span>
        <span className="text-[13px] font-bold text-slate-900">{TITLES[check.rule_id] ?? check.rule_id}</span>
        {check.manual && (
          <Badge tone="blue">manually set</Badge>
        )}
      </div>
      <p className="mt-0.5 font-mono text-[11px] text-slate-500">{check.citation}</p>
      {check.status !== "PASS" && check.cause === "possible_miss" && (
        <p className="mt-1.5 rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] font-semibold text-amber-900">
          Needs verification — our read may have missed this, not necessarily a violation.
        </p>
      )}
      {check.status !== "PASS" && check.why && (
        <p className="mt-1.5 text-xs text-slate-700">
          <span className="font-semibold">Why:</span> {check.why}
        </p>
      )}
      {check.status !== "PASS" && check.next_steps.length > 0 && (
        <ol className="mt-1 list-decimal space-y-0.5 pl-5 text-xs text-slate-700">
          {check.next_steps.map((s, i) => (
            <li key={i}>{s}</li>
          ))}
        </ol>
      )}
      <div className="mt-2 flex items-center gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => {
            if (dirtyText) void save(text, checked);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          }}
          placeholder="Not detected — type the declaration text if present"
          aria-label={`${TITLES[check.rule_id] ?? check.rule_id} observed value`}
          className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-[13px]"
        />
        <label className="flex flex-none cursor-pointer items-center gap-1.5 text-xs font-semibold text-slate-600">
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => {
              const next = e.target.checked;
              setChecked(next);
              void save(text, next);
            }}
            className="h-4 w-4 accent-amber-600"
          />
          Present
        </label>
      </div>
      <p className="mt-1.5 text-[11px] text-slate-500" aria-live="polite">
        {saving ? "Saving attestation…" : savedTick ? "Saved ✓" : `Expected: ${check.expected ?? "—"}`}
      </p>
    </div>
  );
}
