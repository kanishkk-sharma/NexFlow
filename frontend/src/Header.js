import { useState } from "react";

import { AccountDialog } from "./AccountDialog";
import { useStore } from "./store";

const SAVE_LABEL = { idle: "Save", saving: "Saving…", saved: "✓ Saved", error: "Retry save" };

export const Header = ({ onOpenManager }) => {
  const workflowName = useStore((s) => s.workflowName);
  const setWorkflowName = useStore((s) => s.setWorkflowName);
  const dirty = useStore((s) => s.dirty);
  const saveStatus = useStore((s) => s.saveStatus);
  const saveWorkflow = useStore((s) => s.saveWorkflow);
  const runStatus = useStore((s) => s.runStatus);
  const runWorkflow = useStore((s) => s.runWorkflow);
  const cancelRun = useStore((s) => s.cancelRun);
  const analyze = useStore((s) => s.analyze);
  const analyzing = useStore((s) => s.analyzing);
  const nodeCount = useStore((s) => s.nodes.length);
  const canUndo = useStore((s) => s.history.length > 0);
  const canRedo = useStore((s) => s.future.length > 0);
  const undo = useStore((s) => s.undo);
  const redo = useStore((s) => s.redo);
  const newWorkflow = useStore((s) => s.newWorkflow);
  const confirmDiscard = useStore((s) => s.confirmDiscard);
  const darkMode = useStore((s) => s.darkMode);
  const toggleDarkMode = useStore((s) => s.toggleDarkMode);
  const user = useStore((s) => s.user);
  const logout = useStore((s) => s.logout);
  const config = useStore((s) => s.config);
  const panelOpen = useStore((s) => s.panelOpen);
  const setPanelOpen = useStore((s) => s.setPanelOpen);

  const [accountOpen, setAccountOpen] = useState(false);
  const running = runStatus === "running";

  const handleNew = () => {
    if (confirmDiscard()) newWorkflow();
  };

  const handleLogout = () => {
    if (confirmDiscard()) logout();
  };

  return (
    <header className="nf-header">
      <div className="nf-brand">NexFlow</div>

      <input
        className="nf-input nf-name"
        value={workflowName}
        onChange={(e) => setWorkflowName(e.target.value)}
        placeholder="Workflow name"
        aria-label="Workflow name"
        maxLength={120}
      />
      <span className={`nf-dirty${dirty ? " is-dirty" : ""}`} title={dirty ? "You have unsaved changes" : "All changes saved"}>
        {dirty ? "● Unsaved" : "Saved"}
      </span>

      {config && (
        <div className="nf-chips">
          <span className={`nf-chip${config.llm_live ? " is-live" : ""}`} title={config.llm_live ? "LLM nodes call the configured API" : "OPENAI_API_KEY is not set: LLM nodes return mock text"}>
            LLM {config.llm_live ? "live" : "mock"}
          </span>
          <span className={`nf-chip${config.email_live ? " is-live" : ""}`} title={config.email_live ? "Email nodes send via SMTP" : "SMTP is not configured: Email nodes do a dry run"}>
            Email {config.email_live ? "live" : "dry-run"}
          </span>
        </div>
      )}

      <div className="nf-spacer" />

      <div className="nf-actions">
        <button type="button" className="nf-btn" onClick={undo} disabled={!canUndo} title="Undo (Ctrl+Z)">
          ↶
        </button>
        <button type="button" className="nf-btn" onClick={redo} disabled={!canRedo} title="Redo (Ctrl+Shift+Z)">
          ↷
        </button>
        <button type="button" className="nf-btn" onClick={handleNew}>
          New
        </button>
        <button type="button" className="nf-btn" onClick={onOpenManager}>
          Workflows
        </button>
        <button
          type="button"
          className={`nf-btn${saveStatus === "error" ? " is-danger" : ""}`}
          onClick={saveWorkflow}
          disabled={saveStatus === "saving"}
          title="Save (Ctrl+S)"
        >
          {SAVE_LABEL[saveStatus]}
        </button>
        <button type="button" className="nf-btn" onClick={analyze} disabled={analyzing || nodeCount === 0}>
          {analyzing ? "Analyzing…" : "Analyze"}
        </button>
        {running ? (
          <button type="button" className="nf-btn is-danger" onClick={cancelRun}>
            ■ Stop
          </button>
        ) : (
          <button type="button" className="nf-btn is-primary" onClick={runWorkflow} disabled={nodeCount === 0} title="Run (Ctrl+Enter)">
            ▶ Run
          </button>
        )}
        {!panelOpen && runStatus !== "idle" && !running && (
          <button type="button" className="nf-btn is-ghost" onClick={() => setPanelOpen(true)}>
            Results
          </button>
        )}
        <button type="button" className="nf-btn" onClick={toggleDarkMode} title="Toggle theme" aria-label="Toggle theme">
          {darkMode ? "☀" : "☾"}
        </button>
        <button type="button" className="nf-btn nf-user" onClick={() => setAccountOpen(true)} title={`${user?.email} - account settings`}>
          {user?.name}
        </button>
        <button type="button" className="nf-btn is-ghost" onClick={handleLogout}>
          Sign out
        </button>
      </div>
      {accountOpen && <AccountDialog onClose={() => setAccountOpen(false)} />}
    </header>
  );
};
