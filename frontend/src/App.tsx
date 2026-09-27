import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedLayout } from "./components/ProtectedLayout";
import { Admin } from "./pages/Admin";
import { ConfigPage } from "./pages/ConfigPage";
import { Dashboard } from "./pages/Dashboard";
import { Landing } from "./pages/Landing";
import { RepoDetail } from "./pages/RepoDetail";
import { TestAgent } from "./pages/TestAgent";

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/dashboard" element={<ProtectedLayout />}>
        <Route index element={<Dashboard />} />
        <Route path="repos/:name" element={<RepoDetail />} />
        <Route path="test" element={<TestAgent />} />
        <Route path="config" element={<ConfigPage />} />
        <Route path="admin" element={<Admin />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
