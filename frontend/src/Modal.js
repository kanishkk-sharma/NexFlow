import { useEffect, useRef } from "react";

export const Modal = ({ title, subtitle, onClose, children, footer, variant = "center" }) => {
  const panelRef = useRef(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose; // always call the latest handler without re-running the effect

  useEffect(() => {
    const previous = document.activeElement;
    panelRef.current?.focus();
    const onKey = (event) => {
      if (event.key === "Escape") closeRef.current();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      if (previous && previous.focus) previous.focus();
    };
  }, []);

  return (
    <div
      className={`nf-backdrop is-${variant}`}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) closeRef.current();
      }}
    >
      <div className={`nf-modal is-${variant}`} role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={panelRef}>
        <div className="nf-modal-header">
          <div>
            <h2>{title}</h2>
            {subtitle && <div className="nf-muted">{subtitle}</div>}
          </div>
          <button type="button" className="nf-icon-btn" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        <div className="nf-modal-body">{children}</div>
        {footer && <div className="nf-modal-footer">{footer}</div>}
      </div>
    </div>
  );
};

export const ConfirmDialog = ({ title, message, confirmLabel = "Confirm", danger = false, busy = false, confirmDisabled = false, onConfirm, onCancel }) => (
  <Modal
    title={title}
    onClose={busy ? () => {} : onCancel}
    footer={
      <>
        <button type="button" className="nf-btn" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="button" className={`nf-btn ${danger ? "is-danger" : "is-primary"}`} onClick={onConfirm} disabled={busy || confirmDisabled}>
          {busy ? "Please wait…" : confirmLabel}
        </button>
      </>
    }
  >
    <div className="nf-confirm-text">{message}</div>
  </Modal>
);
