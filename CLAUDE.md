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
pnpm lint               # ESLint
pnpm type-check         # tsc --noEmit
```

### Agent (agent/)

```bash
make dev-agent                       # uvicorn --reload --port 8082
make agent-setup                     # uv sync
make test-agent                      # pytest, excludes integration
make test-agent-integration          # Requires backend + agent running
```

### Full build

```bash
./scripts/build.sh      # Builds frontend then backend binaries to ./build/
```

### Environment variables

- `GOPROXY` (Makefile default `https://goproxy.cn,direct`) — Go module proxy.
- `DRIVER` / `DSN` — Tests select the DB driver (defaults to SQLite with a temp file). For MySQL/PostgreSQL set `DRIVER=mysql` or `DRIVER=postgres` and put `DSN` in a `.env` file.
- Memos runtime flags: `MEMOS_DEMO`, `MEMOS_ADDR`, `MEMOS_PORT`, `MEMOS_DATA`, `MEMOS_DRIVER`, `MEMOS_DSN`, `MEMOS_INSTANCE_URL`, `MEMOS_LOG_LEVEL`, etc. (see `cmd/memos/main.go` for the full list and `--allow-private-webhooks`).

## Dev environment notes

- **First user becomes ADMIN automatically.** On a fresh DB, the first call to `CreateUser` (signup UI or `/api/v1/.../CreateUser`) is promoted to admin via `store.CreateUserIfNoUsers` (`server/router/api/v1/user_service.go:201`). Subsequent signups need password auth and registration enabled in instance settings.
- **Default data dir is the cwd** when `--data` is unset. The SQLite file is `memos_prod.db` (or `memos_demo.db` in `--demo` mode) per `internal/profile/profile.go`. To reset dev state: stop the backend and remove `memos_prod.db` + `memos_prod.db-shm` + `memos_prod.db-wal`.
- **Default ports in dev**: backend 5230, web 3001, agent 8082. The web dev server proxies `/api` to 5230.

## Architecture

### Backend (Go)

- **Entry point**: `cmd/memos/main.go` — cobra CLI. Creates `db.Driver` → `store.Store` (runs `Migrate`) → `server.Server`.
- **Server**: `server/server.go` — Echo HTTP server. Registers API v1 (`/api/v1/*` + Connect-gRPC `/memos.api.v1.*`), MCP (`server/router/mcp/`), RSS (`server/router/rss/`), and the built frontend. Auth is JWT with cookie sessions (`server/auth/`).
- **Store layer**: `store/` — Data access with a `Driver` interface (`store/driver.go`). Three backends in `store/db/{sqlite,mysql,postgres}/`. Domain models are flat files (`store/memo.go`, `store/user.go`, ...). `Store` holds in-memory caches for settings, users, and IDPs.
- **API services**: `server/router/api/v1/` — Implementations of the gRPC services defined in `proto/`, served via Connect/gRPC-Gateway. Each file (e.g., `user_service.go`, `memo_service.go`) implements the generated gRPC server interface.
- **Runner**: `server/runner/` — Background tasks (metric collection, version checker).
- **Plugins**: `plugin/` — Telegram bot (`plugin/telegram/`), OpenAI (`plugin/openai/`), storage providers (`plugin/storage/`), webhooks (`plugin/webhook/`), identity providers (`plugin/idp/`).
- **Internal**: `internal/profile/`, `internal/version/`, `internal/webhook/`, etc.

### Frontend (web/)

- **Stack**: React 18, MUI Joy, Tailwind CSS, Redux Toolkit + Zustand, Vite.
- **API client**: `nice-grpc-web` against the Connect-gRPC API. TypeScript types auto-generated from `proto/`.
- **i18n**: i18next with browser language detection.

### Proto / API definitions

- **Location**: `proto/`
- **Codegen**: `pnpm type-gen` (from `web/`) runs `buf generate` against `proto/buf.gen.yaml` → Go code to `proto/gen/`, TypeScript to `web/src/types/proto/`.

### Agent (agent/)

- Python / FastAPI on port 8082. Uses LangChain's `deepagents` runtime. Talks to the Go backend on 5230.

### Testing

- **Store tests**: `test/store/` — `teststore.NewTestingStore()` builds a fresh DB per test.
- **Server tests**: `test/server/` — `testserver.NewTestingServer()` boots a real HTTP server and provides a test client with auth cookie management.
- Shared helpers in `test/test.go` (`GetTestingProfile()`).

## Key Patterns

- **Error wrapping**: Use `errors.Wrap`/`errors.Wrapf`/`errors.Errorf` from `github.com/pkg/errors` — `fmt.Errorf` is forbidden by the linter (`forbidigo` rule).
- **Import ordering**: goimports enforces `github.com/usememos/memos` as a local prefix (grouped after third-party packages).
- **golangci-lint**: Uses revive (all rules enabled, many explicitly disabled), gocritic (ifElseChain disabled), govet (fieldalignment and shadow disabled). See `.golangci.yaml` for full config.
- **Database migrations**: Handled in `store/migrator.go`, with migration history tracked per driver.
