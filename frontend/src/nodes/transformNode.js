import { BaseNode } from "./BaseNode";
import { Field, Select, TextInput, useNodeField } from "./fields";

const OPERATIONS = [
  ["uppercase", "Uppercase"],
  ["lowercase", "Lowercase"],
  ["trim", "Trim whitespace"],
  ["reverse", "Reverse text"],
  ["length", "Length"],
  ["json", "To JSON string"],
  ["parse_json", "Parse JSON"],
  ["get_path", "Get field (path)"],
];

export const TransformNode = ({ id, data }) => {
  const set = useNodeField(id);
  const operation = data.operation ?? "uppercase";
  return (
    <BaseNode id={id} type="transform" inputs={["input"]} outputs={["output"]} width={250}>
      <Field label="Operation">
        <Select value={operation} onChange={set("operation")} options={OPERATIONS} />
      </Field>
      {operation === "get_path" && (
        <Field label="Path" hint="Dot notation, e.g. body.items.0.name">
          <TextInput value={data.path} onChange={set("path")} placeholder="body.title" />
        </Field>
      )}
    </BaseNode>
  );
};
