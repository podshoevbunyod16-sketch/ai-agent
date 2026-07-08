/**
 * Shared TypeScript types for frontend.
 */

export interface User {
  id: number;
  firebase_uid: string;
  email: string | null;
  phone_number: string | null;
  display_name: string | null;
  photo_url: string | null;
  created_at: string;
  last_login: string;
}

export interface Conversation {
  id: number;
  user_id: number;
  title: string;
  pinned: boolean;
  model_provider: string;
  model_name: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: number;
  conversation_id: number;
  branch_id: number | null;
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  tool_calls?: any[];
  tool_call_id?: string;
  tool_name?: string;
  model_used?: string;
  tokens_used?: number;
  chain_of_thought?: string;
  created_at: string;
}

export interface Branch {
  id: number;
  conversation_id: number;
  parent_branch_id: number | null;
  branch_number: number;
  title: string | null;
  created_at: string;
}

export interface MCPServer {
  id: number;
  user_id: number;
  name: string;
  transport_type: "stdio" | "sse";
  command: string | null;
  url: string | null;
  env_vars: Record<string, string> | null;
  enabled: boolean;
  tools_cache: any[] | null;
  created_at: string;
  updated_at: string;
}

export interface ChatState {
  conversations: Conversation[];
  activeConversationId: number | null;
  activeBranchId: number | null;
  messages: Message[];
  isLoading: boolean;
  modelProvider: string;
  modelName: string;
}

export type Theme = "dark" | "light" | "system";

export interface ThemeState {
  theme: Theme;
  resolved: "dark" | "light";
}
