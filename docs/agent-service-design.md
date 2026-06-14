# Agent Service Design

Memos Agent 是一个独立的 Python 服务，采用多 agent 架构，通过 Router + 专职 Agent 模式提供 LLM 驱动的智能能力，包括对话、摘要、标签推荐、景点推荐等。

## Current State (2026-06)

### 已实现

| 层               | 现状                                                                                                                                                                                                                                                                                                   |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Go 后端**      | `AIService` 只有 `Transcribe`（语音转文字）一个 RPC。`internal/ai/` 封装了 STT/AudioLLM。`InstanceAISetting` 存储 provider 配置（OpenAI/Gemini），但没有 agent 概念                                                                                                                                    |
| **Python Agent** | `agent/` 用 FastAPI + LangChain `deepagents` 构建了**通用聊天 agent**，有 `search_memos`/`get_memo`/`create_memo`/`list_tags`/`list_resources`/`create_resource`/`update_resource`/`delete_resource` 共 8 个 tools，SSE 流式输出。**没有多 agent 概念**，所有请求走同一个 system prompt + 同一组 tools |
| **前端**         | 没有与 agent 服务交互的 UI。`AISection` 只管理 provider 和转录配置                                                                                                                                                                                                                                     |
| **MCP**          | Go 后端已有完整的 MCP server（`server/router/mcp/`），基于 OpenAPI spec 自动暴露 API 为 MCP tools，走 StreamableHTTP 协议。Python agent 未利用此能力                                                                                                                                                   |

### 核心差距

1. **Agent 是单体的** — 一个 `create_deep_agent` 处理所有请求，无法按功能分类
2. **缺少 Agent 注册/发现机制** — 没有方式定义、注册、列出可用的 agents
3. **前端无 Agent 交互入口** — 用户无法选择和调用特定 agent
4. **MCP 与 Agent 割裂** — Go 端的 MCP server 已可暴露 API，但 Python agent 没有利用 MCP client 来连接外部服务（搜索、地图等）

## Architecture Overview

```
User
 │
 ▼
Memos Frontend (React)
 │
 ▼
Memos API (Go / Echo)
 │
 ├── /api/v1/memo/*       → Memos 主功能（现有）
 ├── /api/v1/agent/*      → 代理转发 ↓
 │    │
 │    ▼
 │   Agent Service (Python / FastAPI)
 │    │
 │    ├── orchestrator
 │    │    └── router agent（意图识别 → 分发）
 │    │         ├→ summarizer agent（摘要专家）
 │    │         ├→ qa agent（问答专家）
 │    │         ├→ tagger agent（标签专家）
 │    │         └→ pipeline: summarizer → tagger
 │    │
 │    ├── tools ──────────→ Memos REST API（读/写数据）
 │    ├── mcp ────────────→ MCP Servers（网络搜索、文件系统等）
 │    ├── memory ↔ Agent DB（对话、配置、用量）
 │    ├── context builder
 │    ├── guardrails（隐私、限流、配额）
 │    └── LLM provider ───→ OpenAI / Anthropic / ...
 │
 └── agent 不可用时 → 降级，返回功能不可用提示
```

Agent 作为可选依赖。不配置 `MEMOS_AGENT_ADDR` 时，Memos 主功能正常运行。

核心设计：用户请求由 Router Agent 分析意图后分发到专职 Agent，支持单 agent 处理、串行 pipeline、并行协作三种编排模式。

## Project Structure

