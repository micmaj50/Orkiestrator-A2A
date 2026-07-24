from datetime import datetime, timezone

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState

from agents.graph import graph
from agents.state import GraphState

from common.fuel import FuelType
from common.location import Coordinates
from context.car import CarContext, VehicleProfile, VehicleTelemetry


def build_default_car_context() -> CarContext:
    """Build the vehicle context seeded into the graph state.
    TODO: Replace this mock with a real vehicle telemetry source (GPS, fuel
    sensors, ...). For now it provides deterministic data so the orchestrator
    and sub-agents can be exercised end to end.
    """
    return CarContext(
        profile=VehicleProfile(
            fuel_type=FuelType.PETROL_95,
            tank_capacity=50.0,
        ),
        telemetry=VehicleTelemetry(
            # Warsaw city center, matching the fallback previously hard-coded in the agents.
            current_location=Coordinates(latitude=52.2297, longitude=21.0122),
            remaining_range_km=120.0,
            observed_at=datetime.now(timezone.utc),
        ),
    )


class Orchestrator:
    """
    Orchestrator backed by the LangGraph multi-agent graph.
    
    Builds the initial graph state from the user's request, runs the graph and returns the final text answer.
    """

    async def invoke(self, user_request: str, context_id: str | None = None) -> str:
        human_message = HumanMessage(content=user_request)

        graph_input = GraphState(
            user_input=human_message,
            messages=[human_message],
            tasks=[],
            car=build_default_car_context(),
        )

        config: RunnableConfig = {'configurable': {'thread_id': context_id or 'default'}}

        # graph.ainvoke returns the final state as a dict-like mapping
        # (channel name -> value) for a pydantic state schema.
        result = await graph.ainvoke(graph_input, config=config)

        if isinstance(result, GraphState):
            messages = result.messages
        else:
            messages = result.get('messages', [])

        if messages:
            final_message = messages[-1]
            return str(getattr(final_message, 'content', final_message))

        return 'The orchestrator did not produce a response.'

class OrchestratorExecutor(AgentExecutor):
    """A2A executor for the orchestrator"""
    
    def __init__(self) -> None:
        self.agent = Orchestrator()

    # Implement the execute method required by the AgentExecutor base class
    async def execute(
            self,
            context: RequestContext,
            event_queue: EventQueue,
            ) -> None:

        # 1. Reuse the current task or create one for a new request
        if context.current_task:
            task = context.current_task
        elif context.message is not None:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)
        else:
            raise ValueError('No message to process and no current task to resume.')


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


        # 3. Extract the user's text and pass it to the orchestrator graph
        query = get_message_text(context.message) if context.message is not None else ''
        if query:
            result = await self.agent.invoke(
                user_request=query,
                context_id=task.context_id,
            )
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