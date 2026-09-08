"use client";

import Link from "next/link";
import * as React from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}): React.JSX.Element {
  React.useEffect(() => {
    console.error("Console error boundary:", error);
  }, [error]);
  return (
    <div className="mx-auto grid max-w-lg place-items-center px-4 py-16 text-center">
      <p className="rounded-xl border border-red-300 bg-red-50 px-4 py-2 text-sm font-bold text-red-800">
        Something interrupted this page
      </p>
      <h1 className="mt-4 font-display text-xl font-black text-navy-950">The console hit a snag</h1>
      <p className="mt-2 text-sm text-slate-500">
        Your scans and records are safe on the server — only this view failed to render. Try again,
        or return to the console.
        {error.digest ? <span className="mt-1 block font-mono text-xs">Ref: {error.digest}</span> : null}
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <button
          onClick={reset}
          className="rounded-lg bg-navy-900 px-4 py-2.5 text-sm font-bold text-white"
        >
          Try again
        </button>
        <Link
          href="/"
          className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-bold text-slate-700"
        >
          Back to console
        </Link>
      </div>
    </div>
  );
}
