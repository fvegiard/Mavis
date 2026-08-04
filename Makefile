# Makefile for Jarvis (Mavis agent system)
# Usage: make <target>

.PHONY: help install test lint setup clean all

PYTHON ?= python3
RUFF ?= uv run --with ruff ruff

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all mavis-* symlinks in /usr/local/bin
	./scripts/mavis-setup-links.sh

test: ## Run all tests
	$(PYTHON) -m unittest discover tests/ -v

lint: ## Run ruff on all scripts
	$(RUFF) check scripts/

setup: ## Initial setup (install + lint + test)
	@make install
	@make lint
	@make test

all: lint test ## Lint then test

# Individual tool shortcuts
rag: ## Quick RAG query (use: make rag Q="your question")
	@if [ -z "$(Q)" ]; then echo "Usage: make rag Q=\"your question\""; exit 1; fi
	mavis-rag "$(Q)"

providers: ## Test all LLM providers
	mavis-providers test

chain: ## Show provider fallback chain
	mavis-providers chain

commit: ## Commit with Copilot review (use: make commit M="msg")
	@if [ -z "$(M)" ]; then mavis-commit --push; else mavis-commit -m "$(M)" --push; fi

clean: ## Remove cache files (data/, __pycache__, .ruff_cache)
	rm -rf data/__pycache__ scripts/__pycache__ .ruff_cache
	rm -f a2a/outbox.jsonl a2a/inbox.jsonl
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
