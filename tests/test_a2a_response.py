from a2a.types import (
    Artifact,
    Message,
    Part,
    StreamResponse,
    Task,
    TaskState,
    TaskStatus,
)

from utils.a2a_response import extract_artifact_text


def test_reads_text_from_a_message_response() -> None:
    chunk = StreamResponse(
        message=Message(parts=[Part(text='Three days in Rome')])
    )

    assert extract_artifact_text(chunk) == 'Three days in Rome'


def test_joins_every_text_part_of_a_message() -> None:
    chunk = StreamResponse(
        message=Message(parts=[Part(text='Day one'), Part(text='Day two')])
    )

    assert extract_artifact_text(chunk) == 'Day one\nDay two'


def test_reads_text_from_task_artifacts() -> None:
    chunk = StreamResponse(
        task=Task(
            status=TaskStatus(state=TaskState.TASK_STATE_COMPLETED),
            artifacts=[Artifact(parts=[Part(text='Nearest parking: Long Street 5')])]
        )
    )

    assert extract_artifact_text(chunk) == 'Nearest parking: Long Street 5'


def test_reports_the_status_message_of_a_failed_task() -> None:
    chunk = StreamResponse(
        task=Task(
            status=TaskStatus(
                state=TaskState.TASK_STATE_FAILED,
                message=Message(parts=[Part(text='Upstream API is down')])
            )
        )
    )

    assert extract_artifact_text(chunk) == 'SYSTEM ERROR: Upstream API is down'


def test_reads_a_task_passed_without_its_wrapper() -> None:
    task = Task(artifacts=[Artifact(parts=[Part(text='Sunny, 21 degrees')])])

    assert extract_artifact_text(task) == 'Sunny, 21 degrees'


def test_returns_empty_text_for_a_response_without_text_parts() -> None:
    chunk = StreamResponse(
        task=Task(artifacts=[Artifact(parts=[Part(url='https://example.com/map.png')])])
    )

    assert extract_artifact_text(chunk) == ''


def test_an_empty_message_does_not_fall_through_to_the_task_branch() -> None:
    # An unset protobuf task still reads as an empty Task, so a message
    # response must be recognised as such rather than silently dropped.
    chunk = StreamResponse(message=Message())

    assert extract_artifact_text(chunk) == ''
