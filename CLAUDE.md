# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Memos is a self-hosted, privacy-first note-taking service built with Go (backend) and React/TypeScript (frontend). It supports Markdown notes with tags, relations, resource attachments, and third-party integrations. A Python agent service (FastAPI + LangChain `deepagents`) lives in `agent/`.

## Development Commands

The project is driven by `make` (see `Makefile`). Tool paths resolve through `mise which <tool>` with plain `go`/`node`/`pnpm`/`uv` fallbacks.

### Full dev stack

```bash
make dev      # Start backend (5230), web (3001), and agent (8082) in parallel
make stop     # Kill all three by port
```

### Backend (Go)

```bash
make dev-backend                       # go run ./cmd/memos/ --port 5230
go test -v ./...                       # Run all Go tests
go test -v ./test/store/...            # One test package
go test -v -run TestMemoStore ./test/store/   # One test
golangci-lint run --timeout=3m         # Lint
go mod tidy && git diff --exit-code    # Verify go.mod is tidy
```

### Frontend (web/)

```bash
pnpm i                  # Install dependencies
pnpm type-gen           # Regenerate TS types from proto (runs buf generate in ../proto)
pnpm dev                # Dev server on port 3001, proxies API to localhost:5230
pnpm build              # tsc + vite build
pnpm release            # Production build, outputs to server/router/frontend/dist
pnpm lint               # ESLint
pnpm type-check         # tsc --noEmit
```

### Agent (agent/)

```bash
make dev-agent                       # uvicorn --reload --port 8082
make agent-setup                     # uv sync
make test-agent                      # pytest, excludes integration
make test-agent-unit                 # Unit tests only
make test-agent-api                  # API tests only
make test-agent-integration          # Requires backend + agent running
```

### Other make targets

```bash
make rebuild-payloads    # Re-extract tags/properties from memo content (stop backend first)
make type-gen            # Regenerate Go + TS from protobuf (requires buf CLI)
make docker-build        # Build Docker image (runs pnpm release first)
make docker-run          # Smoke-test the image on port 5230
```

### Environment variables

- `GOPROXY` (Makefile default `https://goproxy.cn,direct`) — Go module proxy.
- `DRIVER` / `DSN` — Tests select the DB driver (defaults to SQLite with a temp file). For MySQL/PostgreSQL set `DRIVER=mysql` or `DRIVER=postgres` and put `DSN` in a `.env` file.
- Memos runtime env vars use `MEMOS_` prefix (via Viper `SetEnvPrefix`), with `-` → `_` replacement: `MEMOS_DEMO`, `MEMOS_ADDR`, `MEMOS_PORT`, `MEMOS_DATA`, `MEMOS_DRIVER`, `MEMOS_DSN`, `MEMOS_INSTANCE_URL`, `MEMOS_AGENT_ADDR`, `MEMOS_ALLOW_PRIVATE_WEBHOOKS`, `MEMOS_LOG_LEVEL`. The Go app does **not** auto-load `.env` files — use `source .env` or a dotenv wrapper.
- `DEV_PROXY_SERVER` — Override the Vite dev proxy target (default `http://localhost:8081`; Makefile sets it to `http://localhost:5230`).

## Dev environment notes

- **First user becomes ADMIN automatically.** On a fresh DB, the first call to `CreateUser` (signup UI or `/api/v1/.../CreateUser`) is promoted to admin via `store.CreateUserIfNoUsers` (`server/router/api/v1/user_service.go:201`). Subsequent signups need password auth and registration enabled in instance settings.
- **Default data dir is the cwd** when `--data` is unset. The SQLite file is `memos_prod.db` (or `memos_demo.db` in `--demo` mode) per `internal/profile/profile.go`. To reset dev state: stop the backend and remove `memos_prod.db` + `memos_prod.db-shm` + `memos_prod.db-wal`.
- **Default ports in dev**: backend 5230, web 3001, agent 8082. The web dev server proxies `/api`, `/memos.api.v1`, and `/file` to the backend, with special SSE handling for `/api/v1/sse` (no buffering, no timeout).
- **Makefile DATA dir** defaults to `/mnt/e/data/memos` (override with `make dev DATA=/path/to/db`).

## Architecture

### Backend (Go)

