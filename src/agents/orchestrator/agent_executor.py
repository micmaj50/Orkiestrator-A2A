import httpx
from a2a.client import A2ACardResolver, ClientConfig, create_client
from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Role, SendMessageRequest, TaskState
from utils.a2a_response import extract_artifact_text
from langfuse import observe, get_client

from config import get_food_agent_url, get_gas_agent_url, get_parking_agent_url, get_weather_agent_url

GAS_AGENT_URL  = get_gas_agent_url()
FOOD_AGENT_URL = get_food_agent_url()
PARKING_AGENT_URL = get_parking_agent_url()
WEATHER_AGENT_URL = get_weather_agent_url()


class Orchestrator:
    """Simple orchestrator"""

    @observe(name="orchestrator_invoke")
    async def invoke(self, user_request: str) -> str:
        question = user_request.lower()

        if 'gas' in question:
            gas_result = await self._call_sub_agent(user_request, GAS_AGENT_URL)
            return self._format_result(gas_result)

        if 'food' in question:
            food_result = await self._call_sub_agent(user_request, FOOD_AGENT_URL)
            return self._format_result(food_result)
        
        if 'parking' in question:
            parking_result = await self._call_sub_agent(user_request, PARKING_AGENT_URL)
            return self._format_result(parking_result)

        if 'weather' in question:
            return await self._call_sub_agent(user_request, WEATHER_AGENT_URL)

        return(
                'Unsupported request\n'
                'Try: "find closest gas stations"\n'
                'Or:  "find closest food points"\n'
                'Or:  "find parking nearby"'
                )

    async def _call_sub_agent(self, user_request: str, agent_url: str) -> str:
        """Send a request to a sub-agent and return its text response"""

        client_lf = get_client()
        current_trace_id = client_lf.get_current_trace_id()
        current_span_id = client_lf.get_current_observation_id()
         
        # Resolve the agent card to discover its A2A interface and capabilities
        async with httpx.AsyncClient() as httpx_client:
            resolver = A2ACardResolver(
                    httpx_client=httpx_client,
                    base_url=agent_url,
                    )
            sub_agent_card = await resolver.get_agent_card()

        # Create an A2A client from the card using the default client configuration
        client_config = ClientConfig(streaming=False)
        client = await create_client(
                agent=sub_agent_card,
                client_config=client_config,
                )

        try:
            # Build and send the request as an A2A user message
            message = new_text_message(
                    user_request,
                    role=Role.ROLE_USER,
                    )
            
            if current_trace_id:
                trace_data = {
                    "langfuse_trace_id": current_trace_id,
                    "langfuse_parent_observation_id": current_span_id or "",
                }
                
                if message.metadata is None:
                    message.metadata = {}

                if hasattr(message.metadata, "update"):
                    message.metadata.update(trace_data)
                else:
                    for k, v in trace_data.items():
                        message.metadata[k] = v

            request = SendMessageRequest(message=message)

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

    def _format_result(self, agent_result: str) -> str:
        """Format text extracted from the sub agent result for the orchestrator response"""

        if not agent_result:
            return 'Sub-agent returned no stations'

        locations = [
                location.strip()
                for location in agent_result.replace('\n', ',').split(',')
                if location.strip()
                ]

        if not locations:
            return 'Sub-agent returned no stations'

        locations_lines = '\n'.join(f'- {location}' for location in locations)

        return f'Closest locations:\n{locations_lines}'

class OrchestratorExecutor(AgentExecutor):
    """A2A executor for the orchestrator"""
    
    def __init__(self) -> None:
        self.agent = Orchestrator()

    # Implement the execute method required by the AgentExecutor base class
    @observe(name="orchestrator_execute")
    async def execute(
            self,
            context: RequestContext,
            event_queue: EventQueue,
            ) -> None:

        # 1. Reuse the current task or create one for a new request
        if context.current_task:
            task = context.current_task
        else:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)


        # 2. Mark the task as working in EventQueue before invoking the orchestrator logic
        task_updater = TaskUpdater(
            event_queue=event_queue, 
            task_id=task.id, 
            context_id=task.context_id
        )

        await task_updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message('Orchestrator is processing request...'),
        )


        # 3. Extract the user's text and pass it to the orchestrator
        query = get_message_text(context.message)
        if query:
            result = await self.agent.invoke(user_request=query)
        else:
            result = 'No text input is provided!'

        # 4. Add the orchestrator response as an artifact to EventQueue
        await task_updater.add_artifact(
                parts=[
                    new_text_part(
                        text=result, 
                        media_type='text/plain'
                        )
                    ]
                )
        print('Orchestrator result: ', result)

        # 5. Update task status to completed
        await task_updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message('Sub-agent request is completed!'),
        )


    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Raise exception as cancel is not supported."""
        raise NotImplementedError('Cancel is not supported.')
