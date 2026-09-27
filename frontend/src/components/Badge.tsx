import type { ReviewStatus } from "../lib/types";

const LABELS: Record<ReviewStatus, string> = {
  approved: "Approved",
  changes_requested: "Changes requested",
  commented: "Commented",
};

export function StatusBadge({ status }: { status: ReviewStatus }) {
  return <span className={`badge ${status}`}>{LABELS[status] ?? status}</span>;
}
