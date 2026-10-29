import { BaseNode } from "./BaseNode";
import { Field, TextArea, TextInput, useNodeField } from "./fields";

export const WebhookNode = ({ id, data }) => {
  const set = useNodeField(id);
  return (
    <BaseNode id={id} type="webhook" inputs={["payload"]} outputs={["result"]} width={280}>
      <Field label="URL">
        <TextInput value={data.url} onChange={set("url")} placeholder="https://hooks.example.com/…" />
      </Field>
      <Field label="Headers (JSON)">
        <TextArea value={data.headers} onChange={set("headers")} rows={2} mono />
      </Field>
      <Field label="Payload (JSON)" hint="Used when the 'payload' input is not connected">
        <TextArea value={data.payload} onChange={set("payload")} rows={2} mono placeholder='{"event": "done"}' />
      </Field>
    </BaseNode>
  );
};
