from langchain_core.messages import get_buffer_string
from langchain_core.prompts import PromptTemplate

from agents.orchestrator.llm import Llm
from agents.state import GraphState


class Synthesizer:
    def __init__(self):
        self.responses: list[str | dict] = []

        self.template_string = """
        You are a synthesis agent. Combine the data from our agents into a simple summary for a human.
        Use the conversation history to understand context (e.g., what "there" or "that place" refers to).

        Each output is tagged with what it is worth: [completed] is an answer,
        [need_context] means the agent needs something from the driver, and
        [failed] means that part could not be handled - say so plainly, and
        never present it as an answer.

        {system_warning}

        CONVERSATION HISTORY:
        {conversation_history}

        CURRENT USER REQUEST:
        {user_request}

        AGENT OUTPUTS:
        {agent_answers}
        """

        self.prompt_template = PromptTemplate(
            input_variables=["conversation_history", "user_request", "agent_answers", "system_warning"],
            template=self.template_string
        )

    def __call__(self, state: GraphState, llm: Llm, _asJSON=False):
        if isinstance(state.user_input.content, str):
            request = state.user_input.content
        else:
            request = str(state.user_input.content)

        answers = "\n".join(
            f"Result from {task.assigned_agent} [{task.status.value}]: {task.result}"
            for task in state.tasks if task.result
        )

        conversation_history = get_buffer_string(state.messages[-10:])

        warning_text = ""
        if state.tasks_dropped:
            warning_text = "SYSTEM INSTRUCTION: Some tasks were dropped because the request exceeded the allowed complexity limits. You MUST explicitly state in your final answer that some parts of the user's request were skipped due to system limits."

        final_response = llm(
            prompt=self.prompt_template,
            inputs={
                "conversation_history": conversation_history,
                "user_request": request,
                "agent_answers": answers,
                "system_warning": warning_text,
            },
            asJSON=_asJSON,
            observation_name="response_synthesis"
        )

        self.responses.append(final_response)

        return final_response
