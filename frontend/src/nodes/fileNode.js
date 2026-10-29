import { BaseNode } from "./BaseNode";
import { Field, Select, TextArea, TextInput, useNodeField } from "./fields";

export const FileNode = ({ id, data }) => {
  const set = useNodeField(id);
  const action = data.action ?? "read";
  return (
    <BaseNode id={id} type="file" inputs={["content"]} outputs={["result"]} width={270}>
      <Field label="Action">
        <Select value={action} onChange={set("action")} options={[["read", "Read"], ["write", "Write (overwrite)"], ["append", "Append"]]} />
      </Field>
      <Field label="Path" hint="Relative to your private workspace folder">
        <TextInput value={data.path} onChange={set("path")} placeholder="reports/output.txt" />
      </Field>
      {action !== "read" && (
        <Field label="Content" hint="Overridden by the 'content' input if connected">
          <TextArea value={data.content} onChange={set("content")} rows={2} />
        </Field>
      )}
    </BaseNode>
  );
};
