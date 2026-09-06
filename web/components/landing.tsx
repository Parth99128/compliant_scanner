"use client";

import Link from "next/link";
import * as React from "react";

import { CountUp, Reveal } from "@/components/motion";

const STEPS = [
  {
    n: "01",
    title: "Capture the label",
    body: "Phone photo with a card-size reference beside the pack — or drop existing photos. One close-up, or up to 5 angles merged into a single verdict.",
  },
  {
    n: "02",
    title: "Machine reads every word",
    body: "On-device OCR with enhancement, tilt correction and rotation rescue. No photo ever leaves the device unprocessed — no GPU needed.",
  },
  {
    n: "03",
    title: "Millimetres, not pixels",
    body: "The card sets the pixel-to-mm scale, so letter and numeral heights are judged in real millimetres against the Rule 7 tables.",
  },
  {
    n: "04",
    title: "Officer confirms, report issues",
    body: "Ten deterministic checks produce a verdict; a human review gate unlocks the printable evidence report with photos and citations.",
  },
];

const FEATURES = [
  { title: "Rule 7 font measurement", body: "Numeral, letter and width checks against the verified Table-I/II minima — the check manual inspection always missed." },
  { title: "Live auto-capture", body: "Viewfinder frames are scored for text, size and focus; the shutter fires only when every declaration reads clearly." },
  { title: "Multi-angle merge", body: "Glare on one shot rarely survives five. OCR lines union by confidence into one verdict with per-angle proof." },
  { title: "Unmeasured ≠ passed", body: "Rules that could not run return Not Assessable and block a Compliant verdict. The safe direction, structurally." },
  { title: "Human-in-the-loop reports", body: "Pending by default; confirm or admin-override with written reasons. Full audit trail on every PDF." },
  { title: "100% CPU, offline-ready", body: "Tesseract, OpenCV and regex run on a standard laptop. No cloud key required for the core pipeline." },
];

const RULES = [
  "LMPC-6.1-mrp",
  "LMPC-6.1-netqty",
  "LMPC-6.1-dates",
  "LMPC-6.1-care",
  "LMPC-7.2-numeral",
  "LMPC-7.3-letter",
];

const FAQS: Array<[string, string]> = [
  [
    "Is this an official government portal?",
    "No — a Smart India Hackathon 2026 demonstration prototype. Citations marked Verified were checked against the official Gazette text; the rest need legal review before any enforcement use.",
  ],
  [
    "What phone or computer do I need?",
    "Any modern phone camera for capture, and any standard laptop CPU for analysis. There is deliberately no GPU, cloud, or API-key requirement.",
  ],
  [
    "What if the app cannot measure something?",
    "It says Not Assessable with a remedy (e.g. include the reference card) — and such scans can never show Compliant. Unmeasured is never a pass.",
  ],
  [
    "Where do my photos go?",
    "Into your own secured scan repository with owner-only access, review audit trail, and GPS attached only when you opt in at upload.",
  ],
];

function HeroVisual(): React.JSX.Element {
  return (
    <div className="relative mx-auto w-full max-w-md" aria-hidden="true">
      <div className="animate-floaty overflow-hidden rounded-xl border border-white/15 bg-white text-slate-900 shadow-2xl">
        <div className="flex items-center justify-between bg-navy-900 px-4 py-2.5 text-white">
          <span className="text-xs font-bold tracking-wide">DECLARATION PANEL · LIVE</span>
          <span className="rounded bg-igreen-700 px-2 py-0.5 text-[11px] font-bold">● REC</span>
        </div>
        <div className="relative bg-amber-50/60 p-5 font-mono text-[13px] leading-7">
          <p>Instant Noodles with seasoning</p>
          <p>Net Qty: <span className="rounded bg-igreen-100 px-1 font-bold text-igreen-800">60 g ✓</span></p>
          <p>MRP Rs. 14.00 <span className="rounded bg-igreen-100 px-1 font-bold text-igreen-800">incl. taxes ✓</span></p>
          <p>Mfg: 15/05/2024 · Best Before: 16/02/2026</p>
          <p>Care: 1800-419-0000 · <span className="rounded bg-amber-200 px-1 font-bold text-amber-900">MADE IN INDIA ?</span></p>
          <div className="scanline pointer-events-none absolute inset-x-3 rounded border-b-4 border-saffron-500 shadow-[0_2px_12px_rgba(246,139,31,0.8)]" />
        </div>
        <div className="flex items-center justify-between border-t border-slate-200 bg-white px-4 py-3">
          <span className="text-xs font-bold text-slate-500">6/6 declarations · 1.1 mm type</span>
          <span className="rounded-md bg-igreen-700 px-3 py-1.5 text-xs font-bold text-white">COMPLIANT</span>
        </div>
      </div>
      <div className="absolute -left-4 top-8 hidden rotate-[-6deg] items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-navy-950 shadow-lg sm:flex">
        <span className="grid h-5 w-5 place-items-center rounded-full bg-igreen-700 text-[10px] text-white">✓</span>
        Rule 7 · Table-I passed
      </div>
      <div className="absolute -right-3 bottom-10 hidden rotate-[5deg] items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-navy-950 shadow-lg sm:flex">
        <span className="grid h-5 w-5 place-items-center rounded-full bg-navy-900 text-[10px] text-white">✓</span>
        Officer reviewed
      </div>
    </div>
  );
}

