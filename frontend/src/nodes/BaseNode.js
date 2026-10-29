import { Handle, Position, useReactFlow } from "reactflow";

import { useStore } from "../store";
import { previewValue } from "../utils";
import { NODE_DEFINITIONS } from "./definitions";

const STATUS_LABEL = {
  pending: "Queued",
  running: "Running",
  completed: "Done",
  failed: "Failed",
  skipped: "Skipped",
};

const handleTop = (index, count) => `${((index + 1) / (count + 1)) * 100}%`;

export const BaseNode = ({ id, type, inputs = [], outputs = [], width = 260, children, showPreview = true }) => {
  const definition = NODE_DEFINITIONS[type];
  const result = useStore((state) => state.nodeResults[id]);
  const { deleteElements } = useReactFlow();
  const status = result?.status;

  return (
    <div
      className={`nf-node nf-group-${definition.group.toLowerCase()}${status ? ` is-${status}` : ""}`}
      style={{ width }}
    >
      {inputs.map((name, index) => (
        <Handle key={name} type="target" position={Position.Left} id={name} style={{ top: handleTop(index, inputs.length) }}>
          <span className="nf-handle-label is-left">{name}</span>
        </Handle>
      ))}

      <div className="nf-node-header">
        <span className="nf-node-title">{definition.label}</span>
        {status && <span className={`nf-badge is-${status}`}>{STATUS_LABEL[status]}</span>}
        <button
          type="button"
          className="nf-node-delete nodrag"
          title="Delete node"
          aria-label={`Delete ${definition.label} node`}
          onClick={() => deleteElements({ nodes: [{ id }] })}
        >
          ×
        </button>
      </div>

      <div className="nf-node-body">{children}</div>

      {status === "failed" && result.error && <div className="nf-node-error">{result.error}</div>}
      {showPreview && status === "completed" && result.output !== undefined && (
        <div className="nf-node-preview" title="Latest output">
          {previewValue(result.output) || "(empty)"}
        </div>
      )}

      {outputs.map((name, index) => (
        <Handle key={name} type="source" position={Position.Right} id={name} style={{ top: handleTop(index, outputs.length) }}>
          <span className="nf-handle-label is-right">{name}</span>
        </Handle>
      ))}
    </div>
  );
};
