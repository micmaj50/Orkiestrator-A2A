import asyncio
import sys

import httpx

from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest
from utils.a2a_response import extract_artifact_text

from config import get_orchestrator_url

ORCHESTRATOR_URL = get_orchestrator_url()


async def send_message(text_query: str, context_id: str | None = None) -> str | None:
    async with httpx.AsyncClient(timeout=15.0) as httpx_client:
        resolver = A2ACardResolver(
                httpx_client=httpx_client,
                base_url=ORCHESTRATOR_URL,
                )
        orchestrator_card = await resolver.get_agent_card()

        client_config = ClientConfig(
            streaming=False,
            httpx_client=httpx_client,
            )
        
        client = await create_client(
            agent=orchestrator_card,
            client_config=client_config,
        )

        last_context_id = context_id

        try:
            message = new_text_message(
                    text_query,
                    role=Role.ROLE_USER,
                    )
            
            if context_id:
                message.context_id = context_id

            request = SendMessageRequest(message=message)

            async for chunk in client.send_message(request):
                if hasattr(chunk, 'context_id') and chunk.context_id:
                    last_context_id = chunk.context_id
                elif hasattr(chunk, 'task') and getattr(chunk.task, 'context_id', None):
                    last_context_id = chunk.task.context_id

                print('\n === RAW A2A RESPONSE ===')
                print(chunk)

                artifact_text = extract_artifact_text(chunk)
                print('\n === FINAL ANSWER===')
                if artifact_text:
                    print(artifact_text)
                else:
                    print('No artifact text returned by orchestrator')

            return last_context_id

        finally:
            await client.close()

def get_question_from_cli() -> str:
    if len(sys.argv) > 1:
        return ' '.join(sys.argv[1:])

    return input('user > ').strip()

def main() -> None:
    question = get_question_from_cli()

    while question:
        asyncio.run(send_message(question))
        try:
            question = input('\nuser > ').strip()
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == '__main__':
    main()
