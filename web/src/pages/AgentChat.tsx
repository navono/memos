import {
  BotIcon,
  MessageSquareIcon,
  PanelLeftCloseIcon,
  PanelLeftOpenIcon,
  PlusIcon,
  SendIcon,
  TrashIcon,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import "./AgentChat.css";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useAgentChat } from "@/hooks/useAgentChat";
import useMediaQuery from "@/hooks/useMediaQuery";
import { cn } from "@/lib/utils";
import { useTranslate } from "@/utils/i18n";

const SIDEBAR_MIN = 200;
const SIDEBAR_MAX = 400;
const SIDEBAR_DEFAULT = 256;
const SIDEBAR_STORAGE_KEY = "agent-sidebar-width";

const AgentChat = () => {
  const t = useTranslate();
  const md = useMediaQuery("md");
  const {
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
  } = useAgentChat();

  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem(SIDEBAR_STORAGE_KEY);
    return saved
      ? Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, Number(saved)))
      : SIDEBAR_DEFAULT;
  });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(!md);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  useEffect(() => {
    if (currentAgentId) {
      loadConversationList(currentAgentId);
    }
  }, [currentAgentId, loadConversationList]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = () => {
    const text = input.trim();
    if (!text || isLoading) return;
    setInput("");
    sendMessage(text);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleDeleteConversation = (id: string) => {
    if (window.confirm(t("agent.confirm-delete"))) {
      removeConversation(id);
    }
  };

  const formatDate = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const handleDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const startX = e.clientX;
      const startWidth = sidebarWidth;
      const onMove = (ev: MouseEvent) => {
        const delta = ev.clientX - startX;
        const next = Math.min(
          SIDEBAR_MAX,
          Math.max(SIDEBAR_MIN, startWidth + delta),
        );
        setSidebarWidth(next);
      };
      const onUp = () => {
        window.removeEventListener("mousemove", onMove);
        window.removeEventListener("mouseup", onUp);
        // Save the current width to localStorage via state updater to avoid stale closure
        setSidebarWidth((w) => {
          localStorage.setItem(SIDEBAR_STORAGE_KEY, String(w));
          return w;
        });
      };
      window.addEventListener("mousemove", onMove);
      window.addEventListener("mouseup", onUp);
    },
    [sidebarWidth],
  );

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => !prev);
  }, []);

  if (!agentAvailable) {
    return (
      <div className="flex flex-col items-center justify-center h-full min-h-[60vh] text-muted-foreground">
        <BotIcon className="w-12 h-12 mb-4 opacity-40" />
        <p className="text-lg">{t("agent.not-available")}</p>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] w-full">
      {/* Sidebar: conversation list */}
      {!sidebarCollapsed && (
        <>
          {/* Mobile: overlay drawer */}
          {!md && (
            <div
              className="fixed inset-0 z-40 bg-black/40"
              onClick={toggleSidebar}
            />
          )}
          <div
            className={cn(
              "shrink-0 border-r border-border flex flex-col agent-sidebar",
              !md && "fixed left-0 top-0 z-50 h-full w-[280px]",
            )}
            style={md ? { width: sidebarWidth } : undefined}
          >
            <div className="p-3 border-b border-border">
              <Select value={currentAgentId} onValueChange={switchAgent}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={t("agent.select-agent")} />
                </SelectTrigger>
                <SelectContent>
                  {agents.map((agent) => (
                    <SelectItem key={agent.id} value={agent.id}>
                      {agent.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-center justify-between px-3 py-2">
              <span className="text-xs font-medium text-muted-foreground">
                {t("agent.chat-history")}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={resetConversation}
                title={t("agent.new-chat")}
              >
                <PlusIcon className="w-3.5 h-3.5" />
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto px-2 space-y-1">
              {!conversationId && (
                <div className="flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm cursor-default">
                  <MessageSquareIcon className="w-4 h-4 shrink-0" />
                  <span className="truncate">{t("agent.new-chat")}</span>
                </div>
              )}
              {conversations.map((conv) => (
                <div
                  key={conv.id}
                  className={cn(
                    "group flex items-center gap-2 rounded-lg px-3 py-2 text-sm cursor-pointer hover:bg-accent transition-colors",
                    conversationId === conv.id && "bg-accent",
                  )}
                  onClick={() => selectConversation(conv.id)}
                >
                  <MessageSquareIcon className="w-4 h-4 shrink-0 text-muted-foreground" />
                  <span className="flex-1 truncate text-muted-foreground">
                    {formatDate(conv.updated_at)}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-5 w-5 shrink-0 opacity-0 group-hover:opacity-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteConversation(conv.id);
                    }}
                    title={t("agent.delete-chat")}
                  >
                    <TrashIcon className="w-3 h-3" />
                  </Button>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Drag handle (desktop only) */}
      {!sidebarCollapsed && md && (
        <div
          className="shrink-0 w-1 cursor-col-resize hover:bg-primary/20 active:bg-primary/30 transition-colors"
          onMouseDown={handleDragStart}
        />
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 shrink-0"
            onClick={toggleSidebar}
          >
            {sidebarCollapsed ? (
              <PanelLeftOpenIcon className="w-4 h-4" />
            ) : (
              <PanelLeftCloseIcon className="w-4 h-4" />
            )}
          </Button>
          {currentAgentId && (
            <span className="text-xs text-muted-foreground">
              {agents.find((a) => a.id === currentAgentId)?.description}
            </span>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              {t("agent.empty-message")}
            </div>
          )}
          {messages.map((msg, idx) => (
            <div
              key={idx}
              className={cn(
                "flex",
                msg.role === "user" ? "justify-end" : "justify-start",
              )}
            >
              <div
                className={cn(
                  "max-w-[80%] rounded-xl px-4 py-2.5 text-sm leading-relaxed",
                  msg.role === "user"
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-foreground agent-markdown",
                )}
              >
                {msg.role === "assistant" ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
                    {msg.content || (isLoading ? "..." : "")}
                  </ReactMarkdown>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="flex items-center gap-2 px-4 py-3 border-t border-border">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("agent.placeholder")}
            disabled={isLoading || !currentAgentId}
            className="flex-1"
          />
          <Button
            onClick={handleSend}
            disabled={isLoading || !input.trim() || !currentAgentId}
            size="icon"
          >
            <SendIcon className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default AgentChat;
