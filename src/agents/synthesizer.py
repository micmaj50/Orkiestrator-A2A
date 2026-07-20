from langchain_core.prompts import PromptTemplate
from langchain_core.messages import get_buffer_string
from typing import cast

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

    def __call__(self, state: GraphState, llm: Llm, _asJSON=True):
        if isinstance(state.user_input.content, str):
            request = state.user_input.content
        else:
            request = str(state.user_input.content)

        answers = get_buffer_string(state.messages)

        prompt = self.prompt_template.partial(
            user_request=request,
            agent_answers=answers
        )
        ready_prompt = cast(PromptTemplate, prompt)

        final_response = llm(prompt=ready_prompt, asJSON=_asJSON)

        self.responses.append(final_response)

        return final_response