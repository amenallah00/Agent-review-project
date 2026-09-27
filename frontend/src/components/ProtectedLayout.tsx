import { useState } from "react";
import { Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ConnectRepoModal } from "./ConnectRepoModal";
import { AppHeader } from "./AppHeader";

export function ProtectedLayout() {
  const { user, loading } = useAuth();
  const [modalOpen, setModalOpen] = useState(false);
  const [reposVersion, setReposVersion] = useState(0);

  if (loading) {
    return <div className="centered-spinner">Loading…</div>;
  }

  if (!user) {
    window.location.href = "/";
    return null;
  }

  return (
    <div className="app-shell">
      <AppHeader onConnectRepo={() => setModalOpen(true)} />
      <main className="main">
        <Outlet context={{ bumpRepos: () => setModalOpen(true), reposVersion }} />
      </main>
      {modalOpen && (
        <ConnectRepoModal
          onClose={() => setModalOpen(false)}
          onConnected={() => setReposVersion((v) => v + 1)}
        />
      )}
    </div>
  );
}