- **Entry point**: `cmd/memos/main.go` — cobra CLI. Creates `db.Driver` → `store.Store` (runs `Migrate`) → `server.Server`.
- **Server**: `server/server.go` — Echo HTTP server. Registers API v1 (`/api/v1/*` + Connect-gRPC `/memos.api.v1.*`), MCP (`server/router/mcp/`), RSS (`server/router/rss/`), and the built frontend. Auth is JWT with cookie sessions (`server/auth/`).
- **Store layer**: `store/` — Data access with a `Driver` interface (`store/driver.go`). Three backends in `store/db/{sqlite,mysql,postgres}/`. Domain models are flat files (`store/memo.go`, `store/user.go`, `store/attachment.go`, etc.). `Store` holds in-memory caches for settings, users, and IDPs.
- **API services**: `server/router/api/v1/` — Implementations of the gRPC services defined in `proto/`, served via Connect/gRPC-Gateway. Each file (e.g., `user_service.go`, `memo_service.go`) implements the generated gRPC server interface. Includes SSE hub for real-time updates (`sse_hub.go`), agent proxy (`agent_proxy.go`), and ACL config (`acl_config.go`).
- **CEL filter engine**: `internal/filter/` — Parses and evaluates CEL (Common Expression Language) filter expressions for memo queries. Supports `startsWith`, `endsWith`, `matches()`, `all()` and other helpers.
- **Runner**: `server/runner/` — Background tasks (metric collection, version checker).
- **Plugins**: `plugin/` — Telegram bot (`plugin/telegram/`), OpenAI (`plugin/openai/`), storage providers (`plugin/storage/`), webhooks (`plugin/webhook/`), identity providers (`plugin/idp/`).
- **Internal**: `internal/profile/`, `internal/version/`, `internal/webhook/`, etc.

### Frontend (web/)

- **Stack**: React 18, MUI Joy, Tailwind CSS (via `@tailwindcss/vite` plugin), Vite (with Rolldown), React Compiler (`@vitejs/plugin-react` + `reactCompilerPreset`).
- **Data fetching**: `@tanstack/react-query` — all API calls go through React Query hooks in `web/src/hooks/` (e.g., `useMemoQueries.ts`, `useUserQueries.ts`). No Redux or Zustand.
- **API client**: `nice-grpc-web` against the Connect-gRPC API. TypeScript types auto-generated from `proto/`.
- **Path alias**: `@/` maps to `web/src/`.
- **i18n**: i18next with browser language detection.

### Proto / API definitions

- **Location**: `proto/`
- **API services** (`proto/api/v1/`): `ai_service`, `attachment_service`, `auth_service`, `idp_service`, `instance_service`, `memo_service`, `shortcut_service`, `user_service`, plus `common.proto`.
- **Store models** (`proto/store/`): `attachment`, `idp`, `inbox`, `instance_setting`, `memo`, `user_setting`.
- **Codegen**: `make type-gen` or `pnpm type-gen` (from `web/`) runs `buf generate` against `proto/buf.gen.yaml` → Go code to `proto/gen/`, TypeScript to `web/src/types/proto/`.

### Agent (agent/)

- Python / FastAPI on port 8082. Uses LangChain's `deepagents` runtime. Talks to the Go backend on 5230.
- **Structure**: `agent/agent/` — `main.py` (FastAPI app), `routes/` (API endpoints: `agents.py`, `chat.py`, `config.py`), `agents/` (YAML agent definitions: `general.yaml`, `recommend.yaml`, `summary.yaml`), `tools/` (`memos.py`, `memos_client.py`), `core/`, `db/`, `observability/`.
- **Tests**: `agent/tests/` — `unit/`, `api/`, `integration/` (integration tests need running backend + agent).

### MCP server

- `server/router/mcp/` — Exposes Memos as an MCP (Model Context Protocol) service. Key files: `service.go` (MCP protocol handler), `adapter.go` (Memos→MCP adapter), `catalog.go` (tool catalog), `openapi.go` (OpenAPI-based tool generation), `validation.go`.

### Testing

- **Store tests**: `test/store/` — `teststore.NewTestingStore()` builds a fresh DB per test.
- **Server tests**: `test/server/` — `testserver.NewTestingServer()` boots a real HTTP server and provides a test client with auth cookie management.
- Shared helpers in `test/test.go` (`GetTestingProfile()`).

## Key Patterns

- **Error wrapping**: Use `errors.Wrap`/`errors.Wrapf`/`errors.Errorf` from `github.com/pkg/errors` — `fmt.Errorf` is forbidden by the linter (`forbidigo` rule). `ioutil.ReadDir` is also forbidden (use `os.ReadDir`).
- **Import ordering**: goimports enforces `github.com/usememos/memos` as a local prefix (grouped after third-party packages).
- **golangci-lint**: Uses revive (all rules enabled, many explicitly disabled), gocritic (ifElseChain disabled), govet (fieldalignment and shadow disabled). `errcheck` is disabled. See `.golangci.yaml` for full config.
- **Database migrations**: Handled in `store/migrator.go`, with migration history tracked per driver.
- **Adding a new API endpoint**: 1) Define the proto service/message in `proto/api/v1/`, 2) Run `make type-gen` to generate Go + TS code, 3) Implement the gRPC server interface in `server/router/api/v1/`, 4) Register in `connect_services.go`.
