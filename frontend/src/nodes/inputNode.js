import { BaseNode } from "./BaseNode";
import { Field, Select, TextArea, TextInput, useNodeField } from "./fields";

export const InputNode = ({ id, data }) => {
  const set = useNodeField(id);
  const type = data.inputType ?? "Text";
  return (
    <BaseNode id={id} type="customInput" outputs={["value"]} width={250}>
      <Field label="Name">
        <TextInput value={data.inputName} onChange={set("inputName")} placeholder="input" />
      </Field>
      <Field label="Type">
        <Select value={type} onChange={set("inputType")} options={["Text", "Number", "JSON"]} />
      </Field>
      <Field label="Value">
        <TextArea
          value={data.inputValue}
          onChange={set("inputValue")}
          rows={3}
          mono={type === "JSON"}
          placeholder={type === "JSON" ? '{"key": "value"}' : type === "Number" ? "42" : "Enter a value…"}
        />
      </Field>
    </BaseNode>
  );
};
