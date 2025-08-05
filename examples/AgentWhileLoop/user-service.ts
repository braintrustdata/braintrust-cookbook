import { mockUsers, User, formatDate } from "./user-data.js";

export interface SearchUsersParams {
  query?: string;
  subscriptionPlan?: "basic" | "premium";
  subscriptionStatus?: "active" | "expired";
}

export interface NotifyUserParams {
  email: string;
  message: string;
}

export interface UpdateSubscriptionParams {
  email: string;
  plan?: "basic" | "premium";
  action?: "renew" | "cancel";
}

export class UserService {
  static async searchUsers(
    params: SearchUsersParams,
  ): Promise<{ users: User[]; formatted: string }> {
    let filtered = [...mockUsers];

    if (params.query) {
      filtered = filtered.filter(
        (u) =>
          u.name.toLowerCase().includes(params.query!.toLowerCase()) ||
          u.email.toLowerCase().includes(params.query!.toLowerCase()),
      );
    }

    if (params.subscriptionPlan) {
      filtered = filtered.filter(
        (u) => u.subscription.plan === params.subscriptionPlan,
      );
    }

    if (params.subscriptionStatus) {
      filtered = filtered.filter(
        (u) => u.subscription.status === params.subscriptionStatus,
      );
    }

    if (filtered.length === 0) {
      return {
        users: [],
        formatted: "No users found matching the criteria.",
      };
    }

    const formatted = filtered
      .map(
        (u, i) =>
          `${i + 1}. ${u.name} (${u.email})
   - ${
     u.subscription.plan.charAt(0).toUpperCase() + u.subscription.plan.slice(1)
   } subscriber (${
     u.subscription.status === "active"
       ? `active until ${new Date(u.subscription.expires).toLocaleDateString()}`
       : "expired"
   })
   - Last seen: ${formatDate(u.lastLogin)}`,
      )
      .join("\n\n");

    return {
      users: filtered,
      formatted: `Found ${filtered.length} user${
        filtered.length === 1 ? "" : "s"
      }:\n\n${formatted}`,
    };
  }

  static async getUserDetails(
    email: string,
  ): Promise<{ user: User | null; formatted: string }> {
    const user = mockUsers.find((u) => u.email === email);

    if (!user) {
      return {
        user: null,
        formatted: `No user found with email: ${email}`,
      };
    }

    const formatted = `User Details for ${user.name}:

Email: ${user.email}
User ID: ${user.id}

Subscription:
- Plan: ${user.subscription.plan}
- Status: ${user.subscription.status}
- ${user.subscription.status === "active" ? "Expires" : "Expired"}: ${new Date(
      user.subscription.expires,
    ).toLocaleDateString()}

Activity:
- Last login: ${new Date(user.lastLogin).toLocaleString()}
- Account created: ${new Date(2024, 0, user.id * 15).toLocaleDateString()}`;

    return { user, formatted };
  }

  static async notifyUser(
    params: NotifyUserParams,
  ): Promise<{ success: boolean; message: string }> {
    const user = mockUsers.find((u) => u.email === params.email);

    if (!user) {
      return {
        success: false,
        message: `❌ Failed to send notification: Customer with email ${params.email} not found`,
      };
    }

    // Simulate sending email
    await new Promise((resolve) => setTimeout(resolve, 500));

    return {
      success: true,
      message: `✓ Sent update to ${params.email}: "${params.message}"`,
    };
  }

  static async updateSubscription(
    params: UpdateSubscriptionParams,
  ): Promise<{ success: boolean; message: string }> {
    const user = mockUsers.find((u) => u.email === params.email);

    if (!user) {
      return {
        success: false,
        message: `❌ Failed to update subscription: Customer with email ${params.email} not found`,
      };
    }

    const updates: string[] = [];

    if (params.plan && params.plan !== user.subscription.plan) {
      user.subscription.plan = params.plan;
      updates.push(`plan changed to ${params.plan}`);
    }

    if (params.action === "renew") {
      user.subscription.status = "active";
      const newExpiry = new Date();
      newExpiry.setFullYear(newExpiry.getFullYear() + 1);
      user.subscription.expires = newExpiry.toISOString();
      updates.push("subscription renewed for 1 year");
    } else if (params.action === "cancel") {
      user.subscription.status = "expired";
      updates.push("subscription cancelled");
    }

    if (updates.length === 0) {
      return {
        success: true,
        message: `No changes made to ${user.name}'s subscription.`,
      };
    }

    return {
      success: true,
      message: `✓ Updated ${user.name}'s subscription: ${updates.join(", ")}`,
    };
  }
}
