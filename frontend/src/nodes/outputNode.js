import { useStore } from "../store";
import { stringifyValue } from "../utils";
import { BaseNode } from "./BaseNode";
import { Field, TextInput, useNodeField } from "./fields";

export const OutputNode = ({ id, data }) => {
  const set = useNodeField(id);
  const result = useStore((state) => state.nodeResults[id]);
  const hasValue = result?.status === "completed";
  return (
    <BaseNode id={id} type="customOutput" inputs={["value"]} width={260} showPreview={false}>
      <Field label="Name">
        <TextInput value={data.outputName} onChange={set("outputName")} placeholder="output" />
      </Field>
      <div className="nf-result-box">
        <div className="nf-label">Result</div>
        <pre className="nf-result-text nowheel">
          {hasValue ? stringifyValue(result.output, 4000) || "(empty)" : "Run the workflow to see the value."}
        </pre>
      </div>
    </BaseNode>
  );
};
