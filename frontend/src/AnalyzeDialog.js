import { Modal } from "./Modal";
import { useStore } from "./store";

export const AnalyzeDialog = () => {
  const analysis = useStore((s) => s.analysis);
  const close = useStore((s) => s.closeAnalysis);
  if (!analysis) return null;

  const valid = analysis.errors.length === 0;
  return (
    <Modal
      title="Pipeline analysis"
      onClose={close}
      footer={
        <button type="button" className="nf-btn" onClick={close}>
          Close
        </button>
      }
    >
      <div className="nf-stats">
        <div className="nf-stat">
          <div className="nf-muted">Nodes</div>
          <strong>{analysis.num_nodes}</strong>
        </div>
        <div className="nf-stat">
          <div className="nf-muted">Connections</div>
          <strong>{analysis.num_edges}</strong>
        </div>
      </div>

      <div className={`nf-alert ${valid ? "is-success" : "is-error"}`}>
        {valid ? "✓ Valid DAG — ready to run" : "✕ This workflow cannot run yet"}
      </div>

      {analysis.errors.length > 0 && (
        <>
          <div className="nf-section-title">Errors</div>
          <ul className="nf-list is-error">
            {analysis.errors.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        </>
      )}

      {analysis.warnings.length > 0 && (
        <>
          <div className="nf-section-title">Warnings</div>
          <ul className="nf-list is-warn">
            {analysis.warnings.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        </>
      )}

      {analysis.execution_order.length > 0 && (
        <>
          <div className="nf-section-title">Execution order</div>
          <ol className="nf-order">
            {analysis.execution_order.map((id) => (
              <li key={id}>{id}</li>
            ))}
          </ol>
        </>
      )}
    </Modal>
  );
};
