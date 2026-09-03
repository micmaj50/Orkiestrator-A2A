import json

from pydantic import Field
from langchain_core.prompts import PromptTemplate

from context.agent_context import AgentContext
from context.car import CarContext
from context.context_selection import ContextSelection
from context.context_groups import CONTEXT_GROUPS
from agents.orchestrator.llm import Llm


class AgentRequest:
    """Class used for determaining the needed context"""

    """
    `user_query` preserves the original input.
    """
    prompt: PromptTemplate = PromptTemplate.from_template("""
    You are providing information about car status and metrics fro context groups.
    Your role is to select a given number of context groups from a given list.
    Select based on 'description' which group/groups could be the most useful to complite given task.

    Task:
    {TASK}

    Context group list:
    {CONTEXT_GROUPS}

    Number of groups to select:
    {NUM_OF_GROUPS}
    ------------
    You must respond strictly in string list format. Return only a list of "id" of selected group/groups.
    If it is needed for the task, prioritise car's location.

    """)
    def __init__(
        self,
        user_input: str,
        task: str,
        context: AgentContext | None = None,
        number_of_groups: int = 2
        ):
        self.user_input = user_input
        self.task = task
        self.context = context
        self.number_of_groups = number_of_groups

    def select_context(self, car_context: CarContext, llm: Llm) -> AgentContext:
        """Resturns selected context for given task"""
        groups = [{"id": group.id, "description": group.description} for group in CONTEXT_GROUPS]

        inputs ={
            "TASK" : self.task,
            "CONTEXT_GROUPS" : json.dumps(groups, indent=2),
            "NUM_OF_GROUPS" : self.number_of_groups
        }

        selected_ids = llm(prompt=self.prompt, inputs=inputs, asJSON=True)
        selected_context = [obj for obj in CONTEXT_GROUPS if obj.id in selected_ids]

        selection = ContextSelection.from_groups(selected_context=selected_context)

        self.context = AgentContext.select_from_car_context(car_context=car_context, selection=selection)
        return self.context
