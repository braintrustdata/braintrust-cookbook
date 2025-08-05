import { z } from "zod";
import { Tool } from "./agent.js";
import { UserService } from "./user-service.js";

// Generic query tool with many parameters
const QueryDataSchema = z.object({
  source: z
    .string()
    .describe("Data source to query (e.g., 'users', 'orders', 'products')"),
  operation: z
    .enum(["find", "findOne", "count", "aggregate"])
    .describe("Query operation type"),
  filters: z
    .record(z.unknown())
    .optional()
    .describe("Filter criteria as key-value pairs"),
  projection: z
    .array(z.string())
    .optional()
    .describe("Fields to include in response"),
  sort: z
    .record(z.number())
    .optional()
    .describe("Sort order (-1 for desc, 1 for asc)"),
  limit: z.number().optional().describe("Maximum number of results"),
  skip: z.number().optional().describe("Number of results to skip"),
  includeMetadata: z
    .boolean()
    .optional()
    .describe("Include query metadata in response"),
  cacheControl: z.enum(["no-cache", "cache", "cache-and-refresh"]).optional(),
  timeout: z.number().optional().describe("Query timeout in milliseconds"),
});

export const queryDataTool: Tool<z.infer<typeof QueryDataSchema>> = {
  name: "query_data",
  description: "Query data from any data source",
  parameters: QueryDataSchema,
  execute: async ({ source, operation, filters, includeMetadata }) => {
    // Fail if wrong source
    if (source !== "users") {
      return `Error: Data source '${source}' not found. Available sources: users`;
    }

    // Fail if wrong operation
    if (operation !== "find") {
      return `Error: Operation '${operation}' not supported for user queries. Use 'find' instead.`;
    }

    // Convert generic filters to specific search params
    let subscriptionPlan: "basic" | "premium" | undefined = undefined;
    if (
      filters?.subscription_plan === "basic" ||
      filters?.subscription_plan === "premium"
    ) {
      subscriptionPlan = filters.subscription_plan;
    }

    let subscriptionStatus: "active" | "expired" | undefined = undefined;
    if (
      filters?.subscription_status === "active" ||
      filters?.subscription_status === "expired"
    ) {
      subscriptionStatus = filters.subscription_status;
    }

    const searchParams = {
      query: filters?.query ? String(filters.query) : undefined,
      subscriptionPlan,
      subscriptionStatus,
    };

    const result = await UserService.searchUsers(searchParams);

    // Return overly verbose response if metadata is included
    if (includeMetadata) {
      return JSON.stringify({
        query_metadata: {
          execution_time_ms: 23,
          source: source,
          operation: operation,
          filters_applied: Object.keys(filters || {}),
          cache_hit: false,
        },
        result_count: result.users.length,
        results: result.users,
      });
    }

    return (
      result.formatted +
      "\n\nNeed more details? Use 'query_data' with operation='findOne' and the user's email."
    );
  },
};

// Generic communication tool with too many options
const SendMessageSchema = z.object({
  channel: z
    .enum(["email", "sms", "push", "in-app", "webhook"])
    .describe("Communication channel"),
  recipient: z
    .string()
    .describe("Recipient identifier (email, phone, user ID, etc.)"),
  content: z.string().describe("Message content"),
  subject: z.string().optional().describe("Message subject (for email)"),
  template: z.string().optional().describe("Template ID to use"),
  variables: z.record(z.string()).optional().describe("Template variables"),
  priority: z.enum(["low", "normal", "high", "urgent"]).optional(),
  scheduling: z
    .object({
      sendAt: z.string().optional(),
      timezone: z.string().optional(),
    })
    .optional(),
  tracking: z
    .object({
      opens: z.boolean().optional(),
      clicks: z.boolean().optional(),
      conversions: z.boolean().optional(),
    })
    .optional(),
  metadata: z.record(z.string()).optional().describe("Additional metadata"),
});