```
memos/
├── agent/                        # Agent 服务（Python），独立项目
│   ├── pyproject.toml
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI 入口
│   │   ├── config.py             # 配置加载（环境变量 + 数据库）
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── llm/              # LLM Provider 抽象
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py       # Provider 接口定义
│   │   │   │   ├── openai.py
│   │   │   │   └── anthropic.py
│   │   │   ├── runtime/          # 执行引擎
│   │   │   │   ├── __init__.py
│   │   │   │   ├── loop.py       # 单 agent 执行循环
│   │   │   │   └── orchestrator.py # 多 agent 编排器
│   │   │   ├── planner/          # 任务分解与推理
│   │   │   │   ├── __init__.py
│   │   │   │   └── planner.py
│   │   │   └── prompt/           # Prompt 模板管理
│   │   │       ├── __init__.py
│   │   │       └── templates/
│   │   │           └── agents/   # 每个 agent 独立 prompt
│   │   │               ├── router.md
│   │   │               ├── summarizer.md
│   │   │               ├── qa.md
│   │   │               └── tagger.md
│   │   ├── agents/               # Agent 定义目录
│   │   │   ├── __init__.py
│   │   │   ├── base.py           # Agent 基类
│   │   │   ├── registry.py       # Agent 注册表
│   │   │   ├── router.py         # 路由 agent（意图识别与分发）
│   │   │   ├── summarizer.py     # 摘要专家
│   │   │   ├── qa.py             # 问答专家
│   │   │   ├── tagger.py         # 标签专家
│   │   │   └── custom/           # 用户自定义 agent（预留）
│   │   ├── memory/
│   │   │   ├── __init__.py
│   │   │   ├── short_term.py     # 对话上下文（session 内）
│   │   │   ├── long_term.py      # 持久化记忆（跨 session）
│   │   │   └── working.py        # 当前任务的中间状态
│   │   ├── context/
│   │   │   ├── __init__.py
│   │   │   ├── builder.py        # 组装发给 LLM 的上下文
│   │   │   └── window.py         # 上下文窗口管理（截断、摘要）
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── registry.py       # 工具注册与发现（统一管理内置 + MCP 工具）
│   │   │   ├── memos.py          # 语义化工具封装（agent 内部使用）
│   │   │   └── memos_client.py   # 底层 HTTP client（对接 Memos REST API）
│   │   ├── mcp/                  # MCP Client 集成
│   │   │   ├── __init__.py
│   │   │   ├── client.py         # MCP client 管理（连接、生命周期）
│   │   │   ├── adapter.py        # MCP tool → 内部 Tool 接口适配
│   │   │   └── config.py         # MCP server 配置（地址、能力白名单）
│   │   ├── guardrails/
│   │   │   ├── __init__.py
│   │   │   ├── input.py          # 输入校验
│   │   │   ├── output.py         # 输出过滤（敏感信息脱敏）
│   │   │   └── privacy.py        # 数据隐私策略
│   │   ├── observability/
│   │   │   ├── __init__.py
│   │   │   ├── tracer.py         # 调用链追踪
│   │   │   └── logger.py         # 结构化日志
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py           # 对话接口
│   │   │   ├── tasks.py          # 异步任务接口
│   │   │   ├── agents.py         # Agent 管理接口（列表、启用/禁用）
│   │   │   └── config.py         # 配置管理接口
│   │   ├── schemas.py            # Pydantic 请求/响应模型
│   │   └── db/
│   │       ├── __init__.py
│   │       └── database.py       # Agent 自有数据库（SQLite）
│   └── tests/
│       ├── __init__.py
│       ├── test_agents.py        # Agent 单元测试
│       ├── test_orchestrator.py  # 编排器测试
│       ├── test_tools.py
│       ├── test_memory.py
│       └── test_routes.py
│
├── server/
│   └── service/
│       └── agent/                # Memos 侧适配层（Go）
│           ├── client.go         # HTTP client，调用 agent API
│           ├── types.go          # 请求/响应结构体
│           └── proxy.go          # 代理路由注册
│
├── api/v1/
│   └── agent.go                  # Memos API 路由：/api/v1/agent/*
│
├── proto/                        # Memos 自身 proto（现有，不变）
└── web/                          # 前端（现有）
```

## Communication

Agent 与 Memos 之间使用 REST API 通信（非 gRPC），原因：

- Agent 作为独立设计的服务，不应依赖 Memos 的 proto 定义
- REST 更通用，降低耦合，便于替换 agent 实现
- FastAPI 自带 OpenAPI 文档，API 契约自描述

### Memos → Agent（代理转发）

Memos 前端所有 agent 相关请求走 `/api/v1/agent/*`，由 Memos 转发到 agent 服务。

```
Memos Frontend → Memos API /api/v1/agent/* → Agent Service /v1/*
```

Memos 代理层职责：

- 鉴权：验证用户身份后，将 user_id 透传给 agent
- 服务间认证：使用内部签名（HMAC），不暴露给用户
- 降级：agent 不可用时返回友好提示，不影响主功能
- 流式透传：SSE 响应需要支持 streaming（注意 Memos 默认 30s 超时需要豁免 agent 路由）

### Agent → Memos（工具调用）

Agent 通过 Memos REST API（v1）操作数据，tools 层封装细节：

```
Agent tools/memos.py（语义化接口）
  → tools/memos_client.py（HTTP client）
    → Memos REST API
```

两层分离的目的：

- agent 核心逻辑只关心"搜索 memo"、"创建 memo"等语义操作
- API 版本迁移、认证方式变更只改 client 层
- 一个 tool 可能对应多次 API 调用

### Authentication Flow

```
1. 用户请求 → Memos API（JWT/cookie 鉴权）
2. Memos 验证通过 → 转发到 Agent（携带 user_id + 内部 HMAC 签名）
3. Agent 验证 HMAC → 信任 user_id → 执行操作
```

Agent 不直接面向用户，所有请求都经过 Memos 代理。

## Core Modules

### LLM Provider

抽象不同模型供应商，隔离切换成本：

```python
class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, messages: list[Message], **kwargs) -> Response: ...

    @abstractmethod
    async def stream(self, messages: list[Message], **kwargs) -> AsyncIterator[Chunk]: ...
```

- 支持多 provider（OpenAI、Anthropic、本地模型）
- 方便 fallback 和 A/B 测试
- 统一 token 计量接口

### Runtime

单 agent 执行循环，驱动核心推理过程：

```
用户输入 → context builder 组装上下文 → LLM 推理 → 判断是否需要 tool call
  → 调用 tool → 结果加入上下文 → 再次推理 → ... → 最终响应
```

多 agent 编排由 Orchestrator 负责，Runtime 负责单个 agent 的执行。

### Planner

复杂任务分解。例如"总结上周所有关于 AI 的 memo 并打标签"：

1. 搜索符合条件的 memo
2. 逐个或批量读取内容
3. 生成摘要
4. 自动打标签

简单场景可直接用 ReAct loop，无需显式 planner。

### Memory

三层记忆架构：

- **short_term**：当前对话上下文，session 内有效
- **long_term**：跨 session 持久化记忆，基于用户历史数据构建（如用户偏好、常用标签）
- **working**：当前任务的中间状态（如分步处理时的进度）

### Context Builder

负责组装发给 LLM 的完整上下文：

- 系统提示词
- 对话历史（从 memory 加载）
- 相关 memo 内容（通过 tools 检索）
- 上下文窗口管理（截断、摘要压缩，适配不同模型的 token 限制）

### Tools

Agent 可调用的能力，决定 agent 的能力边界：

| Tool             | 说明               | 对应 Memos API           |
| ---------------- | ------------------ | ------------------------ |
| search_memos     | 搜索 memo          | GET /api/v1/memo         |
| get_memo         | 获取单个 memo 详情 | GET /api/v1/memo/:id     |
| create_memo      | 创建 memo          | POST /api/v1/memo        |
| update_memo      | 更新 memo          | PATCH /api/v1/memo/:id   |
| list_tags        | 获取标签列表       | GET /api/v1/tag          |
| get_user_setting | 获取用户设置       | GET /api/v1/user/setting |

工具通过 `registry.py` 注册，支持动态启用/禁用。

### MCP (Model Context Protocol)

Agent 服务作为 MCP Client，连接外部 MCP Server 获取扩展能力。MCP 工具和内置工具在 agent 看来完全一致——都通过 `registry.py` 统一调用。

```
Agent 内部
  │
  ├── 内置 tools（memos.py：search、create、...）
  │
  └── MCP adapter（将远程 MCP tools 适配为本地 Tool 接口）
        │
        ├── MCP Server: Web Search（Tavily / Brave / ...）
        │     └── web_search(query)
        │
        ├── MCP Server: File System（可选）
        │     └── read_file / write_file
        │
        └── MCP Server: 自定义（可扩展）
              └── ...
```

**MCP Client 管理**：

```python
class MCPClientManager:
    """管理所有 MCP Server 连接"""

    async def connect(self, server_name: str, config: MCPServerConfig):
        """建立连接，发现可用 tools"""
        ...

    async def disconnect(self, server_name: str):
        """断开连接"""
        ...

    async def list_tools(self) -> list[Tool]:
        """汇总所有 MCP server 提供的工具"""
        ...

    async def call_tool(self, tool_name: str, args: dict) -> Any:
        """调用 MCP 工具"""
        ...
```

**Tool 适配**：

