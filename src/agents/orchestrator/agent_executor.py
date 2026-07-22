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


class Orchestrator:
    """Orchestrator backed by the LangGraph multi-agent graph.

    Builds the initial graph state from the user's request, runs the graph
    (which delegates to the gas/food sub-agents over A2A and synthesizes a
    reply), and returns the final text answer.
    """

    async def invoke(self, user_request: str, context_id: str | None = None) -> str:
        human_message = HumanMessage(content=user_request)

        # Per-turn input: refresh the active user input and reset the task list,
        # while appending the new user turn to the accumulating `messages` history.
        # A GraphState instance (vs a plain dict) keeps this type-checked; with a
        # checkpointer LangGraph still applies each field through its channel
        # reducer, so `messages` appends and `tasks` is overwritten (reset).
        graph_input = GraphState(
            user_input=human_message,
            messages=[human_message],
            tasks=[],
        )

        # Key the checkpointed conversation memory by the A2A context id so that
        # several messages in the same conversation share history. Without a
        # context id we fall back to a single shared thread.
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
