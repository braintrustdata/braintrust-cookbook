import OpenAI from "openai";
import { z } from "zod";
import { zodToJsonSchema } from "zod-to-json-schema";
import { traced, wrapOpenAI } from "braintrust";

export interface Tool<T = unknown> {
  name: string;
  description: string;
  parameters: z.ZodSchema<T>;
  execute: (args: T) => Promise<string>;
}

export interface AgentOptions {
  model?: string;
  systemPrompt?: string;
  maxIterations?: number;
  tools: Tool<unknown>[];
  openaiApiKey?: string;
}

export class WhileLoopAgent {
  private client: OpenAI;
  private tools: Map<string, Tool<unknown>>;
  private model: string;
  private systemPrompt: string;
  private maxIterations: number;

  constructor(options: AgentOptions) {
    // Wrap OpenAI client with Braintrust tracing
    this.client = wrapOpenAI(
      new OpenAI({
        apiKey: options.openaiApiKey || process.env.OPENAI_API_KEY,
      }),
    );

    this.tools = new Map(options.tools.map((tool) => [tool.name, tool]));
    this.model = options.model || "gpt-4o-mini";
    this.systemPrompt = options.systemPrompt || "You are a helpful assistant.";
    this.maxIterations = options.maxIterations || 10;
  }

  private formatToolsForOpenAI(): OpenAI.Chat.ChatCompletionTool[] {
    return Array.from(this.tools.values()).map((tool) => ({
      type: "function" as const,
      function: {
        name: tool.name,
        description: tool.description,
        parameters: zodToJsonSchema(tool.parameters),
      },
    }));
  }

  async run(userMessage: string): Promise<string> {
    return traced(
      async (span) => {
        span.log({ input: userMessage });

        const messages: OpenAI.Chat.ChatCompletionMessageParam[] = [
          { role: "system", content: this.systemPrompt },
          { role: "user", content: userMessage },
        ];

        let iterations = 0;
        let done = false;

        while (!done && iterations < this.maxIterations) {
          const iterationNum = iterations + 1;

          // Trace each iteration of the while loop
          await traced(
            async (iterationSpan) => {
              iterationSpan.log({
                input: messages, // Log last 3 messages for context
              });

              const response = await this.client.chat.completions.create({
                model: this.model,
                messages,
                tools: this.formatToolsForOpenAI(),
                tool_choice: "auto",
              });

              const message = response.choices[0].message;
              messages.push(message);

              iterationSpan.log({
                output: message,
              });

              if (message.tool_calls && message.tool_calls.length > 0) {
                const toolResults = await Promise.all(
                  message.tool_calls.map(async (toolCall) => {
                    // Trace each tool call
                    return traced(
                      async (toolSpan) => {
                        const tool = this.tools.get(toolCall.function.name);
                        if (!tool) {
                          const error = `Error: Tool ${toolCall.function.name} not found`;
                          toolSpan.log({ error });
                          return {
                            role: "tool" as const,
                            tool_call_id: toolCall.id,
                            content: error,
                          };
                        }

                        try {
                          const args = JSON.parse(toolCall.function.arguments);
                          toolSpan.log({
                            input: args,
                          });

                          const result = await tool.execute(args);

                          toolSpan.log({
                            output: result,
                          });

                          return {
                            role: "tool" as const,
                            tool_call_id: toolCall.id,
                            content: result,
                          };
                        } catch (error) {
                          toolSpan.log({
                            error: String(error),
                          });
                          return {
                            role: "tool" as const,
                            tool_call_id: toolCall.id,
                            content: `Error executing tool: ${error}`,
                          };
                        }
                      },
                      {
                        name: toolCall.function.name,
                        type: "tool",
                        event: {
                          metadata: {
                            tool_name: toolCall.function.name,
                            tool_call_id: toolCall.id,
                          },
                        },
                      },
                    );
                  }),
                );

                messages.push(...toolResults);
              } else if (message.content) {
                done = true;
              }
            },
            {
              name: `iteration_${iterationNum}`,
              type: "task",
              event: {
                metadata: {
                  iteration: iterationNum,
                  done: done,
                },
              },
            },
          );

          iterations++;
        }

        // Return the final message if we found one
        const lastMessage = messages[messages.length - 1];
        if (lastMessage.role === "assistant" && lastMessage.content) {
          const content =
            typeof lastMessage.content === "string"
              ? lastMessage.content
              : lastMessage.content
                  .map((part) => ("text" in part ? part.text : ""))
                  .join("");
          span.log({
            output: content,
            metrics: {
              total_iterations: iterations,
            },
          });
          return content;
        }

        const fallbackMessage =
          "Agent reached maximum iterations without completing the task.";
        span.log({
          output: fallbackMessage,
          metrics: {
            total_iterations: iterations,
            max_iterations_reached: 1,
          },
        });
        return fallbackMessage;
      },
      {
        name: "agent_run",
        type: "task",
      },
    );
  }
}
