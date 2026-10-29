import { DRAG_MIME } from "./ui";

export const DraggableNode = ({ type, label, description, onAdd }) => {
  const onDragStart = (event) => {
    event.dataTransfer.setData(DRAG_MIME, type);
    event.dataTransfer.effectAllowed = "move";
  };

  return (
    <div
      className="nf-lib-item"
      role="button"
      tabIndex={0}
      draggable
      title={`${description} (drag or click to add)`}
      onDragStart={onDragStart}
      onClick={() => onAdd(type)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onAdd(type);
        }
      }}
    >
      <span className="nf-lib-icon">{label.charAt(0)}</span>
      <span className="nf-lib-label">{label}</span>
    </div>
  );
};
