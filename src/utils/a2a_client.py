"""Minimal A2A client helper for calling sub-agents over the A2A protocol.

Keeps the graph nodes decoupled from the sub-agent implementations: a node
talks to a sub-agent purely through its A2A interface (agent card + JSON-RPC),
exactly like any other external A2A client would.
"""

import httpx

from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest

from utils.a2a_response import extract_artifact_text


async def call_a2a_agent(user_request: str, agent_url: str) -> str:
    """Send a text request to an A2A sub-agent and return its text response.

    Resolves the agent card to discover the A2A interface, sends the request as
    an A2A user message and returns the text of the last artifact produced.
    """

    # Resolve the agent card to discover its A2A interface and capabilities
    async with httpx.AsyncClient() as httpx_client:
        resolver = A2ACardResolver(
            httpx_client=httpx_client,
            base_url=agent_url,
        )
        agent_card = await resolver.get_agent_card()

    # Create an A2A client from the card using the default client configuration
    client = await create_client(
        agent=agent_card,
        client_config=ClientConfig(streaming=False),
    )

    try:
        # Build and send the request as an A2A user message
        request = SendMessageRequest(
            message=new_text_message(user_request, role=Role.ROLE_USER),
        )

        extracted_texts: list[str] = []
        # Iterate over the response chunks and extract text from each
        async for chunk in client.send_message(request):
            text = extract_artifact_text(chunk)
            if text:
                extracted_texts.append(text)

        return extracted_texts[-1] if extracted_texts else ''

    finally:
        await client.close()