```python
class MCPToolAdapter:
    """将 MCP server 暴露的 tool 转换为内部 Tool 接口"""

    def adapt(self, mcp_tool) -> Tool:
        """MCP tool schema → 内部 Tool 定义（name、description、parameters）"""
        ...
```

适配后，MCP 工具自动出现在 `ToolRegistry` 中，agent 不感知工具来源是本地还是远程 MCP server。

**MCP 与多 agent 的关系**：

- 管理员可配置哪些 MCP server 的工具对哪些 agent 可见
- 例如：qa agent 可以使用 web_search，summarizer agent 不需要
- 配置在 `mcp/config.py` 中以白名单形式管理

**MCP 通信方式**：

MCP 支持两种传输：

- **stdio**：MCP server 作为子进程，通过 stdin/stdout 通信（适合本地部署）
- **SSE / Streamable HTTP**：通过 HTTP 通信（适合远程 MCP server）

Agent 服务两种都支持，通过配置选择。

### Prompt Management

Prompt 模板独立管理，不散落在代码中：

- 按场景分文件（system.md、summarize.md 等）
- 支持变量插值
- 便于版本管理和迭代

### Guardrails

- **input**：输入校验，防止 prompt 注入
- **output**：输出过滤，敏感信息脱敏
- **privacy**：控制哪些数据可以发送给 LLM provider
- **action**：限制 agent 可执行的操作范围（如不能删除他人的 memo）

### Observability

Agent 调用链长（用户请求 → planner → tool call → LLM → tool call → ...），需要结构化追踪：

- 每次 agent run 的完整调用链
- 每步的输入/输出/耗时
- LLM token 消耗

## Multi-Agent Architecture

### 设计原则

用户请求由 Router Agent 分析意图后分发到专职 Agent，各 Agent 拥有独立的 prompt、tools 子集和模型配置。

```
用户请求 → Router Agent（意图识别）
              ├→ summarizer agent（摘要专家）
              ├→ qa agent（问答专家）
              ├→ tagger agent（标签专家）
              └→ pipeline: summarizer → tagger（串行编排）
```

### Agent 基类

每个 Agent 是一个独立的配置单元：

```python
class AgentBase:
    name: str                        # agent 标识
    description: str                 # 能力描述（router 用于决策）
    tools: list[Tool]                # 该 agent 可用的工具子集
    model: str | None = None         # 可指定不同模型

    def build_system_prompt(self, user_context: dict) -> str:
        """构建系统提示词"""
        ...

    def build_context(self, request, memory) -> list[Message]:
        """构建上下文，不同 agent 可以有不同策略"""
        ...
```

### Agent 注册表

启动时注册所有 agent，运行时可通过配置启用/禁用：

```python
class AgentRegistry:
    _agents: dict[str, AgentBase] = {}

    def register(self, agent: AgentBase): ...
    def get(self, name: str) -> AgentBase: ...
    def list_agents(self) -> list[AgentBase]: ...
    def enable(self, name: str): ...
    def disable(self, name: str): ...
```

### Router Agent

分析用户意图，决定分发目标：

```python
class RouterAgent(AgentBase):
    name = "router"
    description = "分析用户意图，选择最合适的 agent 处理"

    tools = []  # router 不直接调工具

    def route(self, user_input: str, context: dict) -> RoutingDecision:
        """
        返回：
        - mode: single / pipeline / parallel
        - agent: 目标 agent 名称（single 模式）
        - pipeline: agent 名称列表（pipeline 模式）
        - agents: agent 名称列表（parallel 模式）
        """
        ...
```

Router 的 prompt 包含所有可用 agent 的 description，由 LLM 做分类决策。

### Orchestrator（编排器）

支持三种编排模式：

**Single** — 单 agent 处理

```
用户："这篇 memo 是什么意思？"
→ router → qa agent
```

**Pipeline** — 串行处理，前一个输出作为后一个输入

```
用户："总结我上周的 memo 并自动打标签"
→ router → summarizer → tagger
              ↓ output
              "上周主要讨论了..."
                          ↓ input + memo ids
                          tagger → 创建标签、关联 memo
```

**Parallel** — 并行处理，结果合并

```
用户："帮我从不同角度分析这篇 memo"
→ router → qa agent ──┐
         → tagger ────┤──→ 合并结果返回
         → summarizer─┘
```

实现：

