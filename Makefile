ENV_FILE ?= .env
UV_RUN := uv run --env-file $(ENV_FILE)

.PHONY: run-orchestrator run-gas-agent run-food-agent run-parking-agent run-client

run-orchestrator:
	$(UV_RUN) python -m agents.orchestrator

run-gas-agent:
	$(UV_RUN) python -m agents.gas_agent

run-food-agent:
	$(UV_RUN) python -m agents.food_agent

run-parking-agent:
	$(UV_RUN) python -m agents.parking_agent

run-client:
	$(UV_RUN) python src/utils/test_client.py

test-integration:
	$(UV_RUN) pytest -s tests/integration/smoke_test.py
