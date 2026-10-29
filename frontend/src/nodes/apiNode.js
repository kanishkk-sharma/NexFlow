import { BaseNode } from "./BaseNode";
import { Field, Select, TextArea, TextInput, useNodeField } from "./fields";

const METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"];

export const APINode = ({ id, data }) => {
  const set = useNodeField(id);
  const method = data.method ?? "GET";
  const hasBody = ["POST", "PUT", "PATCH"].includes(method);
  return (
    <BaseNode id={id} type="api" inputs={["request"]} outputs={["response"]} width={290}>
      <Field label="Method">
        <Select value={method} onChange={set("method")} options={METHODS} />
      </Field>
      <Field label="URL" hint="{{request}} in the URL is replaced by the connected value">
        <TextInput value={data.url} onChange={set("url")} placeholder="https://api.example.com/items" />
      </Field>
      <Field label="Headers (JSON)">
        <TextArea value={data.headers} onChange={set("headers")} rows={2} mono placeholder='{"Authorization": "Bearer …"}' />
      </Field>
      {hasBody && (
        <Field label="Body" hint="Empty body + connected 'request' sends the request value">
          <TextArea value={data.body} onChange={set("body")} rows={3} mono placeholder='{"name": "{{request}}"}' />
        </Field>
      )}
    </BaseNode>
  );
};
