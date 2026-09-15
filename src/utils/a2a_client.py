"""Minimal A2A client helper for calling sub-agents over the A2A protocol."""

from a2a.client import ClientCallContext, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import AgentCard, Role, SendMessageRequest, TaskState
from langfuse import get_client

from config import get_sub_agent_timeout_seconds
from utils.a2a_response import extract_agent_result

langfuse = get_client()


async def call_sub_agent(user_request: str, agent_card: AgentCard) -> tuple[TaskState, str]:
    """Send a text request to an A2A sub-agent using its registered Agent Card."""

    trace_id = langfuse.get_current_trace_id()
    parent_observation_id = langfuse.get_current_observation_id()

    # Create an A2A client from the card using the default client configuration
    client = await create_client(
        agent=agent_card,
        client_config=ClientConfig(streaming=False),
    )

    try:
        message = new_text_message(
            user_request,
            role=Role.ROLE_USER
        )

        if trace_id and parent_observation_id:
            message.metadata.update({
                "langfuse_trace_id": trace_id,
                "langfuse_parent_observation_id": parent_observation_id
            })

        # Build and send the request as an A2A user message
        request = SendMessageRequest(message=message)

        call_context = ClientCallContext(timeout=get_sub_agent_timeout_seconds())

        result: tuple[TaskState, str] | None = None

        # Iterate over the response chunks and extract the final state and text.
        async for chunk in client.send_message(request, context=call_context):
            result = extract_agent_result(chunk) or result

        if result is None:
            return TaskState.TASK_STATE_FAILED, 'The sub-agent never reported a final state.'

        state, text = result

        # A success with nothing in it is a failure.
        if state == TaskState.TASK_STATE_COMPLETED and not text.strip():
            return TaskState.TASK_STATE_FAILED, 'The sub-agent reported success but returned no answer.'

        return state, text

    finally:
        await client.close()
