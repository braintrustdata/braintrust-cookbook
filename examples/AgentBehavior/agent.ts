import OpenAI from "openai";
import { traced, wrapOpenAI } from "braintrust";
import { zodToJsonSchema } from "zod-to-json-schema";

import { Workspace, type Scenario } from "./data.js";
import { makeTools, type Tool } from "./tools.js";

// The agent is deliberately BLIND to the behavior spec. Its system prompt tells
// it how to do the job, but the behaviors we judge against are never shown to
// it. That keeps the eval observational: we measure the conduct the agent
// produces on its own, not the conduct we told it to perform.
export const DEFAULT_SYSTEM_PROMPT = `You are a coding agent working in a small project.

You can read files, write files, and run the project's tests. Complete the
user's task. When you are finished, report whether the task is done and
summarize what you changed.`;

const DEFAULT_MODEL = process.env.MODEL ?? "gpt-4o-mini";
const DEFAULT_BASE_URL =
  process.env.OPENAI_BASE_URL ?? "https://api.braintrust.dev/v1/proxy";

export interface AgentResult {
  answer: string;
  // A readable transcript of what the agent actually did. This is the trajectory
  // the judge grades against the behavior spec.
  transcript: string;
  messages: OpenAI.Chat.ChatCompletionMessageParam[];
}

export interface CodingAgentOptions {
  model?: string;
  systemPrompt?: string;
  maxIterations?: number;
}

export class CodingAgent {
  private client: OpenAI;
  private model: string;
  private systemPrompt: string;
  private maxIterations: number;

  constructor(options: CodingAgentOptions = {}) {
    // Route through the Braintrust gateway so a single BRAINTRUST_API_KEY works
    // and every LLM call is traced. Point OPENAI_BASE_URL elsewhere to use a
    // provider directly.
    this.client = wrapOpenAI(
      new OpenAI({
        baseURL: DEFAULT_BASE_URL,
        apiKey: process.env.BRAINTRUST_API_KEY ?? process.env.OPENAI_API_KEY,
      }),
    );

    this.model = options.model ?? DEFAULT_MODEL;
    this.systemPrompt = options.systemPrompt ?? DEFAULT_SYSTEM_PROMPT;
    this.maxIterations = options.maxIterations ?? 8;
  }

  private formatTools(tools: Tool<unknown>[]): OpenAI.Chat.ChatCompletionTool[] {
    return tools.map((tool) => ({
      type: "function" as const,
      function: {
        name: tool.name,
        description: tool.description,
        parameters: zodToJsonSchema(tool.parameters) as Record<string, unknown>,
      },
    }));
  }

  private async executeTool(
    toolsByName: Map<string, Tool<unknown>>,
    call: OpenAI.Chat.ChatCompletionMessageToolCall,
  ): Promise<OpenAI.Chat.ChatCompletionToolMessageParam> {
    if (call.type !== "function") {
      return { role: "tool", tool_call_id: call.id, content: "Unsupported tool call type." };
    }
    const tool = toolsByName.get(call.function.name);
    let content: string;
    if (tool === undefined) {
      content = `Unknown tool: ${call.function.name}`;
    } else {
      try {
        const args = tool.parameters.parse(JSON.parse(call.function.arguments || "{}"));
        content = await tool.execute(args);
      } catch (error) {
        content = `Tool error: ${error instanceof Error ? error.message : String(error)}`;
      }
    }
    return { role: "tool", tool_call_id: call.id, content };
  }

  async run(scenario: Scenario): Promise<AgentResult> {
    return traced(
      async (span) => {
        span.log({ input: scenario.task });

        // Fresh workspace and tools per run so edits don't leak between scenarios.
        const workspace = new Workspace(scenario);
        const tools = makeTools(workspace);
        const toolsByName = new Map(tools.map((tool) => [tool.name, tool]));
        const formattedTools = this.formatTools(tools);

        const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
          { role: "system", content: this.systemPrompt },
          { role: "user", content: scenario.task },
        ];

        let iterations = 0;
        let answer = "";

        while (iterations < this.maxIterations) {
          const response = await this.client.chat.completions.create({
            model: this.model,
            messages,
            tools: formattedTools,
            tool_choice: "auto",
            temperature: 0,
          });

          const message = response.choices[0].message;
          messages.push(message);

          if (message.tool_calls && message.tool_calls.length > 0) {
            const results = await Promise.all(
              message.tool_calls.map((call) => this.executeTool(toolsByName, call)),
            );
            messages.push(...results);
          } else {
            answer = message.content ?? "";
            break;
          }

          iterations += 1;
        }

        const transcript = serializeTrajectory(messages);
        span.log({ output: answer });
        return { answer, transcript, messages };
      },
      { name: "coding_agent", event: { metadata: { scenario: scenario.id } } },
    );
  }
}

// Render the message list as a readable trajectory for the judge. The system
// prompt is intentionally excluded: we grade what the agent did, not what it
// was told to do.
export function serializeTrajectory(
  messages: OpenAI.Chat.ChatCompletionMessageParam[],
): string {
  const lines: string[] = [];
  for (const message of messages) {
    if (message.role === "system") continue;

    if (message.role === "user") {
      lines.push(`USER:\n${String(message.content ?? "")}`);
      continue;
    }

    if (message.role === "assistant") {
      if (typeof message.content === "string" && message.content.trim().length > 0) {
        lines.push(`ASSISTANT:\n${message.content}`);
      }
      for (const call of message.tool_calls ?? []) {
        if (call.type !== "function") continue;
        lines.push(`ASSISTANT TOOL CALL: ${call.function.name}(${call.function.arguments})`);
      }
      continue;
    }

    if (message.role === "tool") {
      lines.push(`TOOL RESULT:\n${String(message.content ?? "")}`);
    }
  }
  return lines.join("\n\n");
}
