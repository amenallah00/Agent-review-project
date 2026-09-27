export type ScoreTier = "low" | "mid" | "high";

/** Shared score-color banding used everywhere a score is shown as a colored chip or dot. */
export function scoreTier(score: number): ScoreTier {
  if (score >= 80) return "high";
  if (score >= 60) return "mid";
  return "low";
}