```python
class Orchestrator:
    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.router = RouterAgent()

    async def run(self, request, user_context) -> Response:
        decision = self.router.route(request, user_context)

        if decision.mode == "single":
            return await self._run_single(decision.agent, request, user_context)
        elif decision.mode == "pipeline":
            return await self._run_pipeline(decision.pipeline, request, user_context)
        elif decision.mode == "parallel":
            return await self._run_parallel(decision.agents, request, user_context)

    async def _run_single(self, agent_name, request, ctx):
        agent = self.registry.get(agent_name)
        # 加载 agent 专属 prompt + tools → 执行 agent loop
        ...

    async def _run_pipeline(self, agent_names, request, ctx):
        result = request
        for name in agent_names:
            result = await self._run_single(name, result, ctx)
        return result

    async def _run_parallel(self, agent_names, request, ctx):
        tasks = [self._run_single(name, request, ctx) for name in agent_names]
        results = await asyncio.gather(*tasks)
        return self._merge_results(results)
```

### Agent 间上下文传递

Pipeline 模式下 agent 之间需要传递中间结果：

```python
@dataclass
class AgentOutput:
    content: str                     # 文本输出
    artifacts: dict                  # 结构化数据（如提取的标签、memo id 列表）
    token_usage: TokenUsage          # token 消耗

    def as_agent_input(self) -> str:
        """转换为下一个 agent 的输入"""
        ...
```

### Memory 隔离策略

```
memory
├── shared/          # 跨 agent 共享（用户偏好、常用标签）
├── agents/
│   ├── summarizer/  # 摘要 agent 的对话历史
│   ├── qa/          # 问答 agent 的对话历史
│   └── tagger/      # 标签 agent 的对话历史
```

- 同一用户与同一 agent 的对话共享 memory（连续对话）
- 不同 agent 之间通过 shared memory 共享基础信息
- Pipeline 模式下，前一个 agent 的输出作为 context 传递给下一个，不写入后者的 memory

### 与现有模块的关系

| 现有模块                | 多 agent 下的变化               |
| ----------------------- | ------------------------------- |
| tools/                  | 不变，每个 agent 选择性使用     |
| memory/                 | 增加按 agent 隔离的存储         |
| context/                | 不变，每个 agent 独立构建上下文 |
| llm/                    | 不变，不同 agent 可配置不同模型 |
| guardrails/             | 不变，全局生效                  |
| runtime/loop.py         | 不变，单个 agent 的执行循环     |
| runtime/orchestrator.py | **新增**，编排多个 agent        |
| agents/                 | **新增**，agent 定义和注册      |

## API Design

### Agent Service Endpoints

```
# 对话
POST   /v1/chat                    # 同步对话（支持 SSE 流式），可选指定 agent
POST   /v1/tasks                   # 异步任务（返回 task_id）
GET    /v1/tasks/{id}              # 查询异步任务状态和结果
GET    /v1/conversations           # 列出对话历史
GET    /v1/conversations/{id}      # 获取单个对话详情
DELETE /v1/conversations/{id}      # 删除对话

# Agent 管理
GET    /v1/agents                  # 列出可用 agent 及状态
PUT    /v1/agents/{name}/status    # 启用/禁用 agent（管理员）

# MCP 管理
GET    /v1/mcp/servers             # 列出已配置的 MCP server 及状态
POST   /v1/mcp/servers             # 添加 MCP server 配置
PUT    /v1/mcp/servers/{name}      # 更新 MCP server 配置
DELETE /v1/mcp/servers/{name}      # 移除 MCP server
GET    /v1/mcp/servers/{name}/tools # 列出某 MCP server 提供的工具

# 配置
GET    /v1/config/system           # 获取系统配置（管理员）
PUT    /v1/config/system           # 更新系统配置
GET    /v1/config/user/{user_id}   # 获取用户偏好
PUT    /v1/config/user/{user_id}   # 更新用户偏好

# 健康检查
GET    /v1/healthz
```

#### Chat 请求示例

```json
// 自动路由（默认，由 router agent 选择）
POST /v1/chat
{
    "message": "总结这篇 memo"
}

// 指定 agent
POST /v1/chat
{
    "message": "总结这篇 memo",
    "agent": "summarizer"
}
```

### Async vs Sync

- **同步 + 流式**（SSE）：对话、简单问答，实时返回
- **异步**：复杂任务（批量摘要、全量分析），返回 task_id，客户端轮询

起步先用同步 + 流式，后续按需加异步。

## Configuration

### 系统级（管理员）

| 配置项       | 环境变量                  | 说明                        |
| ------------ | ------------------------- | --------------------------- |
| LLM Provider | `AGENT_LLM_PROVIDER`      | openai / anthropic          |
| LLM API Key  | `AGENT_LLM_API_KEY`       | API 密钥                    |
| LLM Model    | `AGENT_LLM_MODEL`         | 模型名称                    |
| LLM Base URL | `AGENT_LLM_BASE_URL`      | 自定义 endpoint（本地模型） |
| Memos 地址   | `AGENT_MEMOS_ADDR`        | Memos REST API 地址         |
| 服务间密钥   | `AGENT_MEMOS_SECRET`      | HMAC 签名密钥               |
| 每用户日配额 | `AGENT_DAILY_TOKEN_LIMIT` | 默认 100000                 |

### MCP Server 配置（管理员）

MCP server 通过配置文件管理，支持多个 server 同时连接：

```yaml
# mcp_servers.yaml
servers:
  - name: web-search
    transport: stdio # stdio | sse
    command: npx # stdio 模式：启动命令
    args: ["-y", "@anthropic/mcp-server-web-search"]
    env:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    allowed_agents: ["qa", "router"] # 哪些 agent 可以使用该 server 的工具

  - name: brave-search
    transport: sse # SSE 模式：HTTP 连接
    url: http://mcp-search:3001/sse
    allowed_agents: ["qa"] # 限制只有 qa agent 可用
```

也可通过 API 动态添加（运行时生效）。

### 用户级（运行时）

- 语言风格偏好（正式/随意）
- 摘要粒度（简略/详细）
- 上下文范围（哪些 memo 可以被 agent 访问）
- opt-out 设置（是否允许 memo 内容发送给 LLM）

### Memos 侧配置

| 配置项     | 环境变量           | 说明                  |
| ---------- | ------------------ | --------------------- |
| Agent 地址 | `MEMOS_AGENT_ADDR` | 为空则禁用 agent 功能 |

## Data Privacy

用户的 memo 内容会发送给第三方 LLM provider，需要明确策略：

1. **用户知情**：首次使用 agent 功能时提示数据会发送给 LLM
2. **范围控制**：context builder 只检索和发送相关内容，不盲传全量数据
3. **opt-out**：用户可选择禁用 agent 功能或限制数据范围
4. **不持久化原始内容**：agent 不在自有数据库中存储 memo 原文，只存对话和元数据
5. **传输加密**：agent → LLM provider 强制 HTTPS

## Cost Control

LLM API 按 token 计费，需要：

- **每用户配额**：每日/每月 token 上限
- **调用频控**：每分钟请求数限制
- **用量统计**：记录每次调用的 token 消耗，按用户聚合
- **超限处理**：返回友好提示，非报错

## Fault Tolerance

| 故障场景           | 处理策略                                                       |
| ------------------ | -------------------------------------------------------------- |
| Agent 服务不可用   | Memos 主功能正常，agent 功能返回"暂不可用"提示                 |
| LLM provider 超时  | 返回超时提示，支持用户重试                                     |
| LLM provider 故障  | 可配置 fallback 到备选模型                                     |
| Memos API 调用失败 | Agent 返回工具调用失败的错误信息                               |
| MCP server 不可用  | 该 MCP server 的工具标记为不可用，agent 降级执行（跳过或报错） |

降级原则：agent 的任何故障不影响 Memos 核心功能。

## Agent Data Storage

Agent 自有数据库（SQLite），与 Memos 数据完全分离：

```
agent_db
├── conversations     # 对话历史（关联 agent_name，按 agent 隔离）
├── messages          # 对话消息（角色、内容、token 数、所属 agent）
├── tasks             # 异步任务状态和结果（关联 agent 调用链）
├── agents            # Agent 注册与启用状态
├── user_settings     # 用户级配置
├── system_settings   # 系统级配置
└── usage_logs        # token 用量记录（按用户、按 agent、按天）
```

## Deployment

