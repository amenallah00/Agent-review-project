import { useEffect, useState } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";
import { StatCard } from "../components/StatCard";
import { StatusBadge } from "../components/Badge";
import { api } from "../lib/api";
import { scoreTier } from "../lib/score";
import type { Review, Stats } from "../lib/types";

function timeAgo(iso: string): string {
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function Dashboard() {
  const { bumpRepos, reposVersion } = useOutletContext<{ bumpRepos: () => void; reposVersion: number }>();
  const [stats, setStats] = useState<Stats | null>(null);
  const [reviews, setReviews] = useState<Review[] | null>(null);
  const [repos, setRepos] = useState<any[] | null>(null);
  const navigate = useNavigate();

  async function load() {
    const [statsRes, reposRes] = await Promise.all([api.stats(), api.repos()]);
    setStats(statsRes);
    setReviews(reposRes.recent_reviews);
    setRepos(reposRes.repos);
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 20000);
    return () => clearInterval(timer);
  }, [reposVersion]);

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p>Overview of CodeSentinel activity across your repositories.</p>
        </div>
        <button className="btn primary" onClick={() => bumpRepos()}>+ Connect new repo</button>
      </div>

      <div className="stat-grid">
        <StatCard label="PRs reviewed" value={stats?.prs_reviewed ?? null} loading={!stats} accent="var(--brand)" />
        <StatCard label="Average score" value={stats?.prs_reviewed ? stats.average_score : "—"} loading={!stats} accent="var(--brand-3)" />
        <StatCard label="Issues caught" value={stats?.issues_caught ?? null} loading={!stats} accent="var(--brand-2)" />
        <StatCard label="Repos connected" value={stats?.repos_connected ?? null} loading={!stats} accent="var(--text)" />
      </div>

      <div className="two-col-uneven" style={{ marginTop: "2rem" }}>
        <div className="panel">
          <div className="panel-title-row">
            <h2>Recent reviews</h2>
            <span className="muted" style={{ fontSize: "0.78rem" }}>
              <span className="live-dot" /> Live
            </span>
          </div>
          {reviews === null ? (
            <div className="skeleton" style={{ height: 120 }} />
          ) : reviews.length === 0 ? (
            <div className="empty-state">
              No reviews yet for your connected repositories. Connect a repo and open or update a Pull
              Request to see data appear here.
            </div>
          ) : (
            <table>
              <thead>
                <tr><th>Repository</th><th>Pull Request</th><th>Score</th><th>Status</th><th>Reviewed</th></tr>
              </thead>
              <tbody>
                {reviews.map((r) => (
                  <tr
                    key={`${r.repo}-${r.pr_number}`}
                    className="clickable"
                    onClick={() => r.repo && navigate(`/dashboard/repos/${encodeURIComponent(r.repo)}`)}
                  >
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

        <div className="panel">
          <div className="panel-title-row">
            <h2>Repositories</h2>
          </div>
          {repos === null ? (
            <div className="skeleton" style={{ height: 120 }} />
          ) : repos.length === 0 ? (
             <div className="empty-state">No repositories connected yet.</div>
          ) : (
            <div className="repo-list-dashboard" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
               {repos.map((r) => (
                 <button
                   key={r.name}
                   className="btn ghost"
                   style={{ justifyContent: "flex-start", width: "100%", padding: "0.75rem", border: "1px solid var(--border)" }}
                   onClick={() => navigate(`/dashboard/repos/${encodeURIComponent(r.name)}`)}
                 >
                   <span style={{ opacity: 0.7, marginRight: "0.5rem" }}>
                     {r.active ? "\u{1F4C1}" : "\u{1F5D1}\uFE0F"}
                   </span>
                   {r.name}
                 </button>
               ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}