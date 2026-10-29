import { BaseNode } from "./BaseNode";
import { Field, TextInput, useNodeField } from "./fields";

export const DelayNode = ({ id, data }) => {
  const set = useNodeField(id);
  return (
    <BaseNode id={id} type="delay" inputs={["input"]} outputs={["output"]} width={230}>
      <Field label="Delay (ms)" hint="Maximum 30000. The input is passed through unchanged.">
        <TextInput type="number" min="0" max="30000" value={data.delay} onChange={set("delay")} />
      </Field>
    </BaseNode>
  );
};
