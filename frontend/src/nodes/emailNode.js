import { BaseNode } from "./BaseNode";
import { Field, TextArea, TextInput, useNodeField } from "./fields";

export const EmailNode = ({ id, data }) => {
  const set = useNodeField(id);
  return (
    <BaseNode id={id} type="email" inputs={["body"]} outputs={["result"]} width={280}>
      <Field label="To" hint="Comma-separated, up to 10 addresses">
        <TextInput value={data.to} onChange={set("to")} placeholder="user@example.com" />
      </Field>
      <Field label="Subject">
        <TextInput value={data.subject} onChange={set("subject")} placeholder="Subject" />
      </Field>
      <Field label="Body" hint="Overridden by the 'body' input if connected">
        <TextArea value={data.body} onChange={set("body")} rows={3} placeholder="Message…" />
      </Field>
    </BaseNode>
  );
};
