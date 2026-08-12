from typing import Any

from a2a.types import AgentCard
from langchain_core.prompts import PromptTemplate

from agents.orchestrator.llm import Llm
from agents.state import GraphState, Task

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
2. DELEGATE: Emit one task for each distinct, unhandled need in the request, setting "assigned_agent" to the matching agent key from the Agent Card.
   One request may need several agents, and may need several tasks for the same agent (for example one task per location).
---
You must respond strictly in JSON format. Return only task. Here is the form:
                                         
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
    def __init__(self, llm: Llm, agent_cards: dict[str, AgentCard]):
        self.llm = llm
        self.agent_cards = agent_cards


    #converts agent_card to string
    def card_to_string(self):
        cards = []
        for agent_key, card in self.agent_cards.items():
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
    def tasks_to_string(self, task: Task):
        task_dict = {
            'id': task.id,
            'query': task.query,
            'status': task.status,
            'assigned_agent': task.assigned_agent,
            'result': task.result
        }

        return str(task_dict)


    #function that executes prompt
    def invoke(self, state: GraphState,car_data: Any) -> dict:
        agent_card = self.card_to_string()

        inputs={
            "USER_INPUT": state.user_input.content,                  
            "CONVERSATION_STORY": state.messages,
            "CAR_DATA": car_data, #todo 
            "ACTIVE_TASKS": "\n".join([self.tasks_to_string(task) for task in state.tasks]),
            "AGENT_CARD": agent_card                
        }
        return self.llm(question_prompt,inputs,True)
        