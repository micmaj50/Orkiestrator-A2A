import asyncio
import sys
import uuid

import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest

from config import get_orchestrator_url
from utils.a2a_response import extract_artifact_text

ORCHESTRATOR_URL = get_orchestrator_url()

async def chat_loop() -> None:
    # permanent session ID for this client
    session_id = str(uuid.uuid4())
    print(f"--- Client started (Session ID: {session_id}) ---")
    print("Type 'exit' or 'quit' to finish.\n")

    # Resolve the agent card to discover its A2A interface and capabilities
    async with httpx.AsyncClient(timeout=15.0) as httpx_client:
        resolver = A2ACardResolver(
                httpx_client=httpx_client,
                base_url=ORCHESTRATOR_URL,
                )
        orchestrator_card = await resolver.get_agent_card()

        # Create an A2A client from the card using the default client configuration
        client_config = ClientConfig(
            streaming=False,
            httpx_client=httpx_client,
            )

        client = await create_client(
            agent=orchestrator_card,
            client_config=client_config,
        )

        try:
            while True:
                # input in a loop
                question = await asyncio.to_thread(input, 'user > ')
                question = question.strip()

                if not question:
                    continue
                if question.lower() in ['exit', 'quit']:
                    break

                # Build and send the request as an A2A user message with session ID
                message = new_text_message(
                        question,
                        role=Role.ROLE_USER,
                        )
                message.context_id = session_id

                request = SendMessageRequest(message=message)

                async for chunk in client.send_message(request):
                    # print('\n === RAW A2A RESPONSE ===')
                    # print(chunk)

                    artifact_text = extract_artifact_text(chunk)
                    print('\n === FINAL ANSWER===')
                    if artifact_text:
                        print(artifact_text)
                print('\n')

        finally:
            await client.close()


def main() -> None:
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        print("\nClient finished.")


if __name__ == '__main__':
    main()
