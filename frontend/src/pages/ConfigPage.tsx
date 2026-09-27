import { useEffect, useState } from "react";
import { api } from "../lib/api";

function KeyValueTable({ data }: { data: Record<string, unknown> | null }) {
  if (!data) return <div className="skeleton" style={{ height: 100 }} />;
  return (
    <table>
      <thead><tr><th>Key</th><th>Value</th></tr></thead>
      <tbody>
        {Object.entries(data).map(([k, v]) => (
          <tr key={k}><td>{k}</td><td>{JSON.stringify(v)}</td></tr>
        ))}
      </tbody>
    </table>
  );
}

export function ConfigPage() {
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [metrics, setMetrics] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    api.config().then(setConfig);
    api.metrics().then(setMetrics);
  }, []);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Global configuration</h1>
          <p>Read-only. To change: edit <code>.env</code> (global) or add a <code>.reviewbot.yml</code> at the root of a specific repo.</p>
        </div>
      </div>
      <div className="panel" style={{ marginBottom: "1.2rem" }}>
        <KeyValueTable data={config} />
      </div>
      <div className="panel">
        <h2>Raw metrics <span className="muted" style={{ fontWeight: 400 }}>— reset on every server restart</span></h2>
        <KeyValueTable data={metrics} />
      </div>
    </>
  );
}
