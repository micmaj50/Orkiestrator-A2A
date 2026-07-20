# System Design: Context Sharing Between Orchestrator and Sub-Agents

## Purpose

The orchestrator may have access to different kinds of system context, for example:
- current location
- fuel type
- remaining range
- active route
- estimated arrival time

A sub-agent should not automatically receive the complete context. This document describes how selected context could be exposed to a sub-agent. 

> **Core Decision: Strategy 2 (Attach a fixed subset according to the receiving agent)**
> Application code defines a fixed set of context fields for each sub-agent or capability.

## Current Context Model

Vehicle-related information is currently divided into:
- `VehicleProfile` - stable properties;
- `VehicleTelemetry` - frequently changing values;

`CarContext` groups these two classes.

Conceptually:
CarContext
├── vehicle_profile
│   └── fuel_type
└── vehicle_telemetry
    ├── current_location
    └── remaining_range_km

- the orchestrator will have access to this information;
- it is undecided how much context each sub-agent receives;
- sub-agents internals may be deterministic, API-based or model-based (?), which will determine the decision.

> Note: Route-related information may later belong to a separate `TripContext` rather than `CarContext`, but this is still subject to discussion.

## Context-Sharing Strategies

The strategies explain who decides which context is included in an agent request. In every strategy, the orchestrator constructs the final request and sends it through A2A.

### 1. Send the entire available context
The orchestrator attaches the complete context object to every sub-agent request.

**Advantages:**
- simple -- no context-selection logic is required.

**Risks/Disadvantages:**
- irrelevant context may distract an LLM-based sub-agent; (?)
- potentially larger prompts (increased latency/cost); (?)
- accidental information exposure.

### 2. Attach a fixed subset according to the receiving agent
Application code defines a fixed set of context fields for each sub-agent or capability.

**Advantages:**
- predictable and easy to test and validate;
- no responsibility is placed on the orchestrator model;
- agents receive only fields considered relevant to them.

**Risks/Disadvantages:**
- fixed rules can become too rigid, as different tasks handled by the same agent might require slightly different context;
- adding a new capability or updating an agent requires modifying the context selection code.

### 3. Let the orchestrator choose context keys dynamically
The orchestrator analyzes the task and dynamically selects the necessary context keys on the fly.

**Advantages**:
- highly flexible and context-aware for varied user queries.
- minimizes prompt size by only sending what the orchestrator actively needs.

**Risks/Disadvantages**:
- risk of the orchestrator hallucinating keys (requires strict Pydantic validation and retry logic).
- risk of the orchestrator omitting required context for a given task.
- higher load and responsibility placed on the orchestrator model.

### 4. Hybrid: fixed allowed catalogue per agent, from which the orchestrator selects a subset
A hybrid approach combining fixed boundaries with orchestrator flexibility. 

1. Code defines which context keys each agent is allowed to receive (Allowed Catalogue).
2. The orchestrator may request a subset of those keys dynamically.
3. The system (via Pydantic) rejects unknown or forbidden values.
4. Python code retrieves the actual context values based on the validated request.

**Advantages**:
- balances dynamic flexibility (like Strategy 3) with strict safety boundaries (like Strategy 2);
- prevents unauthorized agents from accessing sensitive global context;
- minimizes prompt size and sub-agent distraction.

**Risks/Disadvantages**:
- highest architectural complexity, requiring maintenance of both catalogues and dynamic logic;
- the orchestrator might still omit allowed context keys that it needs;
- requires the same robust error and retry handling as Strategy 3.

#### Example Catalogue Concept
This is an example of boundaries for Strategy 2 and Strategy 4, as the complete set of system context fields has not yet been finalized.

Global context catalogue:
- current_location, fuel_type, remaining_range, active_route, arrival_time

Food agent allowed catalogue:
- current_location, active_route, arrival_time

Gas agent allowed catalogue:
- current_location, fuel_type, remaining_range, active_route

## Recommendation and Next Steps

While all four strategies are outlined for completeness, we probably should strongly consider a catalogue-based approach — either **Strategy 2 (Fixed Subset)** or **Strategy 4 (Hybrid)**. 

The primary architectural benefits of these two approaches are:

- **Visibility and Predictability (Strategy 2):** By defining fixed subsets in the application code, the exact scope of what an agent works on is highly transparent. We as engineers can see the exact context that shapes the request directly in the code, instead of having to read through the agent's internal logic. 
- **Task-Specific Precision (Strategy 4):** We define a somewhat broad subset of allowed context, but the orchestrator is authorized to narrow this down into an even tinier, task-specific scope before sending the request.

**Next Steps / Prototyping:**
The final decision between Strategy 2 and Strategy 4 depends on testing the orchestrator's capabilities. If we choose Strategy 4, we must test whether the orchestrator model can reliably select this "tinier scope" on the fly. If testing shows that the model fails too often or makes unintuitive context choices, we should fall back to the strict, code-defined predictability of Strategy 2.
