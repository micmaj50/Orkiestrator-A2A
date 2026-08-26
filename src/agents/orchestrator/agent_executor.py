from langchain_core.messages import HumanMessage
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
from langfuse import observe, get_client

from agents.graph import graph
from agents.state import GraphState


class Orchestrator:
    """Orchestrator backed by the LangGraph multi-agent graph."""

    @observe(
            name="orchestrator_invoke",
            capture_input=False,
            capture_output=False
    )
    async def invoke(self, user_request: str) -> str:
        state = GraphState(user_input=HumanMessage(content=user_request))

        # graph.ainvoke returns the final state as a dict-like mapping
        # (channel name -> value) for a pydantic state schema.
        result = await graph.ainvoke(state)

        if isinstance(result, GraphState):
            messages = result.messages
        else:
            messages = result.get('messages', [])

        if messages:
            final_message = messages[-1]
            return str(getattr(final_message, 'content', final_message))

        return(
                'Unsupported request\n'
                'Try: "find closest gas stations"\n'
                'Or:  "find closest food points"\n'
                'Or:  "find parking nearby"'
                )


class OrchestratorExecutor(AgentExecutor):
    """A2A executor for the orchestrator"""
    
    def __init__(self) -> None:
        self.agent = Orchestrator()

    # Implement the execute method required by the AgentExecutor base class
    @observe(
            name="orchestrator_execute",
            capture_input=False,
            capture_output=False
    )
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


        # 3. Extract the user's text and pass it to the orchestrator graph
        query = get_message_text(context.message)
        langfuse = get_client()
        langfuse.update_current_span(
            input={"user_request": query}
        )
        if query:
            result = await self.agent.invoke(user_request=query)
        else:
            result = 'No text input is provided!'

        langfuse.update_current_span(
            output={"response": result}
        )

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
