import type {
  AdminInstallation,
  AdminReview,
  AdminStats,
  AdminUser,
  GithubRepo,
  Repo,
  RepoReviewsResponse,
  Review,
  Stats,
  TestReviewResponse,
  User,
} from "./types";

const API_BASE = import.meta.env.VITE_API_URL || "";

const TOKEN_KEY = "cs_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/**
 * Session sans cookie inter-domaine (cf. rapport §3.9.1) : le jeton est
 * transmis en en-tête `Authorization: Bearer`, jamais en cookie. Un 401
 * déclenche systématiquement une déconnexion — la session n'est plus valide.
 */
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });

  if (res.status === 401) {
    clearToken();
    window.location.href = "/";
    throw new ApiError(401, "Session expired");
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(res.status, body.detail ?? `Request failed (${res.status})`);
  }

  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  me: () => request<User>("/api/user"),
  stats: () => request<Stats>("/api/stats"),
  repos: () => request<{ repos: Repo[]; recent_reviews: Review[] }>("/api/repos"),
  githubRepos: () => request<{ repos: GithubRepo[] }>("/api/github/repos"),
  repo: (name: string) => request<Repo>(`/api/repos/${encodeURIComponent(name)}`),
  repoReviews: (name: string) => request<RepoReviewsResponse>(`/api/repos/${encodeURIComponent(name)}/reviews`),
  connectRepo: (name: string) =>
    request<Repo>(`/api/repos/${encodeURIComponent(name)}/enable`, { method: "POST" }),
  disconnectRepo: (name: string) =>
    request<{ deleted: string }>(`/api/repos/${encodeURIComponent(name)}`, { method: "DELETE" }),
  updateSettings: (name: string, partial: Partial<Repo>) =>
    request<Repo>(`/api/repos/${encodeURIComponent(name)}/settings`, {
      method: "PUT",
      body: JSON.stringify(partial),
    }),
  setActive: (name: string, active: boolean) =>
    request<{ name: string; active: boolean }>(`/api/repos/${encodeURIComponent(name)}/active`, {
      method: "PUT",
      body: JSON.stringify({ active }),
    }),
  adminStats: () => request<AdminStats>("/api/admin/stats"),
  adminUsers: () => request<{ users: AdminUser[] }>("/api/admin/users"),
  adminInstallations: () => request<{ installations: AdminInstallation[] }>("/api/admin/installations"),
  adminReviews: () => request<{ reviews: AdminReview[] }>("/api/admin/reviews"),
  adminUpdateRole: (userId: number, role: string) =>
    request<{ id: number; handle: string; role: string }>(`/api/admin/users/${userId}/role`, {
      method: "PUT",
      body: JSON.stringify({ role }),
    }),
  adminDeleteUser: (userId: number) =>
    request<{ deleted: number }>(`/api/admin/users/${userId}`, { method: "DELETE" }),
  adminResetQuota: (userId: number) =>
    request<{ id: number; handle: string; reviews_used: number }>(`/api/admin/users/${userId}/reset-quota`, {
      method: "PUT",
    }),
  adminDeleteInstallation: (installationId: number) =>
    request<{ deleted: number }>(`/api/admin/installations/${installationId}`, { method: "DELETE" }),
  adminToggleInstallation: (installationId: number, active: boolean) =>
    request<{ id: number; repo_name: string; active: boolean }>(
      `/api/admin/installations/${installationId}/active`,
      { method: "PUT", body: JSON.stringify({ active }) },
    ),
  config: () => request<Record<string, unknown>>("/api/config"),
  metrics: () => request<Record<string, unknown>>("/api/metrics"),
  testReview: (filename: string, code: string) =>
    request<TestReviewResponse>("/api/test-review", {
      method: "POST",
      body: JSON.stringify({ filename, code }),
    }),
};
