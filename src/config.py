import os
from urllib.parse import urlsplit
from dotenv import load_dotenv
from agents.registry import get_agent_definition


load_dotenv()


SINGLE_APP_MODE = os.getenv("SINGLE_APP_MODE", "false").lower() == "true"
MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
A2A_BIND_HOST = os.getenv("A2A_BIND_HOST", "127.0.0.1")


def get_agent_host(agent_name: str) -> str:
    agent = get_agent_definition(agent_name)
    default_host = urlsplit(agent.default_url).hostname or "127.0.0.1"

    return os.getenv(f"{agent.env_prefix}_HOST", default_host)


def get_agent_port(agent_name: str) -> int:
    agent = get_agent_definition(agent_name)
    parsed_url = urlsplit(agent.default_url)
    default_port = parsed_url.port

    return int(os.getenv(f"{agent.env_prefix}_PORT", str(default_port)))


def get_agent_url(agent_name: str) -> str:
    agent = get_agent_definition(agent_name)

    if SINGLE_APP_MODE:
        return f"http://{SERVER_HOST}:{SERVER_PORT}{agent.mount_path}/"

    parsed_url = urlsplit(agent.default_url)
    host = get_agent_host(agent_name)
    port = get_agent_port(agent_name)
    path = parsed_url.path.rstrip("/")

    return f"{parsed_url.scheme}://{host}:{port}{path}"

# Execution time limits.
# They exist to prevent a single request from hanging indefinitely.

DEFAULT_LLM_TIMEOUT_SECONDS = 30.0
DEFAULT_LLM_MAX_RETRIES = 1
DEFAULT_EXTERNAL_API_TIMEOUT_SECONDS = 15.0
DEFAULT_SUB_AGENT_TIMEOUT_SECONDS = 90.0

# How long we wait for one answer from the language model before giving up
def get_llm_timeout_seconds() -> float:
    return float(
            os.getenv("LLM_TIMEOUT_SECONDS", str(DEFAULT_LLM_TIMEOUT_SECONDS))
    )


# How many extra attempts a failed model call gets
def get_llm_max_retries() -> int:
    return int(
            os.getenv("LLM_MAX_RETRIES", str(DEFAULT_LLM_MAX_RETRIES))
    )


# How long we wait for external API to respond
def get_external_api_timeout_seconds() -> float:
    return float(
            os.getenv("EXTERNAL_API_TIMEOUT_SECONDS", str(DEFAULT_EXTERNAL_API_TIMEOUT_SECONDS))
    )


# How long the orchestrator waits for one sub-agent to answer.
# A sub-agent calls the model and then an external API, so this has to cover both.
def get_sub_agent_timeout_seconds() -> float:
    return float(
            os.getenv("SUB_AGENT_TIMEOUT_SECONDS", str(DEFAULT_SUB_AGENT_TIMEOUT_SECONDS))
    )


# How long one whole user request may take, from the question to the final answer.
#
# This is the outermost cap, so it has to leave room for every sub-agent to hit
# its own timeout first. Firing before them kills the whole run and throws away
# the answers that did come back, which is worse than letting one slow sub-agent
# fail on its own. Tasks run one after another, so their budgets add up, and the
# extra slot covers the planning and synthesis the orchestrator does around them.
def get_request_timeout_seconds() -> float:
    default = (get_max_tasks() + 1) * get_sub_agent_timeout_seconds()

    return float(
            os.getenv("REQUEST_TIMEOUT_SECONDS", str(default))
    )



# Loop limits.
# These limits stop the graph from taking too many steps.

DEFAULT_MAX_TASKS = 5

# Tasks now run one after another, so each one takes two steps: the agent node and the return to the orchestrator.
GRAPH_STEPS_PER_TASK = 2

# The overhead is the first delegation and the final synthesis.
GRAPH_STEPS_OVERHEAD = 2

# Five steps so that adding a node to the graph later does not start rejecting valid runs.
# Add one step of slack because LangGraph stops when the count reaches the limit rather than passing it.
GRAPH_STEPS_SLACK = 6


# How many sub-agent calls one question may fan out into.
# Tasks beyond the limit are dropped.
def get_max_tasks() -> int:
    return int(
            os.getenv("MAX_TASKS", str(DEFAULT_MAX_TASKS))
    )


# How many steps the graph may take before LangGraph stops it.

# This assumes tasks run one after another.
# Running them in parallel would collapse the cost to a constant,
# so revisit this if the graph ever fans out.
def get_graph_recursion_limit() -> int:
    return (
            GRAPH_STEPS_PER_TASK * get_max_tasks()
            + GRAPH_STEPS_OVERHEAD
            + GRAPH_STEPS_SLACK
    )



# Routing limits.

# Cosine similarity below which the nearest skill is not a real match.
#
# The vector search always returns its closest hit, however far away it is, so
# without a floor a request no agent covers is answered by whichever agent
# happened to be nearest. The right value depends on the embeddings and on what
# the agent cards say, so this is a starting point to calibrate, not a measured
# one.
DEFAULT_MIN_SKILL_SCORE = 0.5


def get_min_skill_score() -> float:
    return float(
            os.getenv("MIN_SKILL_SCORE", str(DEFAULT_MIN_SKILL_SCORE))
    )



# Budget limits.
# These limits bounds how much the model is allowed to write.

DEFAULT_LLM_MAX_OUTPUT_TOKENS = 1000


def get_llm_max_output_tokens() -> int:
    return int(
            os.getenv("LLM_MAX_OUTPUT_TOKENS", str(DEFAULT_LLM_MAX_OUTPUT_TOKENS))
    )
