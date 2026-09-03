from typing import Any
from langchain_core.messages import HumanMessage

from agents.orchestrator.task_division_verifier import TaskDivisionVerifier, TaskDivision
from agents.state import GraphState


def candidate(*queries: str) -> TaskDivision:
    return {
        "tasks": [
            {
                "id": index,
                "query": query
            }
            for index, query in enumerate(queries, start=1)
        ]
    }


CANDIDATE_A = candidate(
    "Find gas stations in Warsaw"
)

CANDIDATE_B = candidate(
    "Find gas stations in Warsaw.",
    "Check the weather in Warsaw"
)


class FakeDelegator:
    def __init__(self, candidates: list[object]):
        self.candidates = candidates
        self.feedbacks: list[str | None] = []

    def invoke(
            self,
            state: GraphState,
            car_data: Any,
            division_feedback: str | None = None
    ) -> object:
        self.feedbacks.append(division_feedback)
        index = len(self.feedbacks) - 1

        if index >= len(self.candidates):
            raise AssertionError(
                "Delegator was called more than expected."
            )

        return self.candidates[index]


class FakeLlm:
    def __init__(self, responses: list[dict[str, Any]]):
        self.responses = responses
        self.calls = 0

    def __call__(
        self,
        prompt,
        inputs: dict[str, Any],
        asJSON: bool,
        observation_name: str
    ) -> dict[str, Any]:
        prompt.invoke(inputs)

        self.calls += 1

        if not self.responses:
            raise AssertionError("LLM was called more than expected.")

        return self.responses.pop(0)


def create_state() -> GraphState:
    return GraphState(
        user_input=HumanMessage(
            content=(
                "Find gas stations and check the weather in Warsaw."
            )
        )
    )


def create_verifier(
        candidates: list[object],
        responses: list[dict[str, Any]]
) -> tuple[TaskDivisionVerifier, FakeDelegator, FakeLlm]:
    delegator = FakeDelegator(candidates)
    llm = FakeLlm(responses)

    verifier = TaskDivisionVerifier(
        delegator=delegator, # type: ignore[arg-type]
        llm=llm # type: ignore[arg-type]
    )

    return verifier, delegator, llm


def test_returns_first_candidate_when_valid():
    verifier, delegator, llm = create_verifier(
        candidates=[CANDIDATE_A],
        responses=[
            {
                "valid": True,
                "issues": [],
                "feedback": ""
            }
        ]
    )

    result = verifier.invoke(create_state(), car_data=None)

    assert result == CANDIDATE_A
    assert len(delegator.feedbacks) == 1
    assert llm.calls == 1


def test_creates_second_candidate_when_first_is_rejected():
    feedback = "Add a separate task for checking the weather."

    verifier, delegator, llm = create_verifier(
        candidates=[CANDIDATE_A, CANDIDATE_B],
        responses=[
            {
                "valid": False,
                "issues": ["The weather task is missing."],
                "feedback": feedback
            },
            {
                "selected_candidate": 2,
                "reason": "Candidate 2 covers the complete request."
            }
        ]
    )

    result = verifier.invoke(create_state(), car_data=None)

    assert result == CANDIDATE_B
    assert delegator.feedbacks == [None, feedback]
    assert llm.calls == 2


def test_selector_can_choose_first_candidate():
    verifier, delegator, _ = create_verifier(
        candidates=[CANDIDATE_A, CANDIDATE_B],
        responses=[
            {
                "valid": False,
                "issues": ["Consider another division."],
                "feedback": "Create another division."
            },
            {
                "selected_candidate": 1,
                "reason": "Candidate 1 is more appropriate."
            }
        ]
    )

    result = verifier.invoke(create_state(), car_data=None)

    assert result == CANDIDATE_A
    assert len(delegator.feedbacks) == 2


def test_returns_empty_tasks_when_selector_rejects_both_candidates():
    verifier, _, _ =create_verifier(
        candidates=[CANDIDATE_A, CANDIDATE_B],
        responses=[
            {
                "valid": False,
                "issues": ["The first candidate is incomplete"],
                "feedback": "Create a complete task division."
            },
            {
                "selected_candidate": None,
                "reason": "Neither candidate is acceptable."
            }
        ]
    )

    result = verifier.invoke(create_state(), car_data=None)

    assert result == {"tasks": []}


def test_does_not_create_more_than_two_candidates():
    invalid_candidate = candidate("   ")
    unused_third_candidate = candidate(
        "This candidate should never be generated."
    )

    verifier, delegator, _ = create_verifier(
        candidates=[
            CANDIDATE_A,
            invalid_candidate,
            unused_third_candidate
        ],
        responses=[
            {
                "valid": False,
                "issues": ["Create another division."],
                "feedback": "Create another division."
            }
        ]
    )

    result = verifier.invoke(create_state(), car_data=None)

    assert result == CANDIDATE_A
    assert len(delegator.feedbacks) == 2


def test_invalid_verifier_responses_keep_existing_behavior():
    verifier, delegator, _ = create_verifier(
        candidates=[CANDIDATE_A],
        responses=[
            {
                "unexpected_field": "invalid response"
            }
        ]
    )

    result = verifier.invoke(create_state(), car_data=None)

    assert result == CANDIDATE_A
    assert len(delegator.feedbacks) == 1


def test_returns_second_candidate_when_first_has_invalid_structure():
    verifier, delegator, llm = create_verifier(
        candidates=[
            "not a task division",
            CANDIDATE_B
        ],
        responses=[]
    )

    result = verifier.invoke(create_state(), car_data=None)

    assert result == CANDIDATE_B
    assert len(delegator.feedbacks) == 2
    assert delegator.feedbacks[0] is None
    assert delegator.feedbacks[1] is not None
    assert llm.calls == 0