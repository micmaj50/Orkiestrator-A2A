# A2A and LangGraph Integration

## Purpose

LangGraph controls the workflow between agents.

A2A is used to send requests to remote agents and receive their responses.

LangGraph decides which agent should run. A2A handles communication with that agent.

## Responsibilities

### LangGraph

LangGraph is responsible for:

- storing the workflow state;
- creating and tracking internal tasks;
- selecting the next node;
- storing agent results;
- deciding when to run the response synthesizer.

### A2A

A2A is responsible for:

- sending messages between agents;
- receiving messages, task updates and artifacts;
- keeping protocol-level task and context identifiers;
- transporting application data such as `AgentRequest`.

`GraphState`, `AgentRequest` and A2A protocol objects are separate:

- `GraphState` stays inside LangGraph;
- `AgentRequest` contains the data sent to one remote agent;
- A2A `Message`, `Task` and `RequestContext` belong to the protocol layer.

## Current workflow

The current graph contains:

- `orchestrator_node`;
- `route_from_orchestrator`;
- `gas_agent_node`;
- `food_agent_node`;
- `response_synthesizer_node`.

```text
START
  ↓
orchestrator
  ↓
route_from_orchestrator
  ├── gas_agent  ──→ orchestrator
  ├── food_agent ──→ orchestrator
  └── response_synthesizer ──→ END
```

`GraphState` currently stores:

- the original user input;
- message history;
- the internal task list.

The orchestrator uses the delegator to split the user request into tasks and assign agents.

It creates tasks only when the task list is empty. When tasks already exist, it skips delegation.

The router selects the first task that is:

- `IN_PROGRESS`;
- assigned to a registered agent.

The selected agent node calls the remote agent, updates its task and preserves the other tasks.

Execution then returns to the orchestrator. When no in-progress task remains, the router selects the response synthesizer.

The current workflow calls agents sequentially.

## Current request flow

Agent nodes currently send the original user text through A2A:

```text
GraphState
  ↓
agent node
  ↓
call_sub_agent()
  ↓
A2A text message
  ↓
remote agent
```

This is enough for the prototype, but the message does not contain a separate delegated instruction or selected application context.

## Target request flow

The LangGraph-to-agent request should use `AgentRequest`:

```text
GraphState
  ↓
current task
  ↓
selected application context
  ↓
AgentRequest
  ↓
A2A data message
  ↓
remote agent
  ↓
result
  ↓
GraphState update
```

`AgentRequest` should contain:

- the original user query;
- the instruction assigned to the agent;
- the context selected for that agent.

Only `AgentRequest` is sent to the remote agent. The complete `GraphState` is not sent.

## LangGraph agent node

After the structured request is integrated, an agent node should:

1. find the task assigned to that agent;
2. build the selected context;
3. create `AgentRequest`;
4. send it through the shared A2A client;
5. receive the result;
6. update the task in `GraphState`.

## A2A executor

An A2A executor receives:

```text
execute(RequestContext, EventQueue)
```

`RequestContext` contains the incoming A2A request. It is not the vehicle or application context.

The executor should:

1. read the incoming message;
2. extract and validate `AgentRequest`;
3. call the internal agent implementation;
4. publish the result through `EventQueue`.

```text
RequestContext
  ↓
incoming Message
  ↓
AgentRequest
  ↓
invoke()
  ↓
result
  ↓
EventQueue
```

## First integration step

The first implementation should update one existing agent flow:

1. construct `AgentRequest` in one LangGraph node;
2. send it as an A2A data message;
3. validate it in the remote executor;
4. return the result through A2A;
5. save the result in `GraphState`.

Parallel execution, retries, user-input interrupts and the final context-selection strategy can be handled later.
