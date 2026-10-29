import { useStore } from "./store";
import { formatDuration, stringifyValue } from "./utils";

const STATUS_TEXT = { running: "Running…", success: "Succeeded", failed: "Failed", cancelled: "Cancelled" };
const ROW_LABEL = { pending: "Queued", running: "Running", completed: "Done", failed: "Failed", skipped: "Skipped" };

export const ResultsPanel = () => {
  const panelOpen = useStore((s) => s.panelOpen);
  const runStatus = useStore((s) => s.runStatus);
  const runError = useStore((s) => s.runError);
  const runOrder = useStore((s) => s.runOrder);
  const runOutputs = useStore((s) => s.runOutputs);
  const runSummary = useStore((s) => s.runSummary);
  const nodeResults = useStore((s) => s.nodeResults);
  const setPanelOpen = useStore((s) => s.setPanelOpen);
  const clearRun = useStore((s) => s.clearRun);

  if (!panelOpen) return null;

  const ids = runOrder.length ? runOrder : Object.keys(nodeResults);
  const outputEntries = Object.entries(runOutputs);

  return (
    <section className="nf-panel" aria-label="Run results">
      <div className="nf-panel-header">
        <span className={`nf-status-pill is-${runStatus}`}>{STATUS_TEXT[runStatus] ?? "Idle"}</span>
        {runSummary && (
          <span className="nf-muted">
            {runSummary.executed} ran
            {runSummary.skipped ? ` · ${runSummary.skipped} skipped` : ""} · {formatDuration(runSummary.duration_ms)}
          </span>
        )}
        <div className="nf-spacer" />
        {runStatus !== "running" && (
          <button type="button" className="nf-btn is-ghost" onClick={clearRun}>
            Clear
          </button>
        )}
        <button type="button" className="nf-icon-btn" onClick={() => setPanelOpen(false)} aria-label="Hide results">
          ×
        </button>
      </div>

      <div className="nf-panel-body">
        {runError && (
          <div className="nf-alert is-error" role="alert">
            {runError}
          </div>
        )}

        {outputEntries.length > 0 && (
          <div className="nf-outputs">
            <div className="nf-section-title">Outputs</div>
            {outputEntries.map(([name, value]) => (
              <div className="nf-output-card" key={name}>
                <div className="nf-output-name">{name}</div>
                <pre className="nf-pre">{stringifyValue(value) || "(empty)"}</pre>
              </div>
            ))}
          </div>
        )}

        <div className="nf-section-title">Steps</div>
        <div className="nf-steps">
          {ids.map((id, index) => {
            const result = nodeResults[id] ?? { status: "pending" };
            const hasDetails = result.output !== undefined || result.error || result.reason;
            return (
              <details className={`nf-step is-${result.status}`} key={id}>
                <summary>
                  <span className="nf-step-index">{result.position ?? index + 1}</span>
                  <span className="nf-step-name">{id}</span>
                  <span className="nf-muted">{result.node_type}</span>
                  <span className="nf-spacer" />
                  <span className="nf-muted">{formatDuration(result.duration_ms)}</span>
                  <span className={`nf-badge is-${result.status}`}>{ROW_LABEL[result.status] ?? result.status}</span>
                </summary>
                {hasDetails && (
                  <div className="nf-step-details">
                    {result.error && <div className="nf-alert is-error">{result.error}</div>}
                    {result.reason && <div className="nf-muted">{result.reason}</div>}
                    {result.output !== undefined && <pre className="nf-pre">{stringifyValue(result.output) || "(empty)"}</pre>}
                  </div>
                )}
              </details>
            );
          })}
        </div>
      </div>
    </section>
  );
};
