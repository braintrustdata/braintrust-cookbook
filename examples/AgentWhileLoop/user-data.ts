export interface User {
  id: number;
  name: string;
  email: string;
  subscription: {
    plan: "basic" | "premium";
    status: "active" | "expired";
    expires: string;
  };
  lastLogin: string;
}

export const mockUsers: User[] = [
  {
    id: 1,
    name: "John Smith",
    email: "john@co.com",
    subscription: {
      plan: "premium",
      status: "active",
      expires: "2025-01-15T08:30:00Z",
    },
    lastLogin: "2024-03-20T14:22:00Z",
  },
  {
    id: 2,
    name: "Jane Doe",
    email: "jane@co.com",
    subscription: {
      plan: "basic",
      status: "active",
      expires: "2024-08-20T10:15:00Z",
    },
    lastLogin: "2024-03-19T09:45:00Z",
  },
  {
    id: 3,
    name: "Bob Wilson",
    email: "bob@co.com",
    subscription: {
      plan: "premium",
      status: "expired",
      expires: "2024-02-01T12:00:00Z",
    },
    lastLogin: "2024-01-30T16:00:00Z",
  },
];

export function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));

  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 7) return `${days} days ago`;
  return date.toLocaleDateString();
}
