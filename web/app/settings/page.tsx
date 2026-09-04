export default function SettingsPage(): React.JSX.Element {
  return (
    <div>
      <p className="text-xs text-slate-500">Inspect / Settings</p>
      <h1 className="text-xl font-bold">Settings</h1>
      <div className="mt-4 rounded-md border border-slate-200 bg-white p-5 text-sm text-slate-500 shadow-sm">
        Backend endpoint: <code>{process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001"}</code> (set
        via <code>NEXT_PUBLIC_API_URL</code>).
      </div>
    </div>
  );
}
