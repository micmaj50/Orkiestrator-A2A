from .agent_executor import OrchestratorExecutor


def create_executor() -> OrchestratorExecutor:
    """Create the Orchestrator implementation used by shared app factory."""

    return OrchestratorExecutor()