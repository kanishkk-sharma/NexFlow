import { BaseNode } from "./BaseNode";
import { Field, TextArea, useNodeField } from "./fields";

export const CodeNode = ({ id, data }) => {
  const set = useNodeField(id);
  return (
    <BaseNode id={id} type="code" inputs={["input"]} outputs={["result"]} width={290}>
      <Field
        label="Expression"
        hint="One Python-style expression using `input`. Allowed: math, comparisons, comprehensions, len/str/int/sum/min/max…, string methods, json_dumps/json_loads."
      >
        <TextArea value={data.code} onChange={set("code")} rows={4} mono placeholder="input * 2" />
      </Field>
    </BaseNode>
  );
};
