.PHONY: dev-backend dev-web dev-agent dev stop rebuild-payloads test-go test-agent test-agent-unit test-agent-api test-agent-integration \
        docker-build docker-push docker-login docker-run docker-stop docker-pull docker-compose-up docker-compose-down

# Tool paths (mise-managed)
GO      := $(shell mise which go 2>/dev/null || echo go)
NODE    := $(shell mise which node 2>/dev/null || echo node)
PNPM    := $(shell command -v pnpm 2>/dev/null || echo "npx pnpm")
UV      := $(shell command -v uv 2>/dev/null || echo "python3 -m uv")

GOPROXY ?= https://goproxy.cn,direct

# Data dir for the backend (SQLite lives at $(DATA)/memos_prod.db).
# Override on the command line: make dev DATA=/path/to/db
# DATA ?= output/db
DATA ?= /Users/pingqixing/data/NAS/memos

# --- Dev commands ---

## Start all dev services in parallel: backend (5230), web (3001), agent (8082)
## Ctrl-C stops all of them. Each log line is prefixed by its service.
dev:
	@trap 'kill 0' INT TERM EXIT; \
	$(MAKE) --no-print-directory dev-backend 2>&1 | sed -u 's/^/[backend] /' & \
	$(MAKE) --no-print-directory dev-web     2>&1 | sed -u 's/^/[web]     /' & \
	$(MAKE) --no-print-directory dev-agent   2>&1 | sed -u 's/^/[agent]   /' & \
	wait

## Start Memos backend (Go, port 5230, data dir $(DATA))
dev-backend:
	GOPROXY=$(GOPROXY) $(GO) run ./cmd/memos/ --port 5230 --data $(DATA) --agent-addr http://localhost:8082

## Start web frontend (React, port 3001, proxies API to backend port 5230)
dev-web:
	cd web && DEV_PROXY_SERVER=http://localhost:5230 $(PNPM) dev

## Start agent service (Python, port 8082)
dev-agent:
	cd agent && $(UV) run uvicorn agent.main:app --reload --port 8082

## Re-extract tags/properties from memo content into memo.Payload (one-shot maintenance)
## Make sure backend is stopped before running. Override data dir: make rebuild-payloads DATA=/path
rebuild-payloads:
	GOPROXY=$(GOPROXY) $(GO) run ./cmd/memos/ rebuild-memo-payloads --data $(DATA)

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

## Regenerate Go and TypeScript code from protobuf (requires buf: brew install buf)
type-gen:
	cd proto && buf generate

# --- Docker ---

# Image defaults. Override on the command line:
#   make docker-build TAG=personal-fd18f559 PLATFORM=linux/amd64
IMAGE    ?= navono/memos
TAG      ?= personal
PLATFORM ?= linux/arm64

## Build the Docker image (runs `pnpm release` first to embed frontend assets)
docker-build:
	cd web && $(PNPM) release && cd ..
	docker build -f scripts/Dockerfile \
	  -t $(IMAGE):$(TAG) \
	  --build-arg VERSION=$(TAG) \
	  --build-arg COMMIT=$$(git rev-parse --short HEAD) \
	  --platform=$(PLATFORM) .

## Push the image to the configured registry (run `make docker-login` first)
docker-push:
	docker push $(IMAGE):$(TAG)

## Log in to Docker Hub (interactive; pass a username and PAT/password)
docker-login:
	docker login

## Run the image locally for smoke testing (port 5230, data dir output/docker-data)
docker-run:
	docker run -d --name memos --rm \
	  -p 5230:5230 \
	  -v $$(pwd)/output/docker-data:/var/opt/memos \
	  -e MEMOS_PORT=5230 \
	  $(IMAGE):$(TAG)

## Stop and remove the local memos container
docker-stop:
	docker stop memos 2>/dev/null || true
	docker rm memos 2>/dev/null || true

## Pull the image (use on the server before redeploying)
docker-pull:
	docker pull $(IMAGE):$(TAG)

## Start the stack via docker compose (uses scripts/compose.yaml)
docker-compose-up:
	docker compose -f scripts/compose.yaml up -d

## Stop the stack via docker compose
docker-compose-down:
	docker compose -f scripts/compose.yaml down

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
