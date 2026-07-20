# Implementation Details: Payload in A2A Message & Pydantic Models

## General Communication Rules

A sub-agent doesn't automatically have access to the complete CarContext, LangGraph state, or other agent results. Application-level requests are represented as Pydantic models.

### Agent Request Contract
A delegated request will need at least the user query, task, and context.

Example JSON payload:
```json
{
    "user_query": "Find sushi before I arrive at Sandy's",
    "task": "Find suitable sushi places along the active route",
    "context": {
        "current_location": {
            "latitude": 53.4254,
            "longitude": 14.5511
        },
        "active_route": "...",
        "arrival_time": "2026-07-14T20:00:00+02:00"
    }
}
```

## A2A Serialization Flow

The current JSON-RPC implementation relies on standard serialization pipelines. 

Orchestrator Flow:
Pydantic AgentRequest -> model_dump(mode='json') -> dict -> new_data_message() / new_data_part() -> ParseDict() -> google.protobuf.Value -> A2A Part.data -> A2A Message -> SendMessageRequest -> client.send_message()

Server / AgentExecutor Flow:
Receives SendRequestMessage -> Constructs A2A RequestContext -> AgentExecutor.execute(context) -> context.message -> get_data_parts() -> MessageToDict -> dict -> AgentRequest.model_validate() -> Pydantic AgentRequest

> Migration Note: The current prototype sends plain-text A2A messages and doesn't fully utilize the SDK helpers for structured Pydantic-based communication. The custom parsing logic in `a2a_response.py` must be reviewed and updated.

## Pydantic Configuration

For communication contracts, strict validation is required.

| Configuration | Behavior | Recommendation |
| :--- | :--- | :--- |
| `extra='ignore'` | Silently discards unknown fields | Avoid |
| `extra='forbid'` | Rejects the input with a `ValidationError` | **Recommended** |
| `extra='allow'` | Preserves unknown fields in `__pydantic_extra__` | Avoid |

extra='forbid' is strictly preferred because misspelled or incorrectly exposed fields from the Orchestrator should be detected immediately rather than silently removed.

## How to Construct Context Models

There are three architectural options for defining the Pydantic context schemas.

### 1. Flat Agent Context (Recommended)

```python
class FoodAgentContext(BaseModel):
    current_location: Coordinates | None = None
```


**Advantages:**
- smallest and simplest payload;
- agent doesn't need to understand orchestrator's internal context structure;
- easier to change.

**Disadvantages:**
- original source path is lost (but can be reconstructed in code if needed - probably still redundant)
- potential naming collisions

### 2. Agent-Specific Nested Projection Models

```python
class FoodVehicleTelemetryContext(BaseModel):
        current_location: Coordinates | None = None

class FoodVehicleContext(BaseModel):
        telemetry: FoodVehicleTelemetryContext | None = None

class FoodAgentContext(BaseModel):
        vehicle: FoodVehicleContext | None = None
```

**Advantages:**
- preserves the source hierarchy
- strict

**Disadvantages:**
- duplicates many models
- more code and high maintenance
- every agent needs its own projection tree

### 3. Reuse Existing Global Context Models

```python
class VehicleProfile(BaseModel):
    fuel_type: FuelType | None = None

class VehicleTelemetry(BaseModel):
    current_location: Coordinates | None = None
    remaining_range_km: float | None = Field(default=None, ge=0)

class CarContext(BaseModel):
    profile: VehicleProfile | None = None
    telemetry: VehicleTelemetry | None = None

class FoodAgentContext(BaseModel):
    vehicle: CarContext | None = None
```

**Advantages:**
- preserves the same nested structure while remaining flexible
- quick to implement

**Disadvantages:**
most importantly, it forces all fields to become optional (ruining strict validation guarantees elsewhere in the system, in case it's true).
