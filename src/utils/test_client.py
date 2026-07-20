import asyncio
import sys

import httpx

from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest
from utils.a2a_response import extract_artifact_text

from config import get_orchestrator_url

ORCHESTRATOR_URL = get_orchestrator_url()


async def send_message(text_query: str) -> None:
    # Resolve the agent card to discover its A2A interface and capabilities
    async with httpx.AsyncClient() as httpx_client:
        resolver = A2ACardResolver(
                httpx_client=httpx_client,
                base_url=ORCHESTRATOR_URL,
                )
        orchestrator_card = await resolver.get_agent_card()

    # Create an A2A client from the card using the default client configuration
    client_config = ClientConfig(streaming=False)
    client = await create_client(
            agent=orchestrator_card,
            client_config=client_config,
            )

    try:
        # Build and send the request as an A2A user message
        message = new_text_message(
                text_query,
                role=Role.ROLE_USER,
                )
        request = SendMessageRequest(message=message)

        # Iterate over the response chunks and display each one and its extracted artifact text for comparison
        async for chunk in client.send_message(request):
            print('\n === RAW A2A RESPONSE ===')
            print(chunk)

            artifact_text = extract_artifact_text(chunk)
            print('\n === FINAL ANSWER===')
            if artifact_text:
                print(artifact_text)
            else:
                print('No artifact text returned by orchestrator')

    finally:
        await client.close()

def get_question_from_cli() -> str:
    if len(sys.argv) > 1:
        return ' '.join(sys.argv[1:])

    return input('user > ').strip()

def main() -> None:
    question = get_question_from_cli()

    if not question:
        print('No question provided')
        return

    asyncio.run(send_message(question))

if __name__ == '__main__':
    main()
