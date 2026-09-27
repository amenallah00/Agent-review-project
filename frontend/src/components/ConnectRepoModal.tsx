import { useEffect, useState } from "react";
import { useToast } from "../context/ToastContext";
import { api, ApiError } from "../lib/api";
import type { GithubRepo } from "../lib/types";

interface Props {
  onClose: () => void;
  onConnected: () => void;
}

export function ConnectRepoModal({ onClose, onConnected }: Props) {
  const [repos, setRepos] = useState<GithubRepo[] | null>(null);
  const [connected, setConnected] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [connecting, setConnecting] = useState<string | null>(null);
  const showToast = useToast();

  useEffect(() => {
    Promise.all([api.githubRepos(), api.repos()])
      .then(([gh, mine]) => {
        setRepos(gh.repos);
        setConnected(new Set(mine.repos.map((r) => r.name)));
      })
      .catch((e) => setError(e instanceof ApiError ? e.message : "Could not load your GitHub repositories."));
  }, []);

  async function connect(name: string) {
    setConnecting(name);
    try {
      await api.connectRepo(name);
      setConnected((s) => new Set(s).add(name));
      onConnected();
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Could not connect this repository.", true);
    } finally {
      setConnecting(null);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <strong>Connect a repository</strong>
          <button onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          {error && <div className="error-box">{error}</div>}
          {!error && repos === null && <div className="muted">Loading your GitHub repositories…</div>}
          {!error && repos?.length === 0 && <div className="empty-state">No repositories found on your GitHub account.</div>}
          {repos?.map((r) => (
            <div className="modal-repo-row" key={r.name}>
              <div>
                <strong>{r.name}</strong>
                {r.private && <span className="tag" style={{ marginLeft: 8 }}>private</span>}
              </div>
              {connected.has(r.name) ? (
                <span className="muted">Connected</span>
              ) : (
                <button className="btn primary" disabled={connecting === r.name} onClick={() => connect(r.name)}>
                  {connecting === r.name ? "Connecting…" : "Connect"}
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
