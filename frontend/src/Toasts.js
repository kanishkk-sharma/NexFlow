import { useStore } from "./store";

export const Toasts = () => {
  const toasts = useStore((s) => s.toasts);
  const dismiss = useStore((s) => s.dismissToast);
  return (
    <div className="nf-toasts" aria-live="polite">
      {toasts.map((toast) => (
        <div key={toast.id} className={`nf-toast is-${toast.kind}`} role="status">
          <span>{toast.message}</span>
          <button type="button" className="nf-toast-close" onClick={() => dismiss(toast.id)} aria-label="Dismiss">
            ×
          </button>
        </div>
      ))}
    </div>
  );
};
