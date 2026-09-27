interface Props {
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Replaces the browser's native `confirm()` — that dialog is styled by the
 * OS/browser chrome (see the "localhost:8000 says…" popup), not by the app,
 * and can't be themed. This renders inline, respects light/dark mode, and
 * matches the rest of the design system (same shell as ConnectRepoModal).
 */
export function ConfirmDialog({ title, message, confirmLabel = "Confirm", danger, onConfirm, onCancel }: Props) {
  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-card" style={{ width: "min(420px, 92vw)" }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <strong>{title}</strong>
          <button onClick={onCancel}>✕</button>
        </div>
        <div className="modal-body">
          <p style={{ margin: "0 0 1.2rem", fontSize: "0.88rem", lineHeight: 1.5 }}>{message}</p>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.6rem" }}>
            <button className="btn ghost" onClick={onCancel}>Cancel</button>
            <button className={`btn ${danger ? "danger" : "primary"}`} onClick={onConfirm}>
              {confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}