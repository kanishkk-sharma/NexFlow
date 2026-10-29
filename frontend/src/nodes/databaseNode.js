import { BaseNode } from "./BaseNode";
import { Field, TextArea, useNodeField } from "./fields";

export const DatabaseNode = ({ id, data }) => {
  const set = useNodeField(id);
  return (
    <BaseNode id={id} type="database" inputs={["query"]} outputs={["result"]} width={280}>
      <Field label="SQL query" hint="Sandbox with users, products and orders tables. Resets every run.">
        <TextArea value={data.query} onChange={set("query")} rows={4} mono placeholder="SELECT * FROM users" />
      </Field>
    </BaseNode>
  );
};
