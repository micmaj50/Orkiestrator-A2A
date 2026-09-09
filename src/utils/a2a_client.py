"""Minimal A2A client helper for calling sub-agents over the A2A protocol."""

import httpx
from a2a.client import A2ACardResolver, ClientCallContext, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest
from langfuse import get_client

from config import get_sub_agent_timeout_seconds
from utils.a2a_response import extract_artifact_text


langfuse = get_client()


async def call_sub_agent(user_request: str, agent_url: str) -> str:
    """Send a text request to an A2A sub-agent and return its text response."""

    trace_id = langfuse.get_current_trace_id()
    parent_observation_id = langfuse.get_current_observation_id()

    # Resolve the agent card to discover its A2A interface and capabilities
    async with httpx.AsyncClient() as httpx_client:
        resolver = A2ACardResolver(
            httpx_client=httpx_client,
            base_url=agent_url,
        )
        sub_agent_card = await resolver.get_agent_card()

    # Create an A2A client from the card using the default client configuration
    client = await create_client(
        agent=sub_agent_card,
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

        extracted_texts: list[str] = []

        call_context = ClientCallContext(timeout=get_sub_agent_timeout_seconds())

        # Iterate over the response chunks and extract text from each
        async for chunk in client.send_message(request, context=call_context):
            text = extract_artifact_text(chunk)
            if text:
                extracted_texts.append(text)

        if not extracted_texts:
            return ''

        return extracted_texts[-1]

    finally:
        await client.close()
