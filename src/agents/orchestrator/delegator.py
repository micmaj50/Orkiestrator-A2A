from typing import Any

from a2a.types import AgentCard
from langchain_core.messages import get_buffer_string
from langchain_core.prompts import PromptTemplate

from agents.orchestrator.llm import Llm
from agents.state import GraphState, WorkItem


question_prompt = PromptTemplate.from_template("""

You are the  Orchestrator running in a LangGraph workflow. Your job is to analyze user requests, manage the multi-agent execution state, and delegate tasks using the A2A (Agent2Agent) protocol.



---
The current session metrics and history extracted from the graph state:

* Active User Input:
"{USER_INPUT}"

* Conversation History (Chronological):
{CONVERSATION_STORY}

* Active Tasks
{ACTIVE_TASKS}

* Current Car Data:
{CAR_DATA}

* Feedback from the previous task division attempt:
{DIVISION_FEEDBACK}

If feedback is provided, create a corrected task division. Do not repeat the same problems.


---
[ORCHESTRATION PROTOCOL]
Review the current user input against the conversation history and active tasks to determine your next action:

1. EVALUATE: Is there an active task in progress (e.g., waiting for food preparation or fuel status)? Check the status in active tasks.
2. DECOMPOSE: Generate one task for every distinct, unhandled need in the request. Agent selection is handled by a separate semantic router.
3. RESOLVE CONTEXT: When generating task queries, resolve ALL contextual references (e.g., "there", "that place", "it") using the conversation history.
Sub-agents have NO access to conversation history, so each query MUST be fully self-contained and explicit.
For example, if the user previously asked about Warsaw and now asks "What about gas stations there?", the query must be "gas stations in Warsaw", NOT "gas stations there".
---
You must respond strictly in JSON format. Return only task. Here is the form:

{{
    "tasks":[
    {{
        "id": "int",
        "query": "A fully self-contained query with all references resolved from conversation history",
        "status": "in_progress",
        "assigned_agent": null,
        "result": null,
        "parameters": null
    }}
    ]
}}


""")




class Delegator:
    def __init__(self, Llm: Llm):
        self.Llm = Llm


    #converts Task to string
    def tasksToString(self,task: WorkItem):
        taskDict = {
            'id': task.id,
            'query': task.query,
            'status': task.status,
            'assigned_agent': task.assigned_agent,
            'result': task.result
        }

        return str(taskDict)


    #function that executes prompt
    def invoke(self, state: GraphState, carData: Any, division_feedback: str | None = None) -> dict:
      # agentCard = self.cardToString()

        inputs={
            "USER_INPUT": state.user_input.content,
            "CONVERSATION_STORY": get_buffer_string(state.messages[-10:]),
            "CAR_DATA": carData, #todo
            "ACTIVE_TASKS": "\n".join([self.tasksToString(task) for task in state.tasks]),
            "DIVISION_FEEDBACK": division_feedback or "No previous attempt. Create the initial task division."
        }

        return self.Llm(
            prompt=question_prompt,
            inputs=inputs,
            asJSON=True,
            observation_name="routing_planning"
        )