```yaml
# docker-compose.yaml
services:
  memos:
    image: neosmemo/memos:latest
    ports:
      - "5230:5230"
    environment:
      - MEMOS_AGENT_ADDR=http://agent:8082
    volumes:
      - memos-data:/var/opt/memos

  agent:
    image: memos-agent:latest
    environment:
      - AGENT_LLM_PROVIDER=openai
      - AGENT_LLM_API_KEY=${OPENAI_API_KEY}
      - AGENT_LLM_MODEL=gpt-4o
      - AGENT_MEMOS_ADDR=http://memos:5230
      - AGENT_MEMOS_SECRET=${MEMOS_SECRET}
      - AGENT_DAILY_TOKEN_LIMIT=100000
    volumes:
      - agent-data:/var/opt/agent
      - ./mcp_servers.yaml:/etc/agent/mcp_servers.yaml

volumes:
  memos-data:
  agent-data:
```

Agent 是可选服务——不启动 agent 容器、不配 `MEMOS_AGENT_ADDR` 时，Memos 正常运行。

## Implementation Roadmap

> 基于当前代码现状（2026-06）的增量实施计划。Phase 1 的单 agent MVP 已基本完成（`agent/` 目录下的 deepagents 实现），以下从多 agent 架构开始。

### Phase 1 — Agent Framework（核心框架）⏱ 3-4 天

将当前单体 agent 拆分为可配置的多 agent 架构。

**1.1 Agent 定义协议（YAML）**

每个 agent 由一个 YAML 配置定义，放在 `agent/agents/` 目录下：

```yaml
# agent/agents/summary.yaml
id: summary
name: Summary Agent
description: "总结指定时间范围内的 memos，提取关键事件和人物"
icon: bar-chart-3
system_prompt: |
  你是一个总结助手。用户会要求你总结某段时间内的 memos，
  请使用 search_memos 查找相关内容，然后生成结构化总结。
  总结应包含：关键事件、涉及人物、时间线。
tools:
  - search_memos
  - get_memo
  - list_tags
mcp_servers: [] # 暂时不需要外部 MCP
```

```yaml
# agent/agents/recommend.yaml
id: recommend
name: Recommend Agent
description: "推荐附近的游玩景点、餐厅等"
icon: map-pin
system_prompt: |
  你是一个推荐助手。根据用户的位置和偏好推荐周边景点。
  先用 search_memos 了解用户历史偏好，再通过搜索获取推荐。
tools:
  - search_memos
  - get_memo
mcp_servers:
  - name: web-search
    url: http://localhost:8083/mcp
```

```yaml
# agent/agents/general.yaml
id: general
name: General Chat
description: "通用对话助手，回答关于 memos 的问题"
icon: message-square
system_prompt: |
  你是一个通用助手，帮助用户管理 memos。
tools:
  - search_memos
  - get_memo
  - create_memo
  - list_tags
  - list_resources
  - create_resource
  - update_resource
  - delete_resource
mcp_servers: []
```

**1.2 Agent Registry（Python 端）**

- 新增 `agent/registry.py` — 加载 YAML 定义的 agent 配置，动态创建 LangGraph agent
- 每个 agent 有独立的 system prompt + tool 子集 + 可选的 MCP client 连接
- `create_deep_agent` 改为 `create_agent(agent_config)` 工厂方法
- agent 间共享 checkpointer 和 MemosClient

**1.3 API 扩展**

```
GET  /v1/agents                — 列出所有可用 agents（id, name, description, icon）
POST /v1/chat                  — 增加 agent_id 参数，路由到对应 agent
GET  /v1/agents/{agent_id}     — 获取 agent 详情
```

`/v1/chat` 请求体变为：

```json
{
  "message": "总结我这个月做了什么",
  "agent_id": "summary",
  "conversation_id": "xxx"
}
```

**1.4 对话隔离**

- conversation 表增加 `agent_id` 列
- 同一用户在不同 agent 下的对话互不干扰
- checkpointer 的 `thread_id` 使用 `{agent_id}:{conversation_id}` 复合键

### Phase 2 — MCP Client 集成 ⏱ 2-3 天

让 agent 能通过 MCP 协议调用外部服务。

**2.1 Python 端 MCP Client**

- 集成 `langchain-mcp-adapters`，将 MCP tools 转为 LangChain tools
- 通过 YAML 配置连接外部 MCP server，动态加载 tools
- agent 启动时根据配置连接 MCP servers，获取可用 tools 并注入对应 agent

**2.2 利用现有 Go MCP Server**

- Go 端已有 `server/router/mcp/` 暴露了 memos 的 API
- Python agent 可作为 MCP **client** 连接 Go 端的 MCP server，替代当前硬编码的 `MemosClient`
- 短期保留 MemosClient 以避免破坏，长期可迁移为 MCP 调用

