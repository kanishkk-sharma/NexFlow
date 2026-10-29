import { BaseNode } from "./BaseNode";
import { Field, Select, TextInput, useNodeField } from "./fields";

const OPERATORS = [
  ["equals", "Equals"],
  ["not-equals", "Not equals"],
  ["contains", "Contains"],
  ["not-contains", "Does not contain"],
  ["greater-than", "Greater than"],
  ["less-than", "Less than"],
  ["is-empty", "Is empty"],
  ["is-not-empty", "Is not empty"],
];

export const ConditionNode = ({ id, data }) => {
  const set = useNodeField(id);
  const operator = data.operator ?? "equals";
  const needsValue = !["is-empty", "is-not-empty"].includes(operator);
  return (
    <BaseNode id={id} type="condition" inputs={["value"]} outputs={["true", "false"]} width={250}>
      <Field label="Test">
        <Select value={operator} onChange={set("operator")} options={OPERATORS} />
      </Field>
      {needsValue && (
        <Field label="Compare to">
          <TextInput value={data.compareValue} onChange={set("compareValue")} placeholder="Value…" />
        </Field>
      )}
      <div className="nf-hint">Only the matching branch runs; the other is skipped.</div>
    </BaseNode>
  );
};
