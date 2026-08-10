# Docker local development notes

Quick reference for the Docker Compose commands and Makefile targets.

## Dockerfile

The `Dockerfile` describes how to build one application image.

The image contains:

- Python;
- uv;
- project dependencies;
- project source code.

Rebuild the image after changing the Dockerfile, dependencies or source code copied into the image.

## Docker Compose

The Compose file describes which containers should be created from the image and how they communicate.

Each service can have:

- its own command;
- environment variables;
- a service name used as a hostname;
- dependencies on other service;

Compose service names also work as hostnames inside the Compsose network:

`http://food-agent:9997`
`http://gas-agent:9998`
`http://orchestrator:9999`

Servers bind to `0.0.0.0` inside their containers. Other containers connect using the service name, not `0.0.0.0` or `127.0.0.1`.

## Image and container

An image is the built application template.

A container is a running instance of that image.

`docker compose build` builds targets.

`docker compose up` creates and starts containers.

## Makefile targets

The Makefile targets are shorter aliases for Docker Compose commands.

#### `make docker-config`

Runs: 

`docker compose config`

Shows the final Compose configuration after variables have been substituted.

Useful after changing:

- the Compose file;
- `.env`;
- service environment variables.

#### `make docker-build`

Runs:

`docker compose build`

Builds the service images without starting containers.

Docker reuses cached layers when possible.
Use it after changing:

- `Dockerfile`;
- `pyproject.toml`;
- `uv.lock`;
- source code copied into the image.

#### `make docker-up`

Runs:

`docker compose up -d`

Creates or recreates the containers and starts them in the background using the existing images.
Use it only when Compose configuration or environment values changed.

#### `make docker-up-build`

Runs: 

`docker compose up -d --build`

Builds changed images and then starts or recreates the containers.
Use this after changing application code, dependencies or the Dockerfile.

#### `make docker-build-no-cache`

Runs:

`docker compose build --no-cache`

Rebuilds every layer without using the cache. Use it when debugging a possible cache problem.

#### `make docker-ps`

Runs:

#### `docker compose ps`

Shows the state of the Compose containers.

Useful for checking whether a service is:

- running;
- stopped;
- restarting;
- unhealthy.

#### `make docker-logs`

Runs:

`docker compose logs -f`

Follows logs from all services.

For one service:

`make docker-logs SERVICE=orchestrator`

Runs:

`docker compose logs -f orchestrator`

#### `make docker-client`

Runs:

`docker compose run --rm test-clent`

Creates a temporary test-client container and runs its configured command.
`--rm` removes that container after it exists.

#### `make docker-down`

Runs:
`docker compose down`

Stops and removes containers created by the Compose project and removes its network.

## Common sequences

### Inspect the configuration

`make docker-config`

### Build for the first time or after changing source code

`make docker-build`
`make docker-up`
`make docker-ps`
`make docker-logs`

Equivalent:
`make docker-up-build`
`make docker-ps`
`make docker-logs`

### After changing `.env` or Compose environment variables

`make docker-up`

Compose should recreate containers whose configuration changed.

Inspect: 
`make docker-ps`

### Run the test client

With the service containers already running:

`make docker-client`

### Follow one service

`make docker-logs SERVICE=orchestrator`

### Rebuild without cache

`make docker-build-no-cache`
`make docker-up`

### Stop everything:

`make docker-down`

## Environment variables

Compose reads the project-level `.env` file for variable substitution:

```
environment:
    GAS_AGENT_PORT: "${GAS_AGENT_PORT}"
```

A default variable can be provided when the variable is missing or empty:

```
environment:
    GAS_AGENT_PORT: "${GAS_AGENT_PORT:-9998}"
```

Some values can be set directly in the file when they should always use Docker-specific configuration:


```
environment:
    GAS_AGENT_HOST: "gas-agent"
```

They do not use the corresponding values from `.env`.

API keys and other secrets should be read from the local `.env` file. They must not be written in the Compose file.

In GitLab Ci/CD, secrets should be added through **Settings -> CI/CD -> Variables**. GitLab Runner exposes them as environment variables, so Docker Compose can use the same `${VARIABLE_NAME}` syntax without a `.env` file.
Non-secret values can use safe defaults from the Compose file or be defined directly in `gitlab-ci.yml` when CI needs different values.
