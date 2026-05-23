# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Memos is a self-hosted, privacy-first note-taking service built with Go (backend) and React/TypeScript (frontend). It supports Markdown notes with tags, relations, resource attachments, and third-party integrations.

## Development Commands

### Backend

```bash
# Start backend with hot reload (runs on port 8081)
air -c scripts/.air.toml

# Run all Go tests
go test -v ./...

# Run a single test package
go test -v ./test/store/...
go test -v ./test/server/...

# Run a specific test
go test -v -run TestMemoStore ./test/store/

# Lint
golangci-lint run --timeout=3m

# Verify go.mod is tidy
go mod tidy && git diff --exit-code
```

### Frontend

```bash
cd web
pnpm i                  # Install dependencies
pnpm type-gen           # Generate TypeScript types from protobuf (runs buf generate in ../proto)
pnpm dev                # Start dev server on port 3001
pnpm build              # Build for production (tsc + vite build)
pnpm lint               # ESLint check
pnpm type-check         # TypeScript type check
```

### Full Build

```bash
./scripts/build.sh      # Builds frontend then backend binaries to ./build/
```

### Environment Variables

Tests use `DRIVER` and `DSN` env vars to select the database (defaults to SQLite with a temp file). To test with MySQL/PostgreSQL, set `DRIVER=mysql` or `DRIVER=postgres` and provide a `DSN` in a `.env` file.

## Architecture

### Backend (Go)

- **Entry point**: `bin/memos/main.go` — CLI via cobra, creates DB driver → store → server
- **Server**: `server/server.go` — Echo HTTP server, registers API v1, API v2 (gRPC gateway), and frontend serving
- **Store layer**: `store/` — Data access layer with a `Driver` interface (`store/driver.go`). Three implementations live in `store/db/{sqlite,mysql,postgres}/`. Domain models are flat files (e.g., `store/memo.go`, `store/user.go`). The `Store` struct holds in-memory caches for settings, users, and IDPs.
- **API v1**: `api/v1/` — RESTful endpoints registered directly on Echo routes. Auth uses JWT with cookie-based sessions.
- **API v2**: `api/v2/` — gRPC services defined in `proto/`, served via grpc-gateway. Each service file (e.g., `memo_service.go`) implements the gRPC server interface.
- **Plugins**: `plugin/` — Integrations: Telegram bot (`plugin/telegram/`), OpenAI (`plugin/openai/`), storage providers (`plugin/storage/`), webhooks (`plugin/webhook/`), identity providers (`plugin/idp/`)
- **Internal**: `internal/` — cron, log, util packages
- **Server services**: `server/service/` — background services (metric collection, version checker)
- **Server profile**: `server/profile/` — app configuration (mode, port, data dir, driver, DSN)

### Frontend (React/TypeScript)

- **Location**: `web/`
- **Stack**: React 18, MUI Joy, Tailwind CSS, Redux Toolkit + Zustand, Vite
- **API client**: Uses `nice-grpc-web` to call the v2 gRPC API. TypeScript types are auto-generated from protobuf definitions via `pnpm type-gen`.
- **i18n**: i18next with browser language detection

### Proto/API Definitions

- **Location**: `proto/`
- **Code generation**: `buf generate` (configured in `proto/buf.gen.yaml`) produces Go gRPC code to `proto/gen/` and TypeScript types to `web/src/types/proto/`
- After changing `.proto` files, run `pnpm type-gen` (from `web/`) to regenerate both Go and TypeScript code.

### Testing

- **Store tests**: `test/store/` — Uses `teststore.NewTestingStore()` which creates a fresh DB per test
- **Server tests**: `test/server/` — Uses `testserver.NewTestingServer()` which starts a full HTTP server and provides a test client with auth cookie management
- Test infrastructure: `test/test.go` provides `GetTestingProfile()` for creating test profiles

## Key Patterns

- **Error wrapping**: Use `errors.Wrap`/`errors.Wrapf`/`errors.Errorf` from `github.com/pkg/errors` — `fmt.Errorf` is forbidden by the linter (`forbidigo` rule).
- **Import ordering**: goimports enforces `github.com/usememos/memos` as a local prefix (grouped after third-party packages).
- **golangci-lint**: Uses revive (all rules enabled, many explicitly disabled), gocritic (ifElseChain disabled), govet (fieldalignment and shadow disabled). See `.golangci.yaml` for full config.
- **Database migrations**: Handled in `store/migrator.go`, with migration history tracked per driver.
