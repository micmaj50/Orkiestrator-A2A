import json
from typing import Any, TypeGuard
from langchain_core.prompts import PromptTemplate

from agents.orchestrator.delegator import Delegator
from agents.orchestrator.llm import Llm
from agents.state import GraphState


TaskDivision = dict[str, Any]

verification_prompt = PromptTemplate.from_template(
    """
You verify whether a user request was divided into sensible tasks.

USER REQUEST:
{USER_INPUT}

CONVERSATION HISTORY:
{CONVERSATION_HISTORY}

CAR DATA:
{CAR_DATA}

PROPOSED TASK DIVISION:
{CANDIDATE}

Check whether:
1. Every distinct part of the user request is covered.
2. No unrelated or invented tasks were added.
3. Tasks do not unnecessarily overlap or duplicate each other.
4. Every task has a clear and self-contained query.
5. Important constraints, such as location, are preserved.
6. A simple request was not divided into too many tasks.
7. Different user needs are separated when appropriate.

Do not evaluate assigned agents. Agent selection is performed later.

Return only JSON in the following format:

{{
    "valid": false,
    "issues": [
        "Description of the problem"
    ],
    "feedback": "Clear instruction for creating a better task division"
}}
"""
)


selection_prompt = PromptTemplate.from_template(
    """
You compare two possible task divisions for the same user request.

USER REQUEST:
{USER_INPUT}

CONVERSATION HISTORY:
{CONVERSATION_HISTORY}

CAR DATA:
{CAR_DATA}

CANDIDATE 1:
{CANDIDATE_1}

CANDIDATE 2:
{CANDIDATE_2}

Choose the candidate that:
1. Covers every distinct part of the user request.
2. Does not add unrelated or invented tasks.
3. Does not contain duplicated or unnecessarily overlapping tasks.
4. Contains clear and self-contained task queries.
5. Preserves important constraints, such as location.
6. Uses an appropriate level of task division.

Do not evaluate assigned agents. Agent selection is performed later.

If candidate 1 is better, set "selected_candidate" to 1.
If candidate 2 is better, set "selected_candidate" to 2.
If neither candidate is acceptable, set "selected_candidate" to null.

Return only JSON in the following format:

{{
    "selected_candidate": 2,
    "reason": "Candidate 2 covers the whole request without duplicated tasks."
}}
"""
)


def has_valid_structure(candidate: object) -> TypeGuard[TaskDivision]:
    """Check the basic structure without using LLM."""

    if not isinstance(candidate, dict):
        return False

    tasks = candidate.get("tasks")

    if not isinstance(tasks, list) or not tasks:
        return False

    for task in tasks:
        if not isinstance(task, dict):
            return False

        query = task.get("query")

        if not isinstance(query, str) or not query.strip():
            return False

    return True


def serialize_candidate(candidate: object) -> str:
    """Convert a candidate into readable JSON for the prompt."""

    return json.dumps(
        candidate,
        ensure_ascii=False,
        indent=2,
        default=str
    )


def serialize_conversation(state: GraphState) -> str:
    """Convert the conversation history into readable text."""

    if not state.messages:
        return "No previous conversation."

    return "\n".join(f"{type(message).__name__}: {message.content}" for message in state.messages)


class TaskDivisionVerifier:
    """Generate and verify at most two task division candidates."""

    def __init__(self, delegator: Delegator, llm: Llm):
        self.delegator = delegator
        self.llm = llm

    def invoke(self, state: GraphState, car_data: Any) -> TaskDivision:
        """
        Generate the first task division and verify it.
        If the first division is rejected, generate one corrected division
        and let the LLM choose between the two candidates.
        """

        candidate_a = self.delegator.invoke(state, car_data)
        candidate_a_has_valid_structure = has_valid_structure(candidate_a)

        if candidate_a_has_valid_structure:
            verification = self._verify(
                state=state,
                candidate=candidate_a,
                car_data=car_data
            )

            if verification is None:
                return candidate_a

            if verification["valid"]:
                return candidate_a

            feedback = verification["feedback"]
        else:
            feedback = (
                "The previous response did not contain a non-empty list "
                "of tasks with clear, non-empty queries. Create a valid "
                "task division."
            )

        try:
            candidate_b = self.delegator.invoke(state, car_data, division_feedback=feedback)
        except Exception:
            if candidate_a_has_valid_structure:
                return candidate_a

            return {"tasks": []}

        if not has_valid_structure(candidate_b):
            if candidate_a_has_valid_structure:
                return candidate_a

            return {"tasks": []}

        if not has_valid_structure(candidate_a):
            return candidate_b

        selection = self._select(
            state=state,
            candidate_a=candidate_a,
            candidate_b=candidate_b,
            car_data=car_data
        )

        if selection is None:
            return candidate_b

        selected_candidate = selection["selected_candidate"]

        if selected_candidate == 1 and candidate_a_has_valid_structure:
            return candidate_a

        if selected_candidate == 2:
            return candidate_b

        return {"tasks": []}
    

    def _verify(
        self,
        state: GraphState,
        candidate: TaskDivision,
        car_data: Any
    ) -> dict[str, Any] | None:
        """Ask the LLM whether one task division is acceptable."""

        inputs = {
            "USER_INPUT": str(state.user_input.content),
            "CONVERSATION_HISTORY": serialize_conversation(state),
            "CAR_DATA": str(car_data),
            "CANDIDATE": serialize_candidate(candidate)
        }

        try:
            result = self.llm(
                prompt=verification_prompt,
                inputs=inputs,
                asJSON=True,
                observation_name="task_division_verification"
            )
        except Exception:
            return None

        if not isinstance(result, dict):
            return None

        valid = result.get("valid")

        if not isinstance(valid, bool):
            return None

        raw_issues = result.get("issues", [])

        if isinstance(raw_issues, list):
            issues = [str(issue) for issue in raw_issues]
        else:
            issues = []

        raw_feedback = result.get("feedback")

        if isinstance(raw_feedback, str) and raw_feedback.strip():
            feedback = raw_feedback.strip()
        elif issues:
            feedback = " ".join(issues)
        else:
            feedback = (
                "Create a corrected task division that fully covers the "
                "user request without duplicated or unrelated tasks."
            )

        return {
            "valid": valid,
            "issues": issues,
            "feedback": feedback
        }

    def _select(
        self, 
        state: GraphState,
        candidate_a: TaskDivision,
        candidate_b: TaskDivision,
        car_data: Any
    ) -> dict[str, Any] | None:
        """Ask the LLM to choose the better candidate."""

        inputs = {
            "USER_INPUT": str(state.user_input.content),
            "CONVERSATION_HISTORY": serialize_conversation(state),
            "CAR_DATA": str(car_data),
            "CANDIDATE_1": serialize_candidate(candidate_a),
            "CANDIDATE_2": serialize_candidate(candidate_b)
        }

        try:
            result = self.llm(
                prompt=selection_prompt,
                inputs=inputs,
                asJSON=True,
                observation_name="task_division_selection"
            )
        except Exception:
            return None

        if not isinstance(result, dict):
            return None

        if "selected_candidate" not in result:
            return None

        selected_candidate = result["selected_candidate"]

        if isinstance(selected_candidate, bool):
            return None

        if selected_candidate not in (1, 2, None):
            return None

        reason = result.get("reason", "")

        if not isinstance(reason, str):
            reason = str(reason)

        return {
            "selected_candidate": selected_candidate,
            "reason": reason
        }
    