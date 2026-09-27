import { useEffect, useState } from "react";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/Badge";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { api } from "../lib/api";
import { scoreTier } from "../lib/score";
import type { AdminInstallation, AdminReview, AdminStats, AdminUser } from "../lib/types";

type Tab = "overview" | "users" | "installations";

function timeAgo(iso: string): string {
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function Admin() {
  const [tab, setTab] = useState<Tab>("overview");
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [reviews, setReviews] = useState<AdminReview[] | null>(null);
  const [installations, setInstallations] = useState<AdminInstallation[] | null>(null);
  const [denied, setDenied] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<{ title: string; message: string; onConfirm: () => void } | null>(null);

  function loadAll() {
    Promise.all([
      api.adminStats(),
      api.adminUsers(),
      api.adminReviews(),
      api.adminInstallations(),
    ])
      .then(([s, u, r, i]) => {
        setStats(s);
        setUsers(u.users);
        setReviews(r.reviews);
        setInstallations(i.installations);
      })
      .catch(() => setDenied(true));
  }

  useEffect(() => { loadAll(); }, []);

  async function handleAction(key: string, fn: () => Promise<unknown>) {
    setBusy(key);
    try {
      await fn();
      loadAll();
    } catch (e: any) {
      alert(e.message || "Action failed");
    } finally {
      setBusy(null);
    }
  }

  function confirmAction(title: string, message: string, fn: () => Promise<unknown>, key: string) {
    setConfirm({
      title,
      message,
      onConfirm: () => {
        setConfirm(null);
        handleAction(key, fn);
      },
    });
  }

  if (denied) return <div className="error-box">Access denied — this page is for administrators only.</div>;

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Admin</h1>
          <p>Manage all accounts, repositories and reviews across this CodeSentinel deployment.</p>
        </div>
      </div>

      <div className="stat-grid">
        <StatCard label="Users" value={stats?.users ?? null} loading={!stats} />
        <StatCard label="Admins" value={stats?.admins ?? null} loading={!stats} />
        <StatCard label="Repos connected" value={stats?.repos_connected ?? null} loading={!stats} />
        <StatCard label="Active repos" value={stats?.repos_active ?? null} loading={!stats} />
        <StatCard label="Reviews run" value={stats?.reviews_run ?? null} loading={!stats} />
        <StatCard label="Failed reviews" value={stats?.failed_reviews ?? null} loading={!stats} />
      </div>

      {/* Tab bar */}
      <div className="tab-bar" style={{ display: "flex", gap: "0.5rem", marginBottom: "1.2rem" }}>
        {(["overview", "users", "installations"] as Tab[]).map((t) => (
          <button
            key={t}
            className={`tab-btn${tab === t ? " active" : ""}`}
            onClick={() => setTab(t)}
            style={{
              padding: "0.5rem 1.2rem",
              borderRadius: "6px",
              border: "1px solid var(--border)",
              background: tab === t ? "var(--accent)" : "var(--card-bg)",
              color: tab === t ? "#fff" : "var(--text)",
              cursor: "pointer",
              fontWeight: 500,
              fontSize: "0.88rem",
            }}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Overview tab — recent reviews */}
      {tab === "overview" && (
        <div className="panel">
          <div className="panel-title-row">
            <h2>Recent reviews</h2>
            <span className="muted" style={{ fontSize: "0.78rem" }}>across all accounts</span>
          </div>
          {reviews === null ? (
            <div className="skeleton" style={{ height: 100 }} />
          ) : reviews.length === 0 ? (
            <div className="empty-state">No reviews.</div>
          ) : (
            <table>
              <thead><tr><th>User</th><th>Repository</th><th>Pull Request</th><th>Score</th><th>Status</th><th>Reviewed</th></tr></thead>
              <tbody>
                {reviews.map((r, i) => (
                  <tr key={i}>
                    <td>@{r.owner ?? "?"}</td>
                    <td>{r.repo}</td>
                    <td>#{r.pr_number} {r.pr_title}</td>
                    <td><span className={`score-pill ${scoreTier(r.score)}`}>{r.score}</span></td>
                    <td><StatusBadge status={r.status} /></td>
                    <td className="muted">{timeAgo(r.reviewed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Users tab */}
      {tab === "users" && (
        <div className="panel">
          <h2>Users</h2>
          {users === null ? (
            <div className="skeleton" style={{ height: 100 }} />
          ) : users.length === 0 ? (
            <div className="empty-state">No users.</div>
          ) : (
            <table>
              <thead><tr><th>User</th><th>Role</th><th>Repos</th><th>Reviews</th><th>Quota used</th><th style={{ width: 260 }}>Actions</th></tr></thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>
                      {u.avatar_url && <img src={u.avatar_url} alt="" style={{ width: 22, height: 22, borderRadius: "50%", verticalAlign: "middle", marginRight: 6 }} />}
                      {u.name || u.handle} <span className="muted">@{u.handle}</span>
                    </td>
                    <td><span className={`badge ${u.role === "admin" ? "approved" : "commented"}`}>{u.role}</span></td>
                    <td>{u.repos}</td>
                    <td>{u.reviews}</td>
                    <td>{u.reviews_used}</td>
                    <td style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                      <button
                        className="btn-small"
                        disabled={busy !== null}
                        onClick={() =>
                          handleAction(`role-${u.id}`, () =>
                            api.adminUpdateRole(u.id, u.role === "admin" ? "user" : "admin")
                          )
                        }
                        style={{ fontSize: "0.78rem", padding: "0.25rem 0.6rem", borderRadius: 4, border: "1px solid var(--border)", background: "var(--card-bg)", color: "var(--text)", cursor: "pointer" }}
                      >
                        {busy === `role-${u.id}` ? "…" : u.role === "admin" ? "Demote" : "Promote"}
                      </button>
                      <button
                        className="btn-small"
                        disabled={busy !== null || u.reviews_used === 0}
                        onClick={() => handleAction(`quota-${u.id}`, () => api.adminResetQuota(u.id))}
                        style={{ fontSize: "0.78rem", padding: "0.25rem 0.6rem", borderRadius: 4, border: "1px solid var(--border)", background: "var(--card-bg)", color: "var(--text)", cursor: "pointer" }}
                      >
                        {busy === `quota-${u.id}` ? "…" : "Reset quota"}
                      </button>
                      <button
                        className="btn-small"
                        disabled={busy !== null}
                        onClick={() =>
                          confirmAction(
                            "Delete user",
                            `Delete @${u.handle} and all their data? This cannot be undone.`,
                            () => api.adminDeleteUser(u.id),
                            `del-${u.id}`
                          )
                        }
                        style={{ fontSize: "0.78rem", padding: "0.25rem 0.6rem", borderRadius: 4, border: "1px solid #e74c3c", background: "transparent", color: "#e74c3c", cursor: "pointer" }}
                      >
                        {busy === `del-${u.id}` ? "…" : "Delete"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Installations tab */}
      {tab === "installations" && (
        <div className="panel">
          <h2>All installations</h2>
          {installations === null ? (
            <div className="skeleton" style={{ height: 100 }} />
          ) : installations.length === 0 ? (
            <div className="empty-state">No installations.</div>
          ) : (
            <table>
              <thead><tr><th>Repository</th><th>Owner</th><th>Active</th><th>Visibility</th><th style={{ width: 200 }}>Actions</th></tr></thead>
              <tbody>
                {installations.map((inst) => (
                  <tr key={inst.id}>
                    <td>{inst.name}</td>
                    <td>@{inst.owner ?? "?"}</td>
                    <td>
                      <span className={`badge ${inst.active ? "approved" : "changes_requested"}`}>
                        {inst.active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td>{inst.visibility}</td>
                    <td style={{ display: "flex", gap: "0.4rem" }}>
                      <button
                        className="btn-small"
                        disabled={busy !== null}
                        onClick={() =>
                          handleAction(`toggle-${inst.id}`, () =>
                            api.adminToggleInstallation(inst.id, !inst.active)
                          )
                        }
                        style={{ fontSize: "0.78rem", padding: "0.25rem 0.6rem", borderRadius: 4, border: "1px solid var(--border)", background: "var(--card-bg)", color: "var(--text)", cursor: "pointer" }}
                      >
                        {busy === `toggle-${inst.id}` ? "…" : inst.active ? "Deactivate" : "Activate"}
                      </button>
                      <button
                        className="btn-small"
                        disabled={busy !== null}
                        onClick={() =>
                          confirmAction(
                            "Delete installation",
                            `Remove ${inst.name}? All review history will be deleted.`,
                            () => api.adminDeleteInstallation(inst.id),
                            `del-inst-${inst.id}`
                          )
                        }
                        style={{ fontSize: "0.78rem", padding: "0.25rem 0.6rem", borderRadius: 4, border: "1px solid #e74c3c", background: "transparent", color: "#e74c3c", cursor: "pointer" }}
                      >
                        {busy === `del-inst-${inst.id}` ? "…" : "Delete"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.message}
          onConfirm={confirm.onConfirm}
          onCancel={() => setConfirm(null)}
        />
      )}
    </>
  );
}