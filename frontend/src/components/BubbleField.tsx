import { useMemo } from "react";

interface BubbleFieldProps {
  /** How many bubbles to render. */
  count?: number;
  /** Renders smaller and dimmer — for chrome like the sidebar rather than the hero. */
  subtle?: boolean;
}

/**
 * Ambient rising bubbles — the app's signature motion element. Size, position, speed and
 * drift are randomized once per mount via useMemo, so every reload feels a little different
 * without re-randomizing on every render.
 */
export function BubbleField({ count = 18, subtle = false }: BubbleFieldProps) {
  const bubbles = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => {
        const size = subtle ? 3 + Math.random() * 8 : 6 + Math.random() * 24;
        return {
          id: i,
          left: Math.round(Math.random() * 100),
          size: Math.round(size),
          duration: Math.round((subtle ? 14 : 10) + Math.random() * 14),
          delay: -Math.round(Math.random() * 20),
          drift: Math.round((Math.random() - 0.5) * 60),
          opacity: (subtle ? 0.12 + Math.random() * 0.2 : 0.18 + Math.random() * 0.4).toFixed(2),
        };
      }),
    [count, subtle],
  );

  return (
    <div className={`bubble-field${subtle ? " subtle" : ""}`} aria-hidden="true">
      {bubbles.map((b) => (
        <span
          key={b.id}
          className="bubble"
          style={
            {
              left: `${b.left}%`,
              width: b.size,
              height: b.size,
              opacity: b.opacity,
              animationDuration: `${b.duration}s`,
              animationDelay: `${b.delay}s`,
              "--drift": `${b.drift}px`,
            } as Record<string, string | number>
          }
        />
      ))}
    </div>
  );
}