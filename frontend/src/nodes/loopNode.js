import { BaseNode } from "./BaseNode";
import { Field, Select, TextArea, useNodeField } from "./fields";

export const LoopNode = ({ id, data }) => {
  const set = useNodeField(id);
  const mode = data.mode ?? "template";
  return (
    <BaseNode id={id} type="loop" inputs={["items"]} outputs={["result"]} width={270}>
      <Field label="For each item">
        <Select value={mode} onChange={set("mode")} options={[["template", "Fill a template"], ["expression", "Evaluate an expression"]]} />
      </Field>
      {mode === "template" ? (
        <Field label="Template" hint="Use {{item}} and {{index}}">
          <TextArea value={data.template} onChange={set("template")} rows={2} />
        </Field>
      ) : (
        <Field label="Expression" hint="Variables: item, index">
          <TextArea value={data.expression} onChange={set("expression")} rows={2} mono />
        </Field>
      )}
      <div className="nf-hint">Input: a JSON list (or one item per line). Output: the list of results.</div>
    </BaseNode>
  );
};
