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

class FoodPointAgent:
    """Mock sub-agent that returns closest food-points"""

    async def invoke(self, user_request: str) -> str:
        # Mock data
        return 'restaurant A, station B'


class FoodPointAgentExecutor(AgentExecutor):
    """A2A executor for the mock food-point sub-agent"""

    def __init__(self) -> None:
        self.agent = FoodPointAgent()

    # Implement the execute method required by the AgentExecutor base class
    async def execute(
        self,
        context: RequestContext,
        event_queue = EventQueue,
        ) -> None:

        # 1. Reuse the current task or create one for a new request
        if context.current_task:
            task = context.current_task
        else:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)


        # 2. Mark the task as working in EventQueue before invoking the sub-agent logic
        task_updater = TaskUpdater(
            event_queue=event_queue, 
            task_id=task.id, 
            context_id=task.context_id
        )

        await task_updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message('Processing request...'),
        )

        # 3. Extract the request text forwarded by the orchestrator and invoke the mock agent
        query = get_message_text(context.message)
        if query:
            result = await self.agent.invoke(user_request=query)
        else:
            result = 'No text input is provided!'

        # 4. Add the agent response as a task artifact to EventQueue
        await task_updater.add_artifact(
                parts=[
                    new_text_part(
                        text=result, 
                        media_type='text/plain'
                        )
                    ]
                )
        print('FoodPointAgent result: ', result)

        # 5. Mark the task as completed
        await task_updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message('Food point request is completed!'),
        )


    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Raise exception as cancel is not supported."""
        raise NotImplementedError('Cancel is not supported.')
