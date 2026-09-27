import { useEffect, useRef, useState } from "react";
import { useNavigate, useOutletContext, useParams } from "react-router-dom";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { IssuesDonut } from "../components/IssuesDonut";
import { ScoreTrendChart } from "../components/ScoreTrendChart";
import { StatusBadge } from "../components/Badge";
import { useToast } from "../context/ToastContext";
import { api, ApiError } from "../lib/api";
import { scoreTier } from "../lib/score";
import type { RepoReviewsResponse, Severity } from "../lib/types";

const SEVERITY_LEVELS: Severity[] = ["info", "warning", "error", "critical"];
const AVAILABLE_LANGUAGES = ["python", "javascript", "typescript", "java"];

function timeAgo(iso: string): string {
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

export function RepoDetail() {
  const { name } = useParams<{ name: string }>();
  const repo = decodeURIComponent(name ?? "");
  const { bumpRepos } = useOutletContext<{ bumpRepos: () => void }>();
  const navigate = useNavigate();
  const showToast = useToast();

  const [data, setData] = useState<RepoReviewsResponse | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved">("idle");
  const [excludedInput, setExcludedInput] = useState("");
  const [dragging, setDragging] = useState<"approve_threshold" | "changes_threshold" | null>(null);
  const [dragValues, setDragValues] = useState<{ approve_threshold: number; changes_threshold: number }>({
    approve_threshold: 80,
    changes_threshold: 50,
  });
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [showDisconnectConfirm, setShowDisconnectConfirm] = useState(false);

  async function load() {
    try {
      const res = await api.repoReviews(repo);
      setData(res);
      setDragValues({
        approve_threshold: res.settings.approve_threshold,
        changes_threshold: res.settings.changes_threshold,
      });
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Could not load this repository.", true);
      navigate("/dashboard");
    }
  }

  useEffect(() => {
    load();
    const timer = setInterval(load, 20000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [repo]);

  async function saveSettings(partial: Partial<RepoReviewsResponse["settings"]>) {
    setData((d) => (d ? { ...d, settings: { ...d.settings, ...partial } } : d));
    setSaveState("saving");
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      try {
        await api.updateSettings(repo, partial);
        setSaveState("saved");
        setTimeout(() => setSaveState("idle"), 1500);
      } catch (e) {
        setSaveState("idle");
        showToast(e instanceof ApiError ? e.message : "Could not save settings.", true);
      }
    }, 350);
  }

  async function toggleActive() {
    if (!data) return;
    const next = !data.settings.active;
    setData((d) => (d ? { ...d, settings: { ...d.settings, active: next } } : d));
    try {
      await api.setActive(repo, next);
      showToast(next ? "Reviews enabled for this repo" : "Reviews paused for this repo");
    } catch (e) {
      setData((d) => (d ? { ...d, settings: { ...d.settings, active: !next } } : d));
      showToast(e instanceof ApiError ? e.message : "Could not update — try again.", true);
    }
  }

  async function disconnect() {
    try {
      await api.disconnectRepo(repo);
      showToast("Repository disconnected");
      bumpRepos();
      navigate("/dashboard");
    } catch (e) {
      showToast(e instanceof ApiError ? e.message : "Could not disconnect — try again.", true);
    } finally {
      setShowDisconnectConfirm(false);
    }
  }

  function addExcludedFile() {
    const val = excludedInput.trim();
    if (!val || !data) return;
    if (data.settings.excluded_files.includes(val)) {
      setExcludedInput("");
      return;
    }
    saveSettings({ excluded_files: [...data.settings.excluded_files, val] });
    setExcludedInput("");
  }

  function removeExcludedFile(path: string) {
    if (!data) return;
    saveSettings({ excluded_files: data.settings.excluded_files.filter((p) => p !== path) });
  }

  function toggleLanguage(lang: string) {
    if (!data) return;
    const current = new Set(data.settings.languages);
    current.has(lang) ? current.delete(lang) : current.add(lang);
    saveSettings({ languages: Array.from(current) });
  }

  if (!data) {
    return <div className="skeleton" style={{ height: 400 }} />;
  }

  const { settings, reviews, average_score, issues_breakdown } = data;

  return (
    <>
      <div className="page-header">
        <h1>{repo}</h1>
        <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
          <a className="btn" href={`https://github.com/${repo}`} target="_blank" rel="noopener noreferrer">
            Open on GitHub
          </a>
          <button
            className={`toggle-switch${settings.active ? "" : " off"}`}
            onClick={toggleActive}
            title="Toggle reviews for this repo"
          />
          <button className="btn danger" onClick={() => setShowDisconnectConfirm(true)}>Disconnect</button>
        </div>
      </div>

      <div className="two-col">
        <div className="panel">
          <div className="panel-title-row">
            <h2>Quality score trend</h2>
            <span className="muted" style={{ fontSize: "0.78rem" }}>
              {reviews.length ? `Last ${reviews.length} review${reviews.length > 1 ? "s" : ""}` : "No reviews yet"}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "baseline", gap: "0.6rem" }}>
            <div className="big-score">{reviews.length ? average_score : "—"}</div>
            {reviews.length >= 2 && (() => {
              const delta = reviews[0].score - reviews[1].score;
              if (delta === 0) return null;
              return (
                <span className={`delta-pill ${delta > 0 ? "up" : "down"}`} title="Change vs previous review">
                  {delta > 0 ? "▲" : "▼"} {Math.abs(delta)} pts
                </span>
              );
            })()}
          </div>
          <ScoreTrendChart reviews={reviews} />
        </div>

        <div className="panel">
          <h2>Issues breakdown</h2>
          <div style={{ marginTop: "0.6rem" }}>
            <IssuesDonut breakdown={issues_breakdown} />
          </div>
        </div>
      </div>

      <div className="two-col-uneven">
        <div className="panel">
          <h2>Recent PR reviews</h2>
          {reviews.length === 0 ? (
            <div className="empty-state">
              No reviews yet. Open or update a Pull Request on this repository to see one appear here.
            </div>
          ) : (
            reviews.map((r) => (
              <div className="review-row" key={r.pr_number}>
                <div className="pr-title">
                  #{r.pr_number} {r.pr_title || "(untitled)"}
                  <br />
                  <span className="pr-meta">{timeAgo(r.reviewed_at)}</span>
                </div>
                <div className={`score-pill ${scoreTier(r.score)}`}>{r.score}</div>
                <div style={{ width: 12 }} />
                <StatusBadge status={r.status} />
              </div>
            ))
          )}
        </div>

        <div className="panel">
          <div className="panel-title-row">
            <h2>Review settings</h2>
            <span className={`save-indicator${saveState !== "idle" ? " show" : ""}${saveState === "saving" ? " saving" : ""}`}>
              {saveState === "saving" ? "Saving…" : saveState === "saved" ? "✓ Saved" : ""}
            </span>
          </div>

          <div className="settings-row">
            <label>Minimum severity</label>
            <div className="segmented">
              {SEVERITY_LEVELS.map((level) => (
                <button
                  key={level}
                  className={level === settings.min_severity ? "on" : ""}
                  onClick={() => saveSettings({ min_severity: level })}
                >
                  {level}
                </button>
              ))}
            </div>
          </div>

          <div className="settings-row">
            <label>Target languages</label>
            <div className="tag-list">
              {AVAILABLE_LANGUAGES.map((lang) => (
                <span
                  key={lang}
                  className={`tag toggleable${settings.languages.includes(lang) ? " on" : ""}`}
                  onClick={() => toggleLanguage(lang)}
                >
                  {lang}
                </span>
              ))}
            </div>
          </div>

          <div className="settings-row">
            <label>Approve threshold — {dragging === "approve_threshold" ? dragValues.approve_threshold : settings.approve_threshold}</label>
            <input
              type="range"
              className="slider-input"
              min={0}
              max={100}
              value={dragging === "approve_threshold" ? dragValues.approve_threshold : settings.approve_threshold}
              style={{ ["--fill" as string]: `${(dragging === "approve_threshold" ? dragValues.approve_threshold : settings.approve_threshold)}%` }}
              onChange={(e) => {
                setDragging("approve_threshold");
                setDragValues((v) => ({ ...v, approve_threshold: Number(e.target.value) }));
              }}
              onMouseUp={() => { saveSettings({ approve_threshold: dragValues.approve_threshold }); setDragging(null); }}
              onTouchEnd={() => { saveSettings({ approve_threshold: dragValues.approve_threshold }); setDragging(null); }}
            />
          </div>

          <div className="settings-row">
            <label>Request-changes threshold — {dragging === "changes_threshold" ? dragValues.changes_threshold : settings.changes_threshold}</label>
            <input
              type="range"
              className="slider-input"
              min={0}
              max={100}
              value={dragging === "changes_threshold" ? dragValues.changes_threshold : settings.changes_threshold}
              style={{ ["--fill" as string]: `${(dragging === "changes_threshold" ? dragValues.changes_threshold : settings.changes_threshold)}%` }}
              onChange={(e) => {
                setDragging("changes_threshold");
                setDragValues((v) => ({ ...v, changes_threshold: Number(e.target.value) }));
              }}
              onMouseUp={() => { saveSettings({ changes_threshold: dragValues.changes_threshold }); setDragging(null); }}
              onTouchEnd={() => { saveSettings({ changes_threshold: dragValues.changes_threshold }); setDragging(null); }}
            />
          </div>

          <div className="settings-row">
            <label>Excluded files</label>
            <div className="tag-list">
              {settings.excluded_files.length === 0 ? (
                <span className="muted" style={{ fontSize: "0.8rem" }}>None</span>
              ) : (
                settings.excluded_files.map((p) => (
                  <span className="tag removable" key={p}>
                    {p} <button className="x" onClick={() => removeExcludedFile(p)}>✕</button>
                  </span>
                ))
              )}
            </div>
            <div className="tag-input-row">
              <input
                type="text"
                placeholder="e.g. *.lock, dist/**"
                value={excludedInput}
                onChange={(e) => setExcludedInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addExcludedFile(); } }}
              />
              <button className="btn" onClick={addExcludedFile}>Add</button>
            </div>
          </div>
        </div>
      </div>
      {showDisconnectConfirm && (
        <ConfirmDialog
          title="Disconnect repository"
          message={`Disconnect ${repo}? Its review history will be deleted.`}
          confirmLabel="Disconnect"
          danger
          onConfirm={disconnect}
          onCancel={() => setShowDisconnectConfirm(false)}
        />
      )}
    </>
  );
}