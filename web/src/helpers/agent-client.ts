import { getRequestToken } from "@/connect";

const AGENT_BASE = "/api/v1/agent";

export interface AgentInfo {
  id: string;
  name: string;
  description: string;
  icon: string;
}

export interface ChatEvent {
  content?: string;
  done?: boolean;
  conversation_id?: string;
  agent_id?: string;
  error?: string;
}

export interface Conversation {
  id: string;
  user_id: number;
  agent_id: string;
  created_at: number;
  updated_at: number;
}

export interface ConversationDetail {
  conversation: Conversation;
  messages: { role: string; content: string }[];
}

async function getAuthHeaders(): Promise<HeadersInit> {
  const token = await getRequestToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["X-Auth-Token"] = token;
  }
  return headers;
}

export async function listAgents(): Promise<AgentInfo[]> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${AGENT_BASE}/agents`, { headers });
  if (!resp.ok) {
    if (resp.status === 404) return [];
    throw new Error(`Failed to list agents: ${resp.status}`);
  }
  return resp.json();
}

export async function getAgent(id: string): Promise<AgentInfo> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${AGENT_BASE}/agents/${id}`, { headers });
  if (!resp.ok) {
    throw new Error(`Failed to get agent: ${resp.status}`);
  }
  return resp.json();
}

export async function* chatStream(
  message: string,
  agentId?: string,
  conversationId?: string,
): AsyncGenerator<ChatEvent> {
  const headers = await getAuthHeaders();
  const body: Record<string, string> = { message };
  if (agentId) body.agent_id = agentId;
  if (conversationId) body.conversation_id = conversationId;

  const resp = await fetch(`${AGENT_BASE}/chat`, {
    method: "POST",
    headers: { ...headers, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(`Chat request failed: ${resp.status} ${text}`);
  }

  const reader = resp.body?.getReader();
  if (!reader) {
    throw new Error("No response body");
  }

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const jsonStr = line.slice(6);
        try {
          const event: ChatEvent = JSON.parse(jsonStr);
          yield event;
          if (event.done) return;
        } catch {
          // Skip malformed lines
        }
      }
    }
  }
}

export async function listConversations(
  agentId?: string,
): Promise<Conversation[]> {
  const headers = await getAuthHeaders();
  const params = agentId ? `?agent_id=${agentId}` : "";
  const resp = await fetch(`${AGENT_BASE}/conversations${params}`, { headers });
  if (!resp.ok) return [];
  return resp.json();
}

export async function getConversation(id: string): Promise<ConversationDetail> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${AGENT_BASE}/conversations/${id}`, { headers });
  if (!resp.ok) {
    throw new Error(`Failed to get conversation: ${resp.status}`);
  }
  return resp.json();
}

export async function deleteConversation(id: string): Promise<void> {
  const headers = await getAuthHeaders();
  const resp = await fetch(`${AGENT_BASE}/conversations/${id}`, {
    method: "DELETE",
    headers,
  });
  if (!resp.ok) {
    throw new Error(`Failed to delete conversation: ${resp.status}`);
  }
}

export async function checkAgentAvailable(): Promise<boolean> {
  try {
    const agents = await listAgents();
    return agents.length > 0;
  } catch {
    return false;
  }
}
