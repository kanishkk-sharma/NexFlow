import { BaseNode } from "./BaseNode";
import { Field, TextArea, TextInput, useNodeField } from "./fields";

const MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"];

export const LLMNode = ({ id, data }) => {
  const set = useNodeField(id);
  const temperature = Number(data.temperature ?? 0.7);
  return (
    <BaseNode id={id} type="llm" inputs={["system", "prompt"]} outputs={["response"]} width={290}>
      <Field label="Model">
        <TextInput value={data.model} onChange={set("model")} list={`models-${id}`} placeholder="gpt-4o-mini" />
        <datalist id={`models-${id}`}>
          {MODELS.map((model) => (
            <option key={model} value={model} />
          ))}
        </datalist>
      </Field>
      <Field label={`Temperature: ${temperature.toFixed(1)}`}>
        <input
          className="nodrag"
          type="range" min="0" max="1" step="0.1"
          value={temperature}
          onChange={(e) => set("temperature")({ target: { value: Number(e.target.value) } })}
        />
      </Field>
      <Field label="System prompt" hint="Overridden by the 'system' input if connected">
        <TextArea value={data.systemPrompt} onChange={set("systemPrompt")} rows={2} placeholder="You are a helpful assistant." />
      </Field>
      <Field label="Prompt" hint="Overridden by the 'prompt' input if connected">
        <TextArea value={data.prompt} onChange={set("prompt")} rows={3} placeholder="Ask something…" />
      </Field>
    </BaseNode>
  );
};