export function LandingPage(): React.JSX.Element {
  return (
    <div className="-mx-4 -mt-4 md:-mx-7 md:-mt-6">
      {/* HERO */}
      <section className="relative overflow-hidden bg-navy-950 text-white">
        <div className="pointer-events-none absolute inset-0 opacity-[0.07]" aria-hidden="true">
          <svg className="h-full w-full" preserveAspectRatio="none" viewBox="0 0 100 100">
            {Array.from({ length: 11 }).map((_, i) => (
              <line key={i} x1={i * 10} y1="0" x2={i * 10} y2="100" stroke="white" strokeWidth="0.3" />
            ))}
            {Array.from({ length: 11 }).map((_, i) => (
              <line key={i} x1="0" y1={i * 10} x2="100" y2={i * 10} stroke="white" strokeWidth="0.3" />
            ))}
          </svg>
        </div>
        <div className="relative mx-auto grid max-w-6xl items-center gap-10 px-4 py-14 md:grid-cols-2 md:px-7 md:py-20">
          <div>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/drishti-logo.jpg"
              alt="DrishtiLM — scanner emblem"
              className="h-24 w-auto animate-floaty rounded-2xl shadow-[0_0_36px_rgba(56,189,248,0.35)] ring-1 ring-white/20"
            />
            <p className="mt-4 inline-flex items-center gap-2 rounded-full border border-gold/50 bg-white/5 px-3 py-1 text-[11px] font-bold uppercase tracking-widest text-gold">
              SIH26034 · Legal Metrology · Packaged Commodities Rules, 2011
            </p>
            <h1 className="mt-4 font-display text-4xl font-black leading-[1.08] tracking-tight md:text-5xl">
              <span className="bg-gradient-to-r from-white via-white to-slate-300 bg-clip-text text-transparent">
                Drishti
              </span>
              <span className="bg-gradient-to-r from-sky-400 to-green-400 bg-clip-text text-transparent">
                LM
              </span>
              <br />
              Every packet.
              <br />
              Every declaration. <span className="text-saffron-500">Verified.</span>
            </h1>
            <p className="mt-2 text-sm font-semibold tracking-wide text-slate-300">सही माप, हर पैकेट — correct measure, every packet.</p>
            <p className="mt-4 max-w-lg text-[15px] leading-relaxed text-slate-300">
              <strong className="text-white">DrishtiLM</strong> — <em>dṛṣṭi</em>, “vision” — points a phone at any
              packaged commodity, reads the label, measures letter heights in millimetres,
              and judges all ten Legal Metrology declarations on an ordinary CPU.
              Unmeasured is never shown passed.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link
                href="/login"
                className="rounded-md bg-saffron-500 px-6 py-3 text-sm font-bold text-navy-950 shadow-lg transition-all hover:-translate-y-0.5 hover:bg-saffron-600 hover:text-white"
              >
                Start inspecting →
              </Link>
              <a
                href="#how"
                className="rounded-md border border-white/25 px-6 py-3 text-sm font-bold text-white transition-colors hover:bg-white/10"
              >
                See how it works
              </a>
            </div>
            <dl className="mt-8 grid max-w-lg grid-cols-3 gap-4 border-t border-white/10 pt-5">
              {[
                { v: 10, suffix: "", label: "Rule checks per scan" },
                { v: 5, suffix: "s", label: "Per image on CPU", prefix: "<" },
                { v: 100, suffix: "%", label: "CPU-only pipeline" },
              ].map((s) => (
                <div key={s.label}>
                  <dt className="sr-only">{s.label}</dt>
                  <dd className="font-display text-3xl font-black text-white">
                    {s.prefix ?? ""}
                    <CountUp to={s.v} />
                    {s.suffix}
                  </dd>
                  <dd className="mt-0.5 text-xs text-slate-400">{s.label}</dd>
                </div>
              ))}
            </dl>
          </div>
          <HeroVisual />
        </div>
        <div className="relative overflow-hidden border-y border-white/10 bg-navy-900/80 py-2.5" aria-hidden="true">
          <div className="animate-ticker flex w-max gap-8 whitespace-nowrap text-xs font-bold tracking-widest text-slate-300">
            {[...RULES, ...RULES].map((r, i) => (
              <span key={i} className="flex items-center gap-2">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-igreen-700" /> {r}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how" className="mx-auto max-w-6xl scroll-mt-24 px-4 py-14 md:px-7">
        <Reveal>
          <p className="text-xs font-bold uppercase tracking-widest text-saffron-700">How it works</p>
          <h2 className="mt-1 font-display text-3xl font-black tracking-tight text-navy-950">
            Photo in, verdict out — in four steps
          </h2>
        </Reveal>
        <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delay={i * 90}>
              <div className="group h-full rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition-all hover:-translate-y-1 hover:border-navy-800 hover:shadow-lg">
                <p className="font-display text-4xl font-black text-navy-100 transition-colors group-hover:text-saffron-500">
                  {s.n}
                </p>
                <h3 className="mt-2 text-[15px] font-bold text-navy-950">{s.title}</h3>
                <p className="mt-1.5 text-[13px] leading-relaxed text-slate-600">{s.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="scroll-mt-24 border-y border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-4 py-14 md:px-7">
          <Reveal>
            <p className="text-xs font-bold uppercase tracking-widest text-saffron-700">Why it matters</p>
            <h2 className="mt-1 font-display text-3xl font-black tracking-tight text-navy-950">
              Built for enforcement realities
            </h2>
          </Reveal>
          <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f, i) => (
              <Reveal key={f.title} delay={(i % 3) * 90}>
                <div className="h-full rounded-xl border-l-4 border-l-navy-800 border border-slate-200 bg-paper p-5 shadow-sm transition-all hover:-translate-y-1 hover:shadow-md">
                  <h3 className="text-[15px] font-bold text-navy-950">✓ {f.title}</h3>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-slate-600">{f.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* RULES */}
      <section id="rules" className="mx-auto max-w-6xl scroll-mt-24 px-4 py-14 md:px-7">
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Reveal>
            <div className="h-full rounded-xl bg-navy-900 p-6 text-white shadow-lg">
              <h3 className="font-display text-xl font-bold">Rule 6 — What must be printed</h3>
              <ul className="mt-3 space-y-2 text-[13px] leading-relaxed text-slate-300">
                <li>• Maker name + address, generic commodity name</li>
                <li>• Net quantity in standard units, MRP inclusive of all taxes</li>
                <li>• Month-year of manufacture, customer-care contact, origin for imports</li>
              </ul>
            </div>
          </Reveal>
          <Reveal delay={120}>
            <div className="h-full rounded-xl border-2 border-saffron-500 bg-white p-6 shadow-lg">
              <h3 className="font-display text-xl font-bold text-navy-950">Rule 7 — How big it must be</h3>
              <ul className="mt-3 space-y-2 text-[13px] leading-relaxed text-slate-600">
                <li>• Numerals tiered by quantity (Table-I) or panel area (Table-II)</li>
                <li>• Letters ≥ 1 mm (≥ 2 mm embossed); width ≥ ⅓ of height</li>
                <li>• Measured in millimetres via reference-card calibration</li>
              </ul>
            </div>
          </Reveal>
        </div>
        <Reveal>
          <p className="mt-4 rounded-md border border-sky-300 bg-sky-50 px-4 py-3 text-[13px] text-sky-900">
            “Verified” badges in results mean checked word-for-word against the official Gazette text;
            the rest are transcribed from the problem statement and need legal review before enforcement use.
          </p>
        </Reveal>
      </section>

      {/* FAQ */}
      <section id="faq" className="scroll-mt-24 border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-3xl px-4 py-14 md:px-7">
          <Reveal>
            <h2 className="font-display text-3xl font-black tracking-tight text-navy-950">Common questions</h2>
          </Reveal>
          <div className="mt-6 space-y-2.5">
            {FAQS.map(([q, a], i) => (
              <Reveal key={q} delay={i * 60}>
                <details className="group rounded-lg border border-slate-200 bg-paper px-4 py-3 open:shadow-sm">
                  <summary className="cursor-pointer text-sm font-bold text-navy-950 marker:text-saffron-600">
                    {q}
                  </summary>
                  <p className="mt-2 text-[13px] leading-relaxed text-slate-600">{a}</p>
                </details>
              </Reveal>
            ))}
          </div>
          <Reveal>
            <div className="mt-8 overflow-hidden rounded-xl bg-gradient-to-r from-navy-900 via-navy-800 to-igreen-800 p-8 text-center text-white shadow-lg">
              <h3 className="font-display text-2xl font-black">Ready to inspect your first label?</h3>
              <p className="mx-auto mt-1 max-w-md text-sm text-slate-300">
                Sign in as an officer and run a scan in under a minute. Reports unlock after review.
              </p>
              <Link
                href="/login"
                className="mt-4 inline-block rounded-md bg-saffron-500 px-6 py-3 text-sm font-bold text-navy-950 shadow transition-all hover:-translate-y-0.5 hover:bg-saffron-600 hover:text-white"
              >
                Officer sign in →
              </Link>
            </div>
          </Reveal>
        </div>
      </section>
    </div>
  );
}
