from typing import Any

from agents.orchestrator.Llm import Llm
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import get_buffer_string
from agents.state import GraphState,Task
from a2a.types import AgentCard
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

question_prompt = PromptTemplate.from_template("""

You are the  Orchestrator running in a LangGraph workflow. Your job is to analyze user requests, manage the multi-agent execution state, and delegate tasks using the A2A (Agent2Agent) protocol.

---
This is your Agent Card:

{AGENT_CARD}

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

1. EVALUATE: Is there an active task in progress (e.g., waiting for food preparation or fuel status)? Check the status in active tasks.
2. DELEGATE: If the user requires something from the Gas Station (EV/Fuel status) or Food Point (menu/ordering) that is not yet handled, generate a new task payload.
---
You must respond strictly in JSON format. Return only task. Here is he form:
                                         
{{ 
    "tasks":[                                            
    {{
        "id": "int",
        "query": "string",
        "status": "in_progress",
        "assigned_agent": (choose one agent from AgentCard),
        "result": null,
        "parameters": null
    }}
    ]
}}
                                                

""")




class Delegator:
    def __init__(self, Llm: Llm, AgentCards: dict[str, AgentCard]):
        self.Llm = Llm
        self.AgentCards = AgentCards


      #converts agentCard to string
    def cardToString(self):
        cards = []
        for agent_key, card in self.AgentCards.items():
            card_dict = {
                "assigned_agent": agent_key,
                "name": card.name,
                "description": card.description,
                "version": card.version,
                "skills": card.skills,
            }
            cards.append(card_dict)
        return str(cards)
    
    #converts Task to string
    def tasksToString(self, task: Task):
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
        agentCard = self.cardToString()

        inputs={
            "USER_INPUT": state.user_input.content,
            "CONVERSATION_STORY": get_buffer_string(state.messages) if state.messages else "(no prior conversation)",
            "CAR_DATA": carData, #todo 
            "ACTIVE_TASKS": "\n".join([self.tasksToString(task) for task in state.tasks]),
            "AGENT_CARD": agentCard                
        }
        return self.Llm(question_prompt,inputs,True)
        
