# Current prototype

The current prototype validates the following A2A communication sequence:

`test_client -> orchestrator -> gas_station_agent -> orchestrator -> test_client`

The orchestrator acts as an A2A server when communicating with the test client and as an A2A client when communicating with the sub-agent.

# Setup

Run from the repository root:

```bash
uv sync
```

# Running the prototype

Open three terminals in the repository root

1. Start the gas station agent
```bash
uv run py -m agents.gas_agent
```

2. Start the orchestrator
```bash
uv run py -m agents.orchestrator
```

3. Run the test client
```bash
uv run py -m src/utils/test_client.py
```
