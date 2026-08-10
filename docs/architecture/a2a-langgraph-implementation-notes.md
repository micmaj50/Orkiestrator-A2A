# A2A and LangGraph Integration — Implementation Notes

This file contains the current integration decisions, problems found in the code and the next changes to make.

## Main integration boundary

LangGraph controls the workflow.

A2A is used when a LangGraph node calls a remote agent.

```text
LangGraph agent node
  ↓
build AgentRequest using shared code
  ↓
call_sub_agent(AgentRequest, agent_url)
  ↓
A2A message
  ↓
remote AgentExecutor.execute()
  ↓
agent.invoke(AgentRequest)
  ↓
A2A response
  ↓
LangGraph state update
```

The complete `GraphState` is not sent through A2A.

## Orchestrator and A2A

The orchestrator is currently an internal part of the LangGraph workflow.

The delegator runs inside `orchestrator_node` and creates the internal task list. This is a valid place for it because delegation is one step of the graph workflow.

The delegator does not need to move to an `OrchestratorAgent.invoke()` method only to match the structure used by remote agents.

A2A is needed for remote sub-agents that can be replaced or connected independently. It is not required between the application and its own internal orchestrator.

The intended current flow is:

```text
application entry point
  ↓
LangGraph
  ↓
orchestrator_node
  ↓
delegator
  ↓
agent node
  ↓
A2A remote agent call
```

If the project does not expose the orchestrator as an A2A server, an orchestrator `AgentExecutor` and its duplicated `call_sub_agent()` code are unnecessary.

If the orchestrator is exposed through A2A later, its executor should only:

1. read the incoming user request;
2. start the LangGraph workflow;
3. publish the final graph result through `EventQueue`.

It should not call gas, food or other sub-agents directly. Those calls already belong to the LangGraph agent nodes.

The delegator may later be extracted into a separate helper or service for testing, but it should still be called by `orchestrator_node`.

## Internal task naming

The project has internal models named:

- `Task`;
- `TaskStatus`.

A2A also has protocol-level task types.

The internal models should be renamed later, for example:

- `WorkItem`;
- `WorkItemStatus`.

This will avoid ambiguous imports, logs and documentation when A2A task handling is added.

## Internal statuses

The current statuses are:

- `IN_PROGRESS`;
- `COMPLETED`;
- `FAILED`.

Tasks are marked as in progress immediately after delegation, even before the router selects them.

A separate `PENDING` status may be useful later.

The workflow also does not yet define how to handle:

- missing user input;
- incomplete results;
- retries;
- tasks that cannot be completed.

This should be designed after the basic structured A2A request flow works.

## A2A `RequestContext`

Some agent code appears to use A2A `RequestContext` as application or vehicle context.

`RequestContext` is created by the A2A server. It contains the incoming message and protocol information.

Vehicle data should be sent inside `AgentRequest`:

```text
RequestContext
└── Message
    └── data
        └── AgentRequest
            └── selected application context
```

A2A `context_id` is also not the vehicle context. It identifies related A2A interactions.

## `execute()` and `invoke()`

The executor method:

```text
execute(RequestContext, EventQueue)
```

handles the A2A server side of the request.

It should:

1. read the incoming message from `RequestContext`;
2. extract the structured data;
3. validate it as `AgentRequest`;
4. call the internal agent's `invoke()` method;
5. convert the result into an A2A response;
6. publish the response through `EventQueue`.

The internal agent's `invoke()` method handles the actual agent logic.

```text
execute()
  ↓
AgentRequest
  ↓
invoke()
  ↓
agent result
  ↓
execute()
  ↓
EventQueue
```

`invoke()` should receive the validated application request, use its query, instruction and selected context, and return an application result.

It should not normally:

- read A2A message parts;
- depend on the complete `RequestContext`;
- publish events;
- create A2A clients;
- resolve remote agent URLs.

## LangGraph agent node

A LangGraph agent node should handle the workflow-specific part of the call.

It should:

1. find the internal task assigned to that agent;
2. call the shared context and request-building code;
3. receive a validated `AgentRequest`;
4. pass the request and target URL to `call_sub_agent()`;
5. receive the result;
6. update the task in `GraphState`.

The node should not manually recreate the request model or construct A2A protobuf objects.

