import { openai } from "@ai-sdk/openai";
import { streamText, ToolInvocation } from "ai";
import { getWeather, getFahrenheit } from "@/components/tools";
// Uncomment below to use Braintrust's tracing features
// import { initLogger, wrapAISDKModel, traced, currentSpan } from "braintrust";

// Initialize Braintrust as the logging backend. Uncomment below
// const logger = initLogger({
//  apiKey: process.env.BRAINTRUST_API_KEY,
//  projectName: process.env.BRAINTRUST_PROJECT_NAME,
// });

// Any time this model is called, the input and output will be logged to Braintrust. Uncomment below
const model = //wrapAISDKModel(
  openai("gpt-4o")
// Uncomment below
// );

interface Message {
  role: "user" | "assistant";
  content: string;
  toolInvocations?: ToolInvocation[];
}

export async function POST(request: Request) {
  // traced starts a trace span when the POST endpoint is used
  // Unlike wrapTraced, traced does not natively log inputs and outputs. Uncomment below
  // return traced(async (span) => {
      const { messages }: { messages: Message[] } = await request.json();

      const stream = await streamText({
        // Our wrapped OpenAI model
        model: model,
        system: `\
        - you are an AI assistant who gives the weather. If the user gives you a location, give them the current weather in that location in Fahrenheit.
      `,
        messages: messages,
        // Important: maxSteps prevents infinite tool call loops but will stop your LLM's logic prematurely if set too low
        maxSteps: 5,
        // Register the exported tools to the LLM from @/components/tools
        tools: {
          getWeather: getWeather,
          getFahrenheit: getFahrenheit,
        },
        // Enable experimental telemetry
        experimental_telemetry: {
          isEnabled: true,
        },
      // When streamText is finished, log the input and output of the stream for the "root" span. Uncomment below
      // onFinish: (result) => {
      //   currentSpan().log({
      //     input: messages,
      //     output: result.text,
      //   });
      // },
        });

      return stream.toDataStreamResponse();
    }
    // Show the this span as a function and name the span POST /api/chat. Uncomment below
    // ,{ type: "function", name: "POST /api/chat" });}
