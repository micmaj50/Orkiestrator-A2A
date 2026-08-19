import asyncio
import sys
import uuid

import httpx

from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import new_text_message
from a2a.types import Role, SendMessageRequest
from utils.a2a_response import extract_artifact_text

from config import get_orchestrator_url

ORCHESTRATOR_URL = get_orchestrator_url()

async def chat_loop() -> None:
    # 1. Generujemy stałe ID sesji dla tego klienta (naśladuje logowanie/sesję)
    session_id = str(uuid.uuid4())
    print(f"--- Uruchomiono klienta (ID Sesji: {session_id}) ---")
    print("Wpisz 'exit' lub 'quit' aby zakończyć.\n")

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

        try:
            while True:
                # 2. Pobieramy input w pętli (nie wyłączamy klienta)
                question = await asyncio.to_thread(input, 'user > ')
                question = question.strip()

                if not question:
                    continue
                if question.lower() in ['exit', 'quit']:
                    break

                # 3. Budujemy wiadomość i wstrzykujemy nasze ID sesji
                message = new_text_message(
                        question,
                        role=Role.ROLE_USER,
                        )
                message.context_id = session_id  # <--- To połączy konwersację na serwerze!

                request = SendMessageRequest(message=message)

                print('\n === ODPOWIEDŹ ORCHESTRATORA ===')
                async for chunk in client.send_message(request):
                    artifact_text = extract_artifact_text(chunk)
                    if artifact_text:
                        print(artifact_text)
                print('\n')

        finally:
            await client.close()


def main() -> None:
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        print("\nZakończono klienta.")


if __name__ == '__main__':
    main()
