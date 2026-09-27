import { useEffect, useRef, useState } from "react";

interface StatCardProps {
  label: string;
  value: number | string | null;
  loading?: boolean;
  /** Accent color driving the hover glow and top accent bar (defaults to the brand orange). */
  accent?: string;
}

/** Eases a number from its previous value to the next over ~500ms — makes stats feel alive, not static. */
function useAnimatedNumber(target: number | null): number | null {
  const [display, setDisplay] = useState(target);
  const prev = useRef(target);

  useEffect(() => {
    if (target === null) return;
    const from = prev.current ?? 0;
    const to = target;
    prev.current = target;
    if (from === to) {
      setDisplay(to);
      return;
    }
    const start = performance.now();
    const duration = 500;
    let raf: number;
    function tick(now: number) {
      const p = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setDisplay(Math.round(from + (to - from) * eased));
      if (p < 1) raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target]);

  return display;
}

export function StatCard({ label, value, loading, accent }: StatCardProps) {
  const numeric = typeof value === "number" ? value : null;
  const animated = useAnimatedNumber(numeric);

  return (
    <div className="stat-card panel" style={accent ? ({ "--accent": accent } as Record<string, string>) : undefined}>
      <div className="stat-card-label muted">{label}</div>
      {loading ? (
        <div className="skeleton" style={{ height: 28, width: 48, marginTop: 6 }} />
      ) : (
        <div className="stat-card-value">{numeric !== null ? animated : (value ?? "—")}</div>
      )}
    </div>
  );
}