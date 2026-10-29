import { useCallback, useEffect, useMemo } from "react";
import ReactFlow, { Background, Controls, MiniMap, useReactFlow } from "reactflow";

import { nodeTypes } from "./nodes";
import { NODE_DEFINITIONS } from "./nodes/definitions";
import { useStore } from "./store";

export const GRID_SIZE = 20;
export const DRAG_MIME = "application/x-nexflow-node";

const proOptions = { hideAttribution: true };
const snapGrid = [GRID_SIZE, GRID_SIZE];
const GROUP_COLORS = { core: "#6366f1", ai: "#a855f7", integrations: "#0ea5e9", logic: "#f59e0b" };

export const snap = (value) => Math.round(value / GRID_SIZE) * GRID_SIZE;

export const PipelineUI = () => {
  const nodes = useStore((s) => s.nodes);
  const edges = useStore((s) => s.edges);
  const nodeResults = useStore((s) => s.nodeResults);
  const darkMode = useStore((s) => s.darkMode);
  const viewVersion = useStore((s) => s.viewVersion);
  const onNodesChange = useStore((s) => s.onNodesChange);
  const onEdgesChange = useStore((s) => s.onEdgesChange);
  const onConnect = useStore((s) => s.onConnect);
  const isValidConnection = useStore((s) => s.isValidConnection);
  const addNodeOfType = useStore((s) => s.addNodeOfType);
  const pushHistory = useStore((s) => s.pushHistory);
  const { screenToFlowPosition, fitView } = useReactFlow();

  // Frame the whole graph after a workflow is loaded.
  useEffect(() => {
    if (viewVersion === 0) return undefined;
    const frame = requestAnimationFrame(() => fitView({ padding: 0.25, maxZoom: 1 }));
    return () => cancelAnimationFrame(frame);
  }, [viewVersion, fitView]);

  // Colour connections by execution progress.
  const displayEdges = useMemo(
    () =>
      edges.map((edge) => {
        const from = nodeResults[edge.source]?.status;
        const to = nodeResults[edge.target]?.status;
        if (from === "completed" && to === "running") {
          return { ...edge, animated: true, style: { stroke: "#2563eb", strokeWidth: 2 } };
        }
        if (from === "completed" && to === "completed") return { ...edge, style: { stroke: "#16a34a", strokeWidth: 2 } };
        if (to === "skipped") return { ...edge, style: { stroke: "#94a3b8", strokeDasharray: "5 4" } };
        return edge;
      }),
    [edges, nodeResults]
  );

  const onDrop = useCallback(
    (event) => {
      event.preventDefault();
      const type = event.dataTransfer.getData(DRAG_MIME);
      if (!NODE_DEFINITIONS[type]) return;
      const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
      addNodeOfType(type, { x: snap(position.x), y: snap(position.y) });
    },
    [addNodeOfType, screenToFlowPosition]
  );

  const onDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const miniMapColor = useCallback((node) => GROUP_COLORS[NODE_DEFINITIONS[node.type]?.group.toLowerCase()] ?? "#94a3b8", []);

  return (
    <div className="nf-flow">
      <ReactFlow
        nodes={nodes}
        edges={displayEdges}
        nodeTypes={nodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        isValidConnection={isValidConnection}
        onNodeDragStart={pushHistory}
        onDrop={onDrop}
        onDragOver={onDragOver}
        proOptions={proOptions}
        snapToGrid
        snapGrid={snapGrid}
        connectionLineType="smoothstep"
        minZoom={0.2}
        maxZoom={1.75}
        deleteKeyCode={["Backspace", "Delete"]}
      >
        <Background gap={GRID_SIZE} size={1.2} color={darkMode ? "#1e293b" : "#cbd5e1"} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeColor={miniMapColor} maskColor={darkMode ? "rgba(2,6,23,0.7)" : "rgba(241,245,249,0.7)"} />
      </ReactFlow>
      {nodes.length === 0 && (
        <div className="nf-empty">
          <div className="nf-empty-title">Start building your workflow</div>
          <div>Drag a node from the library above onto the canvas, or click one to add it.</div>
        </div>
      )}
    </div>
  );
};
