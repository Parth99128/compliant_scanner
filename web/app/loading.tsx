export default function Loading(): React.JSX.Element {
  return (
    <div className="animate-rise" aria-busy="true" aria-label="Loading">
      <div className="animate-pulse overflow-hidden rounded-xl bg-gradient-to-br from-navy-950 via-navy-900 to-navy-800 px-5 py-6 md:px-8 md:py-8">
        <div className="h-3 w-40 rounded bg-white/20" />
        <div className="mt-3 h-7 w-2/3 rounded bg-white/25" />
        <div className="mt-2 h-4 w-1/2 rounded bg-white/15" />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-32 animate-pulse rounded-xl bg-slate-200" />
        ))}
      </div>
    </div>
  );
}