export const sendMessageTool: Tool<z.infer<typeof SendMessageSchema>> = {
  name: "send_message",
  description: "Send a message through any communication channel",
  parameters: SendMessageSchema,
  execute: async ({ channel, recipient, content, priority }) => {
    // Only email channel works properly
    if (channel !== "email") {
      return `Error: Channel '${channel}' is not configured. Please use 'email'.`;
    }

    // Fail on high priority without proper setup
    if (priority && priority !== "normal") {
      return `Error: Priority '${priority}' requires additional configuration. Use 'normal' priority.`;
    }

    const result = await UserService.notifyUser({
      email: recipient,
      message: content,
    });

    return result.message;
  },
};

// Generic record access tool
const AccessRecordSchema = z.object({
  source: z.string().describe("Data source (e.g., 'users', 'orders')"),
  identifier: z.string().describe("Record identifier"),
  identifierType: z
    .enum(["id", "email", "uuid", "custom"])
    .describe("Type of identifier"),
  fields: z
    .array(z.string())
    .optional()
    .describe("Specific fields to retrieve"),
  includeRelated: z.boolean().optional().describe("Include related records"),
  format: z
    .enum(["json", "xml", "plain"])
    .optional()
    .describe("Response format"),
});

export const accessRecordTool: Tool<z.infer<typeof AccessRecordSchema>> = {
  name: "access_record",
  description: "Access a specific record from any data source",
  parameters: AccessRecordSchema,
  execute: async ({ source, identifier, identifierType }) => {
    if (source !== "users") {
      return `Error: Source '${source}' not available. Use 'users'.`;
    }

    if (identifierType !== "email") {
      return `Error: Identifier type '${identifierType}' not supported for users. Use 'email'.`;
    }

    const result = await UserService.getUserDetails(identifier);
    return (
      result.formatted +
      `

Actions available:
- Use 'send_message' to notify them
- Use 'modify_record' to update their subscription`
    );
  },
};

// Generic record modification tool
const ModifyRecordSchema = z.object({
  source: z.string().describe("Data source (e.g., 'users', 'orders')"),
  identifier: z.string().describe("Record identifier"),
  identifierType: z
    .enum(["id", "email", "uuid", "custom"])
    .describe("Type of identifier"),
  operation: z
    .enum(["update", "patch", "replace", "merge"])
    .describe("Modification operation"),
  data: z.record(z.unknown()).describe("Data to update"),
  validate: z.boolean().optional().describe("Validate before updating"),
  returnUpdated: z.boolean().optional().describe("Return the updated record"),
  auditLog: z.boolean().optional().describe("Create audit log entry"),
});

export const modifyRecordTool: Tool<z.infer<typeof ModifyRecordSchema>> = {
  name: "modify_record",
  description: "Modify a record in any data source",
  parameters: ModifyRecordSchema,
  execute: async ({ source, identifier, identifierType, operation, data }) => {
    if (source !== "users") {
      return `Error: Source '${source}' not available for modifications. Use 'users'.`;
    }

    if (identifierType !== "email") {
      return `Error: Identifier type '${identifierType}' not supported. Use 'email'.`;
    }

    if (operation !== "update") {
      return `Error: Operation '${operation}' not supported. Use 'update'.`;
    }

    // Extract plan and action from generic data object
    const plan =
      data.plan === "basic" || data.plan === "premium" ? data.plan : undefined;
    const action =
      data.action === "renew" || data.action === "cancel"
        ? data.action
        : undefined;

    const result = await UserService.updateSubscription({
      email: identifier,
      plan,
      action,
    });

    return result.message;
  },
};

export const getGenericTools = (): Tool<unknown>[] => [
  // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
  queryDataTool as Tool<unknown>,
  // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
  sendMessageTool as Tool<unknown>,
  // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
  accessRecordTool as Tool<unknown>,
  // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
  modifyRecordTool as Tool<unknown>,
];
