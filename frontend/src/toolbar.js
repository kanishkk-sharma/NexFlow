import { useMemo, useState } from "react";
import { useReactFlow } from "reactflow";

import { DraggableNode } from "./draggableNode";
import { NODE_TYPE_LIST } from "./nodes/definitions";
import { useStore } from "./store";
import { snap } from "./ui";

const GROUP_ORDER = ["Core", "AI", "Integrations", "Logic"];
const GRID_STEP = 24;

export const PipelineToolbar = () => {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(true);
  const addNodeOfType = useStore((s) => s.addNodeOfType);
  const { screenToFlowPosition } = useReactFlow();

  const groups = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matches = NODE_TYPE_LIST.filter(
      (n) => !needle || [n.label, n.type, n.group, n.description].some((v) => v.toLowerCase().includes(needle))
    );
    return GROUP_ORDER.map((group) => ({ group, items: matches.filter((n) => n.group === group) })).filter(
      (g) => g.items.length
    );
  }, [query]);

  const addAtCenter = (type) => {
    const canvas = document.querySelector(".nf-flow");
    const rect = canvas ? canvas.getBoundingClientRect() : { left: 0, top: 0, width: 800, height: 500 };
    const center = screenToFlowPosition({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
    const offset = (useStore.getState().nodes.length % 6) * GRID_STEP;
    addNodeOfType(type, { x: snap(center.x - 130 + offset), y: snap(center.y - 100 + offset) });
  };

  return (
    <section className="nf-library" aria-label="Node library">
      <div className="nf-library-bar">
        <button type="button" className="nf-btn is-ghost" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          {open ? "▾" : "▸"} Node library
        </button>
        {open && (
          <input
            type="search"
            className="nf-input nf-search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search nodes…"
            aria-label="Search nodes"
          />
        )}
        <span className="nf-muted nf-library-hint">Drag onto the canvas · Delete key removes the selection</span>
      </div>
      {open && (
        <div className="nf-library-groups">
          {groups.map(({ group, items }) => (
            <div className="nf-lib-group" key={group}>
              <div className="nf-lib-group-title">{group}</div>
              <div className="nf-lib-items">
                {items.map((n) => (
                  <DraggableNode key={n.type} type={n.type} label={n.label} description={n.description} onAdd={addAtCenter} />
                ))}
              </div>
            </div>
          ))}
          {groups.length === 0 && <span className="nf-muted">No nodes match “{query}”.</span>}
        </div>
      )}
    </section>
  );
};
