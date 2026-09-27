import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { Logo } from "./Logo";

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

interface AppHeaderProps {
  onConnectRepo: () => void;
}

export function AppHeader({ onConnectRepo }: AppHeaderProps) {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const navigate = useNavigate();
  const initials = (user?.name || user?.handle || "??")
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <header className="app-header">
      <div className="sidebar-brand" style={{ padding: 0, cursor: "pointer" }} onClick={() => navigate("/dashboard")}>
        <Logo />
        CodeSentinel
      </div>
      <nav className="app-nav">
        <NavLink to="/dashboard" end style={({ isActive }) => ({ color: isActive ? "var(--text)" : "var(--muted)" })}>
          Dashboard
        </NavLink>
        <button onClick={onConnectRepo} style={{ display: "flex", alignItems: "center", gap: "0.25rem" }}>
          + Repo
        </button>
        <NavLink to="/dashboard/test" style={({ isActive }) => ({ color: isActive ? "var(--text)" : "var(--muted)" })}>
          Test Agent
        </NavLink>
        <NavLink to="/dashboard/config" style={({ isActive }) => ({ color: isActive ? "var(--text)" : "var(--muted)" })}>
          Configuration
        </NavLink>
        {user?.role === "admin" && (
          <NavLink to="/dashboard/admin" style={({ isActive }) => ({ color: isActive ? "var(--text)" : "var(--muted)" })}>
            Admin
          </NavLink>
        )}
        <button className="theme-toggle" onClick={toggle} title="Toggle dark mode" style={{ marginLeft: "1rem" }}>
          {theme === "dark" ? SUN : MOON}
        </button>
        <button className="sidebar-footer" onClick={logout} title="Sign out" style={{ border: "none", background: "none", margin: 0, padding: 0, display: "flex", alignItems: "center" }}>
          <div className="avatar" style={{ width: 32, height: 32, margin: 0 }}>{initials}</div>
        </button>
      </nav>
    </header>
  );
}
