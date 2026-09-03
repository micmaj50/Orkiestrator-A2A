from typing import Any

from langchain_core.prompts import PromptTemplate
from agents.orchestrator.llm import Llm
from agents.state import GraphState,Task
from a2a.types import AgentCard
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

question_prompt = PromptTemplate.from_template("""You are the Orchestrator running in a LangGraph workflow. Your job is to analyze user requests, manage the multi-agent execution state, and delegate tasks using the A2A (Agent2Agent) protocol.

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

---
[ORCHESTRATION PROTOCOL]
Review the current user input against the conversation history and active tasks to determine your next action:

1. EVALUATE: Is there an active task in progress? Check the status in active tasks.
2. DELEGATE: If the user requires something from the available sub-agents (Gas Station, Food, Parking, Weather), generate a new task payload.
3. STATUS EVALUATION:
   - Set status to "in_progress" if the task has sufficient context to be executed directly by the sub-agent.
   - Set status to "context" ONLY if crucial information is missing (e.g., location, specific mandatory parameters).

You must respond strictly in JSON format matching this schema:

{{
    "tasks": [
        {{
            "id": 1,
            "query": "string description of what sub-agent should do",
            "status": "in_progress",
            "assigned_agent": "string (matching sub-agent key)",
            "result": null,
            "parameters": null
        }}
    ]
}}
""")




class Delegator:
    def __init__(self, Llm: Llm, AgentCard: AgentCard):
        self.Llm = Llm
        self.AgentCard = AgentCard



    
    #converts Task to string
    def tasksToString(self,task: Task):
        taskDict = {
            'id': task.id,
            'query': task.query,
            'status': task.status,
            'assigned_agent': task.assigned_agent,
            'result': task.result
        }

        return str(taskDict)


    #function that executes prompt
    def invoke(self, state: GraphState,carData: Any) -> dict:
      # agentCard = self.cardToString()

        inputs={
            "USER_INPUT": state.user_input.content,                  
            "CONVERSATION_STORY": state.messages,
            "CAR_DATA": carData, #todo 
            "ACTIVE_TASKS": "\n".join([self.tasksToString(task) for task in state.tasks]),
      #      "AGENT_CARD": agentCard                
        }
        return self.Llm(question_prompt,inputs,True)

