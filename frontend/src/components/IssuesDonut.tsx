import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { IssueCategory } from "../lib/types";

const CATEGORY_META: Record<IssueCategory, { label: string; color: string }> = {
  security: { label: "Security", color: "#EF4444" },
  quality: { label: "Quality", color: "#3B82F6" },
  performance: { label: "Performance", color: "#A855F7" },
  style: { label: "Style", color: "#F59E0B" },
  documentation: { label: "Documentation", color: "#22C55E" },
};

interface Props {
  breakdown: Record<string, number>;
}

export function IssuesDonut({ breakdown }: Props) {
  const entries = (Object.entries(breakdown) as [IssueCategory, number][]).filter(([, v]) => v > 0);
  const total = entries.reduce((sum, [, v]) => sum + v, 0);
  const data = entries.map(([cat, value]) => ({ name: CATEGORY_META[cat].label, value, color: CATEGORY_META[cat].color }));

  return (
    <div className="donut-row">
      <div className="donut-chart-wrap">
        <ResponsiveContainer width={120} height={120}>
          <PieChart>
            <Pie data={data.length ? data : [{ name: "none", value: 1, color: "var(--panel-2)" }]}
                 dataKey="value" innerRadius={38} outerRadius={58} startAngle={90} endAngle={-270} stroke="none">
              {(data.length ? data : [{ name: "none", value: 1, color: "var(--panel-2)" }]).map((d, i) => (
                <Cell key={i} fill={d.color} />
              ))}
            </Pie>
            {data.length > 0 && <Tooltip />}
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-total">{total}</div>
      </div>
      <div className="donut-legend">
        {(Object.keys(CATEGORY_META) as IssueCategory[]).map((cat) => (
          <div className="legend-row" key={cat}>
            <span className="legend-dot" style={{ background: CATEGORY_META[cat].color }} />
            {CATEGORY_META[cat].label}
            <span className="count">{breakdown[cat] ?? 0}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
