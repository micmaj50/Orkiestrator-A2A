# Testing remote agent registration with an external agent

Remote agent registration is meant for agents this repository does not own. The
`travel_planner_agent` sample from [a2aproject/a2a-samples](https://github.com/a2aproject/a2a-samples)
is a good test subject: it is built against a different A2A SDK version, it runs
in its own virtual environment and nothing about it was adapted to this project.

## 1. Run the sample agent

The sample pins `a2a-sdk 0.3.8`, while this project uses `1.1.2`. Keep the two
environments apart - clone the sample outside this repository and let `uv` build
a separate virtual environment for it.

```bash
git clone --depth 1 --filter=blob:none --sparse https://github.com/a2aproject/a2a-samples.git
cd a2a-samples
git sparse-checkout set samples/python/agents/travel_planner_agent
cd samples/python/agents/travel_planner_agent
uv sync
```

The agent talks to an OpenAI compatible endpoint. `config.json` holds the model
name, the base URL and the *name of the environment variable* that carries the
API key:

```json
{
  "model_name": "gpt-4o",
  "api_key": "API_KEY",
  "base_url": ""
}
```

```bash
echo "API_KEY=your_openai_api_key" > .env
set -a && . ./.env && set +a
uv run python __main__.py
```

The agent starts on port `10001` and serves its Agent Card at
`http://127.0.0.1:10001/.well-known/agent-card.json`.

The variable named in `config.json` has to be set or the agent exits at startup,
but the key does not have to be usable. With an unusable key the agent still
serves its card and still answers over A2A, it just replies `Sorry, an error
occurred while processing your request.` - enough to exercise discovery and
delegation. Pointing `base_url` at a local OpenAI compatible stub gives real
answers without a key.

## 2. Register it

`database.json` in the repository root already carries the sample as a disabled
entry. Set `enabled` to `true`:

```json
{
  "remote_agents": [
    {
      "key": "travel_planner",
      "base_url": "http://127.0.0.1:10001",
      "enabled": true
    }
  ]
}
```

`key` has to differ from every local agent directory name; a collision is
reported as a warning and the remote card is dropped. Start the remote agent
first, then the orchestrator, and ask something the travel planner should handle.

## 3. What this exercise showed

Checked against the running sample:

- The `1.1.2` card resolver reads the `0.3.0` card the sample serves and
  translates the flat `url` / `preferredTransport` fields into
  `supported_interfaces`, so no card conversion is needed on our side.
- `call_sub_agent` reaches the sample over JSON-RPC and comes back with
  `TASK_STATE_COMPLETED` and the agent's answer, so a foreign agent can be
  delegated to like a local one.
- A broken remote agent does not block the others: an unreachable host and a
  missing card path are reported as warnings while the healthy agents still
  register.

Skill matching was not checked against a live model, because the router needs
the `BAAI/bge-m3` weights.

## 4. Things to watch out for

**The card's own URL wins.** `base_url` is only used to fetch the card; every
later call goes to the URL inside the card. The sample advertises
`http://localhost:10001/`, which works when both processes share a host and
breaks from inside a container. A remote agent that advertises an unreachable
address cannot be redirected from `database.json`.

**Only `/.well-known/agent-card.json` is probed.** Agents older than A2A 0.3
publish `/.well-known/agent.json` and fail registration with an HTTP 404
warning. The sample serves both paths, so it is unaffected.

**Chunked artifacts arrive as separate lines.** The sample emits one artifact per
streamed token, and `extract_artifact_text` joins artifacts with newlines, so its
answer comes back one word per line. The content is complete, only the
formatting suffers. Agents that return a single final artifact, like the local
ones, are unaffected.

**A thin card may never win a query.** The sample describes its only skill as
`travel planner` and gives `hello` and `nice to meet you!` as examples. Those
examples are indexed as separate search points, and the whole card has to clear
`MIN_SKILL_SCORE` before the router will route anything to it. Check what the
remote card actually says before assuming a missing match is a registration
problem.
