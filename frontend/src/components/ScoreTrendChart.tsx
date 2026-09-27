import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useTheme } from "../context/ThemeContext";
import type { Review } from "../lib/types";

interface Props {
  reviews: Review[];
}

interface Point {
  label: string;
  score: number;
  title: string;
  date: string;
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: Point }> }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div
      style={{
        background: "var(--panel)",
        border: "1px solid var(--border)",
        borderRadius: 8,
        padding: "0.5rem 0.7rem",
        fontSize: "0.78rem",
        boxShadow: "var(--shadow-lg)",
        maxWidth: 220,
      }}
    >
      <div style={{ fontWeight: 600 }}>
        {p.label} · score {p.score}
      </div>
      <div className="muted" style={{ marginTop: 2 }}>
        {p.title}
      </div>
    </div>
  );
}

export function ScoreTrendChart({ reviews }: Props) {
  const { theme } = useTheme();
  const brand = theme === "dark" ? "#FF6A1F" : "#E8590C";

  if (reviews.length === 0) {
    return (
      <div className="chart-empty muted">
        No score history yet. The trend appears here after your first reviewed Pull Request.
      </div>
    );
  }

  // reviews arrive newest-first from the API; charts read left-to-right chronologically.
  const data: Point[] = [...reviews].reverse().map((r) => ({
    label: `#${r.pr_number}`,
    score: r.score,
    title: r.pr_title ?? "(untitled)",
    date: r.reviewed_at,
  }));

  if (data.length === 1) {
    return (
      <div className="chart-single">
        <div className="chart-single-dot" style={{ background: brand }} />
        <span className="muted">Only one review so far — the trend line appears from your second.</span>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={110}>
      <AreaChart data={data} margin={{ top: 6, right: 4, left: 4, bottom: 0 }}>
        <defs>
          <linearGradient id="scoreFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={brand} stopOpacity={0.32} />
            <stop offset="100%" stopColor={brand} stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid
          stroke={theme === "dark" ? "rgba(255,255,255,0.07)" : "rgba(20,18,16,0.07)"}
          vertical={false}
        />
        <XAxis dataKey="label" hide />
        <YAxis domain={[0, 100]} hide />
        <Tooltip content={<CustomTooltip />} />
        <Area
          type="monotone"
          dataKey="score"
          stroke={brand}
          strokeWidth={2.5}
          fill="url(#scoreFill)"
          dot={{ r: 2.5, fill: brand, strokeWidth: 0 }}
          activeDot={{ r: 5, strokeWidth: 2, stroke: theme === "dark" ? "#141311" : "#fff" }}
          isAnimationActive
          animationDuration={900}
          animationEasing="ease-out"
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}