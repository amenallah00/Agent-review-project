export function Logo({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" xmlns="http://www.w3.org/2000/svg">
      {/* Hex "node" badge — reads as both a security shield and a circuit/tech node. */}
      <path
        d="M14 1.3 L25.1 7.65 V20.35 L14 26.7 L2.9 20.35 V7.65 Z"
        fill="var(--brand)"
      />
      {/* Eye formed from two mirrored code-bracket curves — vigilance + code, at once. */}
      <path
        d="M6.2 14 C9 9.6 19 9.6 21.8 14 C19 18.4 9 18.4 6.2 14 Z"
        fill="var(--panel)"
      />
      {/* Cursor-bar pupil — a blinking editor caret doubling as the eye's pupil. */}
      <rect x="12.7" y="10.9" width="2.6" height="6.2" rx="1.3" fill="var(--brand)" />
    </svg>
  );
}