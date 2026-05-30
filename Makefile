.PHONY: dev-backend dev-web dev-agent dev stop test-go test-agent test-agent-unit test-agent-api test-agent-integration

# Tool paths (mise-managed)
GO      := $(shell mise which go 2>/dev/null || echo go)
NODE    := $(shell mise which node 2>/dev/null || echo node)
PNPM    := $(shell command -v pnpm 2>/dev/null || echo "npx pnpm")
UV      := $(shell command -v uv 2>/dev/null || echo "python3 -m uv")

GOPROXY ?= https://goproxy.cn,direct

# --- Dev commands ---

## Start all services for development
dev: dev-backend dev-web dev-agent

## Start Memos backend (Go, dev mode, port 5230)
dev-backend:
	GOPROXY=$(GOPROXY) $(GO) run ./bin/memos/main.go --mode dev --port 5230

## Start web frontend (React, port 3001, proxies API to backend port 5230)
dev-web: type-gen
	cd web && DEV_PROXY_SERVER=http://localhost:5230 $(PNPM) dev

## Start agent service (Python, port 8082)
dev-agent:
	cd agent && $(UV) run uvicorn agent.main:app --reload --port 8082

# --- Stop ---

## Stop all running dev services
stop:
	@lsof -ti:5230 2>/dev/null | xargs kill 2>/dev/null; true
	@lsof -ti:3001 2>/dev/null | xargs kill 2>/dev/null; true
	@lsof -ti:8082 2>/dev/null | xargs kill 2>/dev/null; true
	@echo "All services stopped."

# --- Build ---

## Build agent dependencies
agent-setup:
	cd agent && $(UV) sync

## Generate TypeScript types from protobuf
type-gen:
	cd web && $(PNPM) i && $(PNPM) type-gen

# --- Test ---

## Run Go tests
test-go:
	$(GO) test -v ./...

## Run Python agent tests (unit + API, excludes integration)
test-agent:
	cd agent && $(UV) run pytest tests/ -v -m "not integration"

## Run Python agent unit tests only
test-agent-unit:
	cd agent && $(UV) run pytest tests/unit/ -v

## Run Python agent API tests only
test-agent-api:
	cd agent && $(UV) run pytest tests/api/ -v

## Run Python agent integration tests (requires running services)
## Prerequisites:
##   1. Memos backend running on port 5230: make dev-backend
##   2. Agent service running on port 8082: make dev-agent
## Usage:
##   make test-agent-integration
##   Or with custom credentials:
##   MEMOS_USERNAME=your_user MEMOS_PASSWORD=your_pass make test-agent-integration
test-agent-integration:
	cd agent && $(UV) run pytest tests/integration/ -v
