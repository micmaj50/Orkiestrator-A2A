from langchain_core.prompts import PromptTemplate

from agents.state import GraphState
from agents.orchestrator.Llm import Llm

class Synthesizer:
    def __init__(self):
        self.responses: list[str | dict] = []

        self.template_string = """
        You are a synthesis agent. Combine the data from our agents into a simple summary for a human.

        ORIGINAL HUMAN REQUEST:
        {user_request}

        AGENT OUTPUTS:
        {agent_answers}
        """

        self.prompt_template = PromptTemplate(
            input_variables=["user_request", "agent_answers"],
            template=self.template_string
        )

    def __call__(self, state: GraphState, llm: Llm, _asJSON=False):
        if isinstance(state.user_input.content, str):
            request = state.user_input.content
        else:
            request = str(state.user_input.content)

        # Combine only the current turn's sub-agent results (kept on the tasks)
        # rather than the whole `messages` history, which now spans past turns.
        answers = "\n\n".join(
            f"{task.assigned_agent or 'agent'}: {task.result}"
            for task in state.tasks
            if task.result
        )

        final_response = llm(
            prompt=self.prompt_template,
            inputs={
                "user_request": request,
                "agent_answers": answers,
            },
            asJSON=_asJSON
        )

        self.responses.append(final_response)

        return final_response