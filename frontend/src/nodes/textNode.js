import { useEffect, useMemo, useRef } from "react";
import { useUpdateNodeInternals } from "reactflow";

import { extractVariables } from "../utils";
import { BaseNode } from "./BaseNode";
import { Field, useNodeField } from "./fields";

export const TextNode = ({ id, data }) => {
  const set = useNodeField(id);
  const updateNodeInternals = useUpdateNodeInternals();
  const textareaRef = useRef(null);
  const text = data.text ?? "";
  const variables = useMemo(() => extractVariables(text), [text]);
  const variableKey = variables.join("|");
  const width = Math.min(420, Math.max(260, 220 + Math.min(text.length * 2, 160)));

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [text, width]);

  // React Flow must re-measure handles whenever the variable list changes.
  useEffect(() => {
    updateNodeInternals(id);
  }, [id, variableKey, updateNodeInternals]);

  return (
    <BaseNode id={id} type="text" inputs={variables} outputs={["output"]} width={width}>
      <Field label="Text" hint={variables.length ? `Variables: ${variables.join(", ")}` : "Use {{name}} to add an input"}>
        <textarea
          ref={textareaRef}
          className="nf-input nf-textarea nodrag nowheel nf-autosize"
          value={text}
          onChange={set("text")}
          rows={2}
          spellCheck={false}
          placeholder="Hello {{name}}!"
        />
      </Field>
    </BaseNode>
  );
};
