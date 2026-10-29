import { useCallback, useEffect, useState } from "react";

import * as api from "./api";
import { ConfirmDialog, Modal } from "./Modal";
import { useStore } from "./store";

export const WorkflowManager = ({ onClose }) => {
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openingId, setOpeningId] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);

  const currentId = useStore((s) => s.workflowId);
  const loadWorkflow = useStore((s) => s.loadWorkflow);
  const newWorkflow = useStore((s) => s.newWorkflow);
  const confirmDiscard = useStore((s) => s.confirmDiscard);
  const notify = useStore((s) => s.notify);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setWorkflows(await api.listWorkflows());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const open = async (workflow) => {
    if (workflow.id !== currentId && !confirmDiscard()) return;
    setOpeningId(workflow.id);
    try {
      loadWorkflow(await api.getWorkflow(workflow.id));
      onClose();
    } catch (err) {
      notify("error", `Could not open workflow: ${err.message}`);
      setOpeningId(null);
    }
  };

  const remove = async () => {
    setDeleting(true);
    try {
      await api.deleteWorkflow(deleteTarget.id);
      if (deleteTarget.id === currentId) newWorkflow();
      setWorkflows((list) => list.filter((w) => w.id !== deleteTarget.id));
      notify("success", `Deleted “${deleteTarget.name}”`);
      setDeleteTarget(null);
    } catch (err) {
      notify("error", `Could not delete: ${err.message}`);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <>
      <Modal title="Your workflows" subtitle="Open or delete saved workflows" variant="drawer" onClose={onClose}>
        {loading && <div className="nf-center-note">Loading workflows…</div>}

        {!loading && error && (
          <div className="nf-alert is-error">
            {error}
            <button type="button" className="nf-btn" onClick={refresh}>
              Retry
            </button>
          </div>
        )}

        {!loading && !error && workflows.length === 0 && (
          <div className="nf-center-note">
            <strong>No saved workflows yet</strong>
            <div>Build something and press Save to see it here.</div>
          </div>
        )}

        {!loading &&
          !error &&
          workflows.map((workflow) => (
            <div key={workflow.id} className={`nf-wf-card${workflow.id === currentId ? " is-current" : ""}`}>
              <div className="nf-wf-name">{workflow.name}</div>
              <div className="nf-muted">
                {workflow.node_count} nodes · {workflow.edge_count} connections
              </div>
              <div className="nf-muted">Updated {new Date(workflow.updated_at).toLocaleString()}</div>
              <div className="nf-wf-actions">
                <button type="button" className="nf-btn" onClick={() => open(workflow)} disabled={openingId === workflow.id}>
                  {openingId === workflow.id ? "Opening…" : workflow.id === currentId ? "Reload" : "Open"}
                </button>
                <button type="button" className="nf-btn is-danger-outline" onClick={() => setDeleteTarget(workflow)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
      </Modal>

      {deleteTarget && (
        <ConfirmDialog
          title="Delete workflow?"
          message={`“${deleteTarget.name}” will be permanently deleted. This cannot be undone.`}
          confirmLabel="Delete"
          danger
          busy={deleting}
          onConfirm={remove}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </>
  );
};
