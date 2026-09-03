ENV_FILE ?= .env
UV_RUN := uv run --env-file $(ENV_FILE)

.PHONY: run-server run-orchestrator run-gas-agent run-food-agent run-parking-agent run-weather-agent run-client test-integration test-agent-registry \
	docker-config docker-build docker-up docker-up-build docker-build-no-cache docker-ps docker-logs docker-client docker-down docker-smoke

# unified server mode
run-server:
	$(UV_RUN) python -m src.server.main

# standalone mode
run-orchestrator:
	$(UV_RUN) python -m agents.orchestrator

run-gas-agent:
	$(UV_RUN) python -m agents.gas_agent

run-food-agent:
	$(UV_RUN) python -m agents.food_agent

run-parking-agent:
	$(UV_RUN) python -m agents.parking_agent

run-weather-agent:
	$(UV_RUN) python -m agents.weather_agent

run-client:
	$(UV_RUN) python src/utils/test_client.py

test-integration:
	$(UV_RUN) pytest -s tests/integration/smoke_test.py

test-agent-registry:
	$(UV_RUN) pytest -v tests/test_agent_registry.py

docker-config:
	docker compose config

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-up-build:
	docker compose up -d --build

docker-build-no-cache:
	docker compose build --no-cache

docker-ps:
	docker compose ps

docker-logs:
	docker compose logs -f $(SERVICE)

docker-client:
	docker compose run --rm test-client

docker-down:
	docker compose down

docker-smoke:
	printf 'gas\n' | docker compose run --rm -T test-client