## `call_sub_agent()`

`call_sub_agent()` is the client-side A2A adapter used by LangGraph nodes.

It should:

1. accept a validated `AgentRequest` and target agent URL;
2. serialize the request into JSON-compatible data;
3. create an A2A data message with `ROLE_USER`;
4. create `SendMessageRequest`;
5. call the A2A client's `send_message()` method;
6. extract and validate the returned result;
7. return the application result to the LangGraph node.

The helper should not decide which task to execute or which context fields to select. Those decisions belong to the LangGraph and request-building layers.

## Duplicated client logic

`a2a_client.py` contains `call_sub_agent()`.

`test_client.py` contains another request implementation with similar client setup, message creation, response handling and cleanup.

There may also be duplicated sub-agent call code in the orchestrator executor.

The shared flow should stay in `a2a_client.py`:

```text
a2a_client.py
    ↑
    ├── LangGraph agent nodes
    └── test_client.py
```

The test client should use the shared helper instead of repeating:

- Agent Card resolution;
- client construction;
- message construction;
- `SendMessageRequest` construction;
- `client.send_message()` iteration;
- response extraction;
- client cleanup.

The orchestrator executor should not use the same helper to call sub-agents if the LangGraph nodes already perform those calls.

## Response extraction

The project has custom response and artifact extraction code.

The pinned A2A SDK should be checked for existing helpers for:

- message text;
- artifact text;
- stream responses;
- structured-data parts.

Use the SDK helper when it already supports the current response type.

Keep custom parsing only when project-specific validation or response handling is needed.

## Message roles

A component sending a request to another A2A server is the client for that exchange.

Outgoing requests should use:

```text
ROLE_USER
```

Remote-agent responses should use:

```text
ROLE_AGENT
```

This should be checked in `call_sub_agent()` and `test_client.py`.

The role depends on the direction of the current A2A exchange, not on whether the component is generally called an agent.

## Structured requests

LangGraph currently sends the original user text with a text message.

The LangGraph-to-sub-agent call should send the application-level `AgentRequest` as structured data:

```text
AgentRequest
  ↓
model_dump(mode="json")
  ↓
new_data_message()
  ↓
SendMessageRequest
```

The remote executor should:

```text
RequestContext.message
  ↓
extract data
  ↓
AgentRequest.model_validate(...)
  ↓
agent.invoke(AgentRequest)
```

The external test client may continue sending a plain-text query if it is used only to test an external user request.

```text
test client → application/orchestrator: text
LangGraph node → remote sub-agent: AgentRequest data
```

## Agent URLs

Passing a raw URL to `call_sub_agent()` is acceptable for the current prototype.

For now, the main goal is to avoid repeating URL and client setup code.

A central agent registry can be added later if deployment configuration becomes more complicated.

## First structured request integration

The current LangGraph and A2A flow is already connected, but the remote agents receive only the original user text.

The first structured integration should update one existing agent flow.

### In the LangGraph agent node

1. Find the task assigned to the agent.
2. Call the shared request-building code.
3. Pass the resulting `AgentRequest` to `call_sub_agent()`.
4. Save the returned result in `GraphState`.

### In `call_sub_agent()`

1. Serialize `AgentRequest`.
2. Send it as an A2A data message.
3. Receive and extract the result.
4. Return the result to the node.

### In the remote executor

1. Extract the data from the incoming message.
2. Validate it as `AgentRequest`.
3. Call the agent's `invoke()` method.
4. Publish the result through `EventQueue`.

### In the agent's `invoke()` method

1. Read the query, instruction and selected context from `AgentRequest`.
2. Run the agent logic.
3. Return the application result.

The same flow can be applied to other agents after it works for one agent.

## Next steps

1. Confirm whether the orchestrator is exposed through A2A anywhere.
2. Remove or simplify the orchestrator A2A executor if it is unused.
3. Compare `a2a_client.py` and `test_client.py`.
4. Move duplicated request logic into `a2a_client.py`.
5. Make `test_client.py` use the shared helper.
6. Check outgoing message roles.
7. Replace custom response extraction where an SDK helper is sufficient.
8. Find incorrect uses of A2A `RequestContext`.
9. Integrate one structured `AgentRequest` flow.
10. Rename the internal task models later.
