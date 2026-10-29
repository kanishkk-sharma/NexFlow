/** Pure node metadata (no React) so the store, toolbar and canvas share one source of truth. */
export const NODE_DEFINITIONS = {
  customInput: {
    label: "Input", group: "Core",
    description: "A starting value: text, number or JSON.",
    defaults: { inputName: "input", inputType: "Text", inputValue: "" },
  },
  text: {
    label: "Text", group: "Core",
    description: "A template. {{name}} creates an input handle.",
    defaults: { text: "{{input}}" },
  },
  llm: {
    label: "LLM", group: "AI",
    description: "Ask a language model (OpenAI-compatible).",
    defaults: { model: "gpt-4o-mini", temperature: 0.7, systemPrompt: "", prompt: "" },
  },
  transform: {
    label: "Transform", group: "Core",
    description: "Change case, parse/stringify JSON, pick a field.",
    defaults: { operation: "uppercase", path: "" },
  },
  customOutput: {
    label: "Output", group: "Core",
    description: "Collects a final result by name.",
    defaults: { outputName: "output" },
  },
  api: {
    label: "API", group: "Integrations",
    description: "Make an HTTP request.",
    defaults: { method: "GET", url: "https://jsonplaceholder.typicode.com/todos/1", headers: "{}", body: "" },
  },
  database: {
    label: "Database", group: "Integrations",
    description: "Run SQL on a sandboxed demo database.",
    defaults: { query: "SELECT * FROM users LIMIT 5" },
  },
  condition: {
    label: "Condition", group: "Logic",
    description: "Branch the flow on a true/false test.",
    defaults: { operator: "equals", compareValue: "" },
  },
  delay: {
    label: "Delay", group: "Logic",
    description: "Wait, then pass the value through.",
    defaults: { delay: 1000 },
  },
  code: {
    label: "Code", group: "Logic",
    description: "Evaluate a safe expression on the input.",
    defaults: { code: "input" },
  },
  email: {
    label: "Email", group: "Integrations",
    description: "Send an email through the server's SMTP.",
    defaults: { to: "", subject: "", body: "" },
  },
  webhook: {
    label: "Webhook", group: "Integrations",
    description: "POST JSON to a URL.",
    defaults: { url: "", headers: "{}", payload: "" },
  },
  file: {
    label: "File", group: "Integrations",
    description: "Read or write a file in your workspace.",
    defaults: { action: "read", path: "", content: "" },
  },
  loop: {
    label: "Loop", group: "Logic",
    description: "Apply a template or expression to every list item.",
    defaults: { mode: "template", template: "{{item}}", expression: "item" },
  },
};

export const NODE_TYPE_LIST = Object.entries(NODE_DEFINITIONS).map(([type, def]) => ({ type, ...def }));

export const createNodeData = (type) => ({ ...(NODE_DEFINITIONS[type]?.defaults ?? {}) });
