import { APINode } from "./apiNode";
import { CodeNode } from "./codeNode";
import { ConditionNode } from "./conditionNode";
import { DatabaseNode } from "./databaseNode";
import { DelayNode } from "./delayNode";
import { EmailNode } from "./emailNode";
import { FileNode } from "./fileNode";
import { InputNode } from "./inputNode";
import { LLMNode } from "./llmNode";
import { LoopNode } from "./loopNode";
import { OutputNode } from "./outputNode";
import { TextNode } from "./textNode";
import { TransformNode } from "./transformNode";
import { WebhookNode } from "./webhookNode";

/** Must be a stable module-level object (React Flow warns if it changes between renders). */
export const nodeTypes = {
  customInput: InputNode,
  text: TextNode,
  llm: LLMNode,
  transform: TransformNode,
  customOutput: OutputNode,
  api: APINode,
  database: DatabaseNode,
  condition: ConditionNode,
  delay: DelayNode,
  code: CodeNode,
  email: EmailNode,
  webhook: WebhookNode,
  file: FileNode,
  loop: LoopNode,
};
