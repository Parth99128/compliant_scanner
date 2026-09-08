import Link from "next/link";

export default function NotFound(): React.JSX.Element {
  return (
    <div className="mx-auto grid max-w-lg place-items-center px-4 py-16 text-center">
      <p className="font-display text-6xl font-black tabular-nums text-navy-900">404</p>
      <div className="tricolor-bar mt-3 h-1 w-24 rounded-full" aria-hidden="true" />
      <h1 className="mt-4 font-display text-xl font-black text-navy-950">This record does not exist</h1>
      <p className="mt-2 text-sm text-slate-500">
        The page or scan you asked for was moved, deleted, or never filed. Records here are never
        removed by the system — check the scan ID and try again.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        <Link href="/" className="rounded-lg bg-navy-900 px-4 py-2.5 text-sm font-bold text-white">
          Back to console
        </Link>
        <Link
          href="/scans"
          className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm font-bold text-slate-700"
        >
          Scan history
        </Link>
      </div>
    </div>
  );
}