**2.3 外部 MCP Server 支持**

- 用户可在 YAML 中配置外部 MCP server URL
- agent 启动时连接这些 MCP server，获取可用 tools 并注入对应 agent
- 例如：搜索服务（Tavily/Brave）、地图服务、天气服务等
- MCP server 不可用时降级：标记该 server 的 tools 为不可用，agent 仍可使用内置 tools

### Phase 3 — 前端 UI ⏱ 4-5 天

**3.1 Agent 交互入口**

- 独立的 Chat 页面，左侧可切换 agent，右侧对话
- 对话历史按 agent + conversation 隔离
- 在 memo 详情页/列表页添加 Agent 快捷操作按钮（如"总结本页"）

**3.2 Agent 管理（Admin）**

- 在 Settings > AI 中新增 Agents tab
- 显示内置 agents 列表（不可删除）
- 支持添加自定义 agent（填写 name、description、system_prompt、选择 tools、配置 MCP servers）

**3.3 快捷调用**

- memo 列表页的筛选栏旁加 "Ask Agent" 按钮
- 选择 agent 后自动注入上下文（如当前筛选的时间范围、tag 等）

### Phase 4 — 自定义 Agent 支持 ⏱ 2-3 天

**4.1 Agent 配置存储**

- 自定义 agent 配置存入 agent 服务的 SQLite DB（`agents` 表）
- 不存在 Go 后端，因为 agent 逻辑全在 Python 端

**4.2 Agent 配置 API**

```
POST   /v1/agents              — 创建自定义 agent
PUT    /v1/agents/{agent_id}   — 更新
DELETE /v1/agents/{agent_id}   — 删除（仅自定义）
```

**4.3 Tool 权限控制**

- 内置 tools（search_memos 等）可被任意 agent 引用
- MCP tools 按 agent 配置绑定
- 敏感 tool（create_memo, delete_resource）需要 admin 授权

### Phase 5 — 高级编排与增强（后续）

1. Pipeline 编排模式（串行多 agent，如 summarizer → tagger）
2. Parallel 编排模式（并行多 agent）
3. 用户级配置（语言风格、摘要粒度）
4. 用量统计和配额（按 agent 统计）
5. Long-term memory + shared memory
6. Planner（复杂任务分解为多 agent 计划）
7. 异步任务（批量摘要等长时间任务）
8. Multi-provider fallback
9. 调用链追踪（OpenTelemetry）
10. Guardrails（输入/输出过滤、隐私控制）

### 工作量汇总

| Phase    | 内容                             | 预估         |
| -------- | -------------------------------- | ------------ |
| Phase 1  | Agent 框架 + Registry + API 扩展 | 3-4 天       |
| Phase 2  | MCP Client 集成                  | 2-3 天       |
| Phase 3  | 前端 UI                          | 4-5 天       |
| Phase 4  | 自定义 Agent 支持                | 2-3 天       |
| **合计** |                                  | **11-15 天** |

### 关键技术决策

| 决策点         | 建议                                                         | 理由                                                       |
| -------------- | ------------------------------------------------------------ | ---------------------------------------------------------- |
| Agent 定义格式 | YAML 文件（内置）+ DB（自定义）                              | 内置 agent 随代码版本管理，自定义 agent 需持久化           |
| Agent 实现     | 共享 LangGraph 框架，每 agent 独立 system_prompt + tool 子集 | 复用 deepagents 的 ReAct 循环，不需要每个 agent 写独立代码 |
| MCP Client     | `langchain-mcp-adapters`                                     | LangChain 生态原生支持，将 MCP tools 转为 LangChain tools  |
| 对话隔离       | conversation_id + agent_id 复合键                            | 同一用户在不同 agent 下的对话互不干扰                      |
| Agent 存储     | agent SQLite DB                                              | 不增加 Go 后端复杂度，agent 逻辑全在 Python 端             |

### 风险点

1. **MCP 连接稳定性** — 外部 MCP server 可能不可用，需要降级策略
2. **LLM 成本** — 多 agent 意味着更多调用，需考虑 token 限制和成本
3. **deepagents 兼容性** — `register_harness_profile` 当前排除了一些 tools，多 agent 场景需调整排除列表
4. **并发** — 多 agent 共享 checkpointer，需确认 LangGraph 的并发安全性
