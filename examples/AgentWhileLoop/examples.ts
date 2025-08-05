/**
 * This file demonstrates the key concepts from the blog post,
 * showing good vs bad tool design patterns.
 */

import { z } from "zod";
import { Tool } from "./agent.js";

// Example 1: Bad vs Good Tool Design
// ===================================

console.log("🔄 While-Loop Agent Pattern Examples");
console.log("====================================\n");

// Bad: Generic email API wrapper that exposes everything
const BadEmailSchema = z.object({
  to: z.string().describe("Recipient email address"),
  from: z.string().describe("Sender email address"),
  subject: z.string().describe("Email subject line"),
  body: z.string().describe("Email body content"),
  cc: z.array(z.string()).optional().describe("CC recipients"),
  bcc: z.array(z.string()).optional().describe("BCC recipients"),
  replyTo: z.string().optional().describe("Reply-to address"),
  headers: z.record(z.string()).optional().describe("Custom email headers"),
  attachments: z.array(z.any()).optional().describe("File attachments"),
  priority: z.enum(["high", "normal", "low"]).optional(),
  encoding: z.string().optional().describe("Text encoding"),
  htmlBody: z.string().optional().describe("HTML version of body"),
  trackOpens: z.boolean().optional().describe("Track email opens"),
  trackClicks: z.boolean().optional().describe("Track link clicks"),
  sendAt: z.string().optional().describe("Scheduled send time"),
});

const _badEmailTool: Tool<z.infer<typeof BadEmailSchema>> = {
  name: "send_email",
  description: "Send an email using the email API",
  parameters: BadEmailSchema,
  execute: async (args) => {
    // Complex implementation handling all parameters
    return `Email sent with ${Object.keys(args).length} parameters configured`;
  },
};

// Good: Purpose-built tool for the agent's actual job
const GoodNotifySchema = z.object({
  customerEmail: z.string().describe("Customer's email address"),
  message: z.string().describe("The update message to send to the customer"),
});

const _goodNotifyCustomerTool: Tool<z.infer<typeof GoodNotifySchema>> = {
  name: "notify_customer",
  description: "Send a notification email to a customer about their order",
  parameters: GoodNotifySchema,
  execute: async ({ customerEmail, message }) => {
    // The tool handles all the complexity internally
    // Agent doesn't need to think about email infrastructure
    return `✓ Sent update to ${customerEmail}`;
  },
};

// Example 2: Bad vs Good Tool Output
// ==================================

// Bad tool output - raw JSON dump
async function badSearchUsers(): Promise<string> {
  return JSON.stringify({
    status: 200,
    data: {
      users: [
        {
          id: 1,
          name: "John Smith",
          email: "john@co.com",
          created_at: "2024-01-15T08:30:00Z",
          last_login: "2024-03-20T14:22:00Z",
          subscription: {
            plan: "premium",
            status: "active",
            expires: "2025-01-15T08:30:00Z",
          },
          preferences: {
            notifications: true,
            theme: "dark",
          },
        },
        {
          id: 2,
          name: "Jane Doe",
          email: "jane@co.com",
          created_at: "2024-02-20T10:15:00Z",
          last_login: "2024-03-19T09:45:00Z",
          subscription: {
            plan: "basic",
            status: "active",
            expires: "2024-08-20T10:15:00Z",
          },
          preferences: {
            notifications: false,
            theme: "light",
          },
        },
      ],
      pagination: {
        page: 1,
        per_page: 20,
        total: 2,
        total_pages: 1,
      },
    },
  });
}

// Good tool output - human-readable, structured
async function goodSearchUsers(): Promise<string> {
  return `Found 2 users:

1. John Smith (john@co.com)
   - Premium subscriber (active until Jan 15, 2025)
   - Last seen: yesterday at 2:22 PM

2. Jane Doe (jane@co.com)
   - Basic subscriber (expires Aug 20, 2024)
   - Last seen: 2 days ago

Need more details? Use 'get_user_details' with the user's email.`;
}

// Example 3: The Core While Loop Pattern
// ======================================

async function demonstrateWhileLoop() {
  console.log("The Canonical Agent Pattern:");
  console.log("===========================\n");

  console.log(`
while (!done) {
  const response = await callLLM();
  messages.push(response);

  if (response.toolCalls) {
    messages.push(
      ...(await Promise.all(
        response.toolCalls.map((tc) => tool(tc.args))
      )),
    );
  } else {
    messages.push(getUserMessage());
  }
}
  `);

  console.log("\nKey Benefits:");
  console.log("- Simple and understandable");
  console.log("- Easy to debug");
  console.log("- Flexible and composable");
  console.log("- Minimal overhead");
  console.log("- Production-ready");
}

// Run demonstrations
async function main() {
  console.log("1. Tool Output Comparison:");
  console.log("==========================");
  console.log("\nBad Output:");
  console.log(await badSearchUsers());
  console.log("\nGood Output:");
  console.log(await goodSearchUsers());

  console.log("\n\n2. Tool Design Comparison:");
  console.log("=========================");
  console.log("\nBad Tool (Generic API Wrapper):");
  console.log(`- ${Object.keys(BadEmailSchema.shape).length} parameters`);
  console.log("- Agent must understand email infrastructure");
  console.log("- High cognitive load");

  console.log("\nGood Tool (Purpose-Built):");
  console.log(`- ${Object.keys(GoodNotifySchema.shape).length} parameters`);
  console.log("- Focused on the actual task");
  console.log("- Low cognitive load");

  console.log("\n");
  await demonstrateWhileLoop();
}

main().catch(console.error);
