import { z } from "zod";
import { Tool } from "./agent.js";
import { UserService } from "./user-service.js";

const NotifyCustomerSchema = z.object({
  customerEmail: z.string().describe("Customer's email address"),
  message: z.string().describe("The update message to send to the customer"),
});

export const notifyCustomerTool: Tool<z.infer<typeof NotifyCustomerSchema>> = {
  name: "notify_customer",
  description:
    "Send a notification email to a customer about their order or account",
  parameters: NotifyCustomerSchema,
  execute: async ({ customerEmail, message }) => {
    const result = await UserService.notifyUser({
      email: customerEmail,
      message,
    });
    return result.message;
  },
};

const SearchUsersSchema = z.object({
  query: z
    .string()
    .optional()
    .describe("Search query to match against user names or emails"),
  subscriptionPlan: z
    .enum(["basic", "premium"])
    .optional()
    .describe("Filter by subscription plan"),
  subscriptionStatus: z
    .enum(["active", "expired"])
    .optional()
    .describe("Filter by subscription status"),
});

export const searchUsersTool: Tool<z.infer<typeof SearchUsersSchema>> = {
  name: "search_users",
  description: "Search for users by various criteria",
  parameters: SearchUsersSchema,
  execute: async ({ query, subscriptionPlan, subscriptionStatus }) => {
    const result = await UserService.searchUsers({
      query,
      subscriptionPlan,
      subscriptionStatus,
    });
    return (
      result.formatted +
      "\n\nNeed more details? Use 'get_user_details' with the user's email."
    );
  },
};

const GetUserDetailsSchema = z.object({
  email: z.string().describe("User's email address"),
});

export const getUserDetailsTool: Tool<z.infer<typeof GetUserDetailsSchema>> = {
  name: "get_user_details",
  description: "Get detailed information about a specific user",
  parameters: GetUserDetailsSchema,
  execute: async ({ email }) => {
    const result = await UserService.getUserDetails(email);
    return (
      result.formatted +
      `

Actions available:
- Use 'notify_customer' to send them an email
- Use 'update_subscription' to modify their plan`
    );
  },
};

const UpdateSubscriptionSchema = z.object({
  email: z.string().describe("Customer's email address"),
  plan: z
    .enum(["basic", "premium"])
    .optional()
    .describe("New subscription plan"),
  action: z
    .enum(["renew", "cancel"])
    .optional()
    .describe("Action to take on subscription"),
});

export const updateSubscriptionTool: Tool<
  z.infer<typeof UpdateSubscriptionSchema>
> = {
  name: "update_subscription",
  description: "Update a customer's subscription plan or status",
  parameters: UpdateSubscriptionSchema,
  execute: async ({ email, plan, action }) => {
    const result = await UserService.updateSubscription({
      email,
      plan,
      action,
    });
    return result.message;
  },
};

export const getAllTools = (): Tool<unknown>[] => [
  // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
  notifyCustomerTool as Tool<unknown>,
  // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
  searchUsersTool as Tool<unknown>,
  // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
  getUserDetailsTool as Tool<unknown>,
  // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
  updateSubscriptionTool as Tool<unknown>,
];
