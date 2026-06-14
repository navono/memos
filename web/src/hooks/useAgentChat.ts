import { useCallback, useRef, useState } from "react";
import {
  chatStream,
  deleteConversation,
  getConversation,
  listAgents,
  listConversations,
  type AgentInfo,
  type Conversation,
} from "@/helpers/agent-client";

interface Message {
  role: "user" | "assistant" | "system";
  content: string;
}

export function useAgentChat() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [currentAgentId, setCurrentAgentId] = useState<string>("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [agentAvailable, setAgentAvailable] = useState(true);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const streamingRef = useRef(false);

  const loadAgents = useCallback(async () => {
    try {
      const result = await listAgents();
      setAgents(result);
      setAgentAvailable(result.length > 0);
      if (result.length > 0 && !currentAgentId) {
        setCurrentAgentId(result[0].id);
      }
    } catch {
      setAgentAvailable(false);
      setAgents([]);
    }
  }, []);

  const loadConversationList = useCallback(async (agentId?: string) => {
    try {
      const result = await listConversations(agentId);
      setConversations(result);
      return result;
    } catch {
      setConversations([]);
      return [];
    }
  }, []);

  const selectConversation = useCallback(async (id: string) => {
    try {
      const detail = await getConversation(id);
      const msgs = detail.messages
        .filter((m) => m.role !== "system" && m.role !== "tool")
        .map((m) => ({
          role: (m.role === "human"
            ? "user"
            : m.role === "ai"
              ? "assistant"
              : m.role) as "user" | "assistant",
          content: m.content,
        }))
        .filter((m) => m.content);
      setConversationId(id);
      setMessages(msgs);
    } catch {
      // If loading fails, start fresh with the conversation ID
      setConversationId(id);
      setMessages([]);
    }
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      if (streamingRef.current || !currentAgentId) return;

      setMessages((prev) => [...prev, { role: "user", content }]);
      setIsLoading(true);
      streamingRef.current = true;

      // Add a placeholder assistant message for streaming.
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

      try {
        const stream = chatStream(
          content,
          currentAgentId,
          conversationId ?? undefined,
        );
        let newConvId: string | null = null;
        for await (const event of stream) {
          if (event.content) {
            setMessages((prev) => {
              const updated = [...prev];
              const lastAssistantIdx = updated.reduce(
                (lastIdx, msg, idx) =>
                  msg.role === "assistant" ? idx : lastIdx,
                -1,
              );
              if (lastAssistantIdx >= 0) {
                updated[lastAssistantIdx] = {
                  ...updated[lastAssistantIdx],
                  content: updated[lastAssistantIdx].content + event.content,
                };
              }
              return updated;
            });
          }
          if (event.done && event.conversation_id) {
            newConvId = event.conversation_id;
            setConversationId(event.conversation_id);
          }
          if (event.error) {
            setMessages((prev) => {
              const updated = [...prev];
              const lastAssistantIdx = updated.reduce(
                (lastIdx, msg, idx) =>
                  msg.role === "assistant" ? idx : lastIdx,
                -1,
              );
              if (lastAssistantIdx >= 0) {
                updated[lastAssistantIdx] = {
                  ...updated[lastAssistantIdx],
                  content: `Error: ${event.error}`,
                };
              }
              return updated;
            });
          }
        }
        // Refresh conversation list after a new message.
        if (newConvId || conversationId) {
          loadConversationList(currentAgentId);
        }
      } catch (err) {
        setMessages((prev) => {
          const updated = [...prev];
          const lastAssistantIdx = updated.reduce(
            (lastIdx, msg, idx) => (msg.role === "assistant" ? idx : lastIdx),
            -1,
          );
          if (lastAssistantIdx >= 0) {
            updated[lastAssistantIdx] = {
              ...updated[lastAssistantIdx],
              content: `Error: ${err instanceof Error ? err.message : "Unknown error"}`,
            };
          }
          return updated;
        });
      } finally {
        setIsLoading(false);
        streamingRef.current = false;
      }
    },
    [currentAgentId, conversationId, loadConversationList],
  );

  const switchAgent = useCallback(
    (agentId: string) => {
      setCurrentAgentId(agentId);
      setConversationId(null);
      setMessages([]);
      loadConversationList(agentId);
    },
    [loadConversationList],
  );

  const resetConversation = useCallback(() => {
    setConversationId(null);
    setMessages([]);
  }, []);

  const removeConversation = useCallback(
    async (id: string) => {
      await deleteConversation(id);
      if (id === conversationId) {
        setConversationId(null);
        setMessages([]);
      }
      loadConversationList(currentAgentId);
    },
    [conversationId, currentAgentId, loadConversationList],
  );

  return {
    agents,
    currentAgentId,
    conversationId,
    conversations,
    messages,
    isLoading,
    agentAvailable,
    loadAgents,
    loadConversationList,
    selectConversation,
    sendMessage,
    switchAgent,
    resetConversation,
    removeConversation,
  };
}
