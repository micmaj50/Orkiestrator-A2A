"""Minimal A2A client helper for calling sub-agents over the A2A protocol."""

import httpx

from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest

from utils.a2a_response import extract_artifact_text


async def call_sub_agent(user_request: str, agent_url: str) -> str:
    """Send a text request to an A2A sub-agent and return its text response."""

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

        if not extracted_texts:
            return ''
        
        return extracted_texts[-1]

    finally:
        await client.close()
