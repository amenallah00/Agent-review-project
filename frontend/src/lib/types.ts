export type Role = "user" | "admin";
export type ReviewStatus = "approved" | "changes_requested" | "commented";
export type Severity = "info" | "warning" | "error" | "critical";
export type IssueCategory = "security" | "quality" | "performance" | "style" | "documentation";

export interface User {
  id: number;
  github_id: number;
  handle: string;
  name: string | null;
  avatar_url: string | null;
  role: Role;
  reviews_used: number;
}

export interface Stats {
  prs_reviewed: number;
  average_score: number;
  issues_caught: number;
  repos_connected: number;
  reviews_remaining: number | null;
}

export interface Repo {
  name: string;
  visibility: string;
  active: boolean;
  min_severity: Severity;
  languages: string[];
  excluded_files: string[];
  approve_threshold: number;
  changes_threshold: number;
  reviewer_map: Record<string, string>;
}

export interface Review {
  pr_number: number;
  pr_title: string | null;
  score: number;
  status: ReviewStatus;
  reviewed_at: string;
  issues_by_category: Partial<Record<IssueCategory, number>>;
  repo: string | null;
}

export interface RepoReviewsResponse {
  repo: string;
  average_score: number;
  trend: number[];
  issues_breakdown: Record<IssueCategory, number>;
  reviews: Review[];
  settings: Repo;
}

export interface GithubRepo {
  name: string;
  private: boolean;
  description: string | null;
}

export interface AdminStats {
  users: number;
  admins: number;
  repos_connected: number;
  repos_active: number;
  reviews_run: number;
  failed_reviews: number;
}

export interface AdminUser extends User {
  repos: number;
  reviews: number;
}

export interface AdminInstallation extends Repo {
  id: number;
  owner: string | null;
}

export interface AdminReview extends Review {
  owner: string | null;
}

export interface ReviewIssue {
  filename: string;
  line: number;
  severity: Severity;
  message: string;
  suggestion?: string | null;
}

export interface LintIssue {
  line: number;
  rule: string;
  message: string;
  severity: string;
}

export interface PatternMatch {
  line: number;
  pattern_name: string;
  severity: Severity;
  message: string;
}

export interface TestReviewResponse {
  error: string | null;
  llm_summary: string;
  llm_provider: string;
  lint_issues: LintIssue[];
  pattern_matches: PatternMatch[];
  issues: ReviewIssue[];
  flagged_issues_count: number;
  labels: string[];
  check: { conclusion: string; summary: string };
  auto_approve: boolean;
}
