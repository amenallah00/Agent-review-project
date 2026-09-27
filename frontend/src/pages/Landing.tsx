import { useEffect } from "react";
import { useTheme } from "../context/ThemeContext";
import { useToast } from "../context/ToastContext";
import { BubbleField } from "../components/BubbleField";
import { Logo } from "../components/Logo";

const SUN = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </svg>
);
const MOON = (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
  </svg>
);

const GITHUB_MARK = (
  <svg width={16} height={16} viewBox="0 0 16 16" fill="currentColor">
    <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
  </svg>
);

export function Landing() {
  const { theme, toggle } = useTheme();
  const showToast = useToast();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("auth_error") === "1") {
      showToast("GitHub sign-in failed — please try again.", true);
      params.delete("auth_error");
      const query = params.toString();
      window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
    }
  }, [showToast]);

  return (
    <>
      <header className="app-header">
        <div className="sidebar-brand" style={{ padding: 0 }}>
          <Logo />
          CodeSentinel
        </div>
        <nav className="app-nav">
          <a href="#features">Features</a>
          <a href="#docs">Docs</a>
          <a href="#pricing">Pricing</a>
          <button className="theme-toggle" onClick={toggle} title="Toggle dark mode">
            {theme === "dark" ? SUN : MOON}
          </button>
          <a className="btn ghost" href={`${import.meta.env.VITE_API_URL}/auth/github`}>Sign in</a>
        </nav>
      </header>

      <section className="hero">
        <BubbleField count={20} />
        <div className="live-pill">
          <span className="blip" /> Live · Now reviewing on your repositories
        </div>
        <h1>
          AI Code Review
          <br />
          for <span className="accent">GitHub</span>
        </h1>
        <p>
          CodeSentinel reviews every pull request the moment it opens — flagging security holes,
          scoring quality, and labeling changes automatically, so your team ships with confidence.
        </p>
        <div className="hero-ctas">
          <a className="btn primary" href={`${import.meta.env.VITE_API_URL}/auth/github`}>
            {GITHUB_MARK} Login with GitHub
          </a>
          <a className="btn ghost" href="#demo">View demo →</a>
        </div>
        <div className="fineprint">Free for open source · No credit card required</div>
      </section>

      <div className="demo-wrap" id="demo">
        <div className="demo-card">
          <div className="demo-topbar">
            <div className="demo-dots"><span /><span /><span /></div>
            <div className="demo-path">github.com/acme/api-gateway/pull/482</div>
          </div>
          <div className="demo-body">
            <div className="demo-pr-row">
              <span className="demo-pr-badge">Open</span>
              <span className="demo-pr-title">Add JWT auth middleware to gateway #482</span>
            </div>
            <div className="demo-tags">
              <span className="demo-tag-crit">security: critical</span>
              <span className="demo-tag-changes">needs-changes</span>
            </div>
            <div style={{ marginTop: "0.8rem" }}>
              <div className="demo-line">14   const token = req.headers.authorization;</div>
              <div className="demo-line demo-del">15 - jwt.verify(token, secret, {"{"} algorithms: ['none'] {"}"})</div>
              <div className="demo-line demo-add">15 + jwt.verify(token, secret, {"{"} algorithms: ['RS256'] {"}"})</div>
            </div>
            <div className="demo-comment">
              <div className="who">
                🛡️ codesentinel-reviewer <span style={{ fontWeight: 400, color: "#8C8577" }}>bot · just now</span>
                <span className="badge-sev">Critical</span>
              </div>
              <p>
                Insecure JWT verification. Passing <code>algorithm: ['none']</code> disables signature
                checks entirely, allowing forged tokens. Pin to <code>'RS256'</code>.
              </p>
            </div>
          </div>
        </div>
      </div>

      <footer className="landing-footer">© 2026 CodeSentinel. Built on the agent-review pipeline.</footer>
    </>
  );
}