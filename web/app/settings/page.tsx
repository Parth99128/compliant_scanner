import { PageHeader } from "@/components/page-header";

export default function SettingsPage(): React.JSX.Element {
  return (
    <div>
      <PageHeader
        title="Settings"
        description="Connection and environment details for this installation."
      />
      <div className="mt-4 rounded-md border border-slate-200 bg-white p-5 text-sm text-slate-500 shadow-sm">
        Backend endpoint: <code>{process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8001"}</code> (set
        via <code>NEXT_PUBLIC_API_URL</code>).
      </div>
    </div>
  );
}
