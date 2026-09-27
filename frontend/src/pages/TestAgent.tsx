import { useState } from "react";
import { api, ApiError } from "../lib/api";
import type { TestReviewResponse } from "../lib/types";

const DEFAULT_CODE = `import os

def get_user(user_id):
    query = "SELECT * FROM users WHERE id = " + user_id
    return db.execute(query)

api_key = "sk-hardcoded-secret-value-123"
`;

function SeverityBadge({ sev }: { sev: string }) {
  const cls = sev === "critical" || sev === "error" ? "sev-critical" : sev === "warning" ? "sev-warning" : "sev-info";
  return <span className={cls} style={{ fontWeight: 700, textTransform: "uppercase", fontSize: "0.72rem" }}>{sev}</span>;
}

export function TestAgent() {
  const [filename, setFilename] = useState("example.py");
  const [code, setCode] = useState(DEFAULT_CODE);
  const [result, setResult] = useState<TestReviewResponse | null>(null);
  const [running, setRunning] = useState(false);

  async function run() {
    setRunning(true);
    setResult(null);
    try {
      setResult(await api.testReview(filename || "test.py", code));
    } catch (e) {
      setResult({
        error: e instanceof ApiError ? e.message : "Network error",
        llm_summary: "", llm_provider: "", lint_issues: [], pattern_matches: [], issues: [],
        flagged_issues_count: 0, labels: [], check: { conclusion: "", summary: "" }, auto_approve: false,
      });
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1>Test the agent</h1>
          <p>Runs the real pipeline (linter, patterns, the LLM configured in <code>.env</code>, filtering, labels, check, auto-approve) — without a real GitHub Pull Request.</p>
        </div>
      </div>

      <div className="panel">
        <input type="text" value={filename} onChange={(e) => setFilename(e.target.value)} placeholder="filename (e.g. app.py)" style={{ marginBottom: "0.7rem" }} />
        <textarea className="code-input" value={code} onChange={(e) => setCode(e.target.value)} />
        <button className="btn primary" onClick={run} disabled={running} style={{ marginTop: "0.8rem" }}>
          {running ? "Analyzing…" : "▶ Analyze"}
        </button>

        {result && (
          <div style={{ marginTop: "1rem" }}>
            {result.error && (
              <div className="error-box" style={{ marginBottom: "0.6rem" }}>
                <strong>LLM call failed ({result.llm_provider})</strong>
                <br />{result.error}
                <br /><span style={{ opacity: 0.8 }}>Check your API key in .env.</span>
              </div>
            )}

            <div className="result-card"><strong>LLM summary</strong> ({result.llm_provider}): {result.llm_summary || "(none)"}</div>
            <div className="result-card"><strong>Check run:</strong> {result.check.conclusion.toUpperCase()} — {result.check.summary}</div>
            <div className="result-card">
              <strong>Labels applied:</strong>{" "}
              {result.labels.map((l) => <span key={l} className="badge commented" style={{ marginRight: 4 }}>{l}</span>)}
            </div>
            <div className="result-card">
              <strong>Auto-approve:</strong> {result.auto_approve ? "✅ Yes (minor PR, nothing blocking)" : "❌ No"}
            </div>

            {result.flagged_issues_count > 0 && (
              <div className="result-card" style={{ opacity: 0.8 }}>
                🔍 {result.flagged_issues_count} finding(s) discarded by the anti-hallucination filter (low confidence / not grounded in the diff).
              </div>
            )}

            {result.issues.length > 0 ? (
              <>
                <h3>Issues found ({result.issues.length})</h3>
                {result.issues.map((issue, i) => (
                  <div className="result-card" key={i}>
                    <SeverityBadge sev={issue.severity} /> <strong>{issue.filename}:{issue.line}</strong>
                    <br />{issue.message}
                    {issue.suggestion && <pre className="suggestion">{issue.suggestion}</pre>}
                  </div>
                ))}
              </>
            ) : !result.error && (
              <div className="result-card">✅ No issues found.</div>
            )}

            {result.pattern_matches.length > 0 && (
              <>
                <h3>Pattern matches (local detection)</h3>
                {result.pattern_matches.map((m, i) => (
                  <div className="result-card" key={i}>
                    <SeverityBadge sev={m.severity} /> <strong>line {m.line}</strong> — {m.message}{" "}
                    <span style={{ opacity: 0.7 }}>({m.pattern_name})</span>
                  </div>
                ))}
              </>
            )}

            {result.lint_issues.length > 0 && (
              <>
                <h3>Linter warnings ({result.lint_issues.length})</h3>
                {result.lint_issues.map((l, i) => (
                  <div className="result-card" key={i}>
                    <SeverityBadge sev={l.severity === "error" ? "critical" : l.severity} /> line {l.line} ({l.rule}) — {l.message}
                  </div>
                ))}
              </>
            )}
          </div>
        )}
      </div>
    </>
  );
}
