import os
import subprocess
import sys
import time
import httpx

def wait_for_server(port: int, agent_path: str = "", timeout: int = 60) -> None:
    url = f"http://127.0.0.1:{port}{agent_path}/.well-known/agent-card.json"

    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=1, follow_redirects=True)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            pass

    raise AssertionError(f"Server did not start within {timeout}s: {url}")


def test_standalone_mode_smoke():
    # force MOCK_MODE, standalone architecture and UTF-8 encoding for Windows compatibility
    test_env = {
        **os.environ,
        "MOCK_MODE": "true",
        "SINGLE_APP_MODE": "false",
        "PYTHONUTF8": "1"
    }

    processes = []
    agent_modules = [
        "agents.gas_agent",
        "agents.food_agent",
        "agents.parking_agent",
        "agents.weather_agent",
        "agents.orchestrator",
    ]
    test_cases = [
        ("find the closest gas stations near me", "Sample Station"),
        ("find pizza restaurants near me", "Demo Pizza"),
        ("find parking near me", "Test Parking"),
        ("what is the weather today?", "cloudy")
    ]
    
    try:
        for module in agent_modules:
            proc = subprocess.Popen(
                [sys.executable, "-m", module],
                env=test_env,
            )
            processes.append(proc)

        for port in [9999, 9998, 9997, 9996, 9995]:
            wait_for_server(port)

        for query, expected_keyword in test_cases:
            result = subprocess.run(
                [sys.executable, "src/utils/test_client.py"],
                input=f"{query}\n",
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=90,
                env=test_env,
            )

            assert result.returncode == 0, (
                f"Test client failed for query '{query}':\n{result.stderr}"
            )
            assert expected_keyword.lower() in result.stdout.lower(), (
                f"Expected '{expected_keyword}' in response for '{query}', got:\n{result.stdout}"
            )

    finally:
        for process in reversed(processes):
            process.terminate()

        for process in reversed(processes):
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()


def test_single_app_smoke():
    # force MOCK_MODE=true and SINGLE_APP_MODE=true for unified server testing
    test_env = {
        **os.environ,
        "MOCK_MODE": "true",
        "SINGLE_APP_MODE": "true",
        "PYTHONUTF8": "1",
    }

    test_cases = [
        ("find the closest gas stations near me", "Sample Station"),
        ("find pizza restaurants near me", "Demo Pizza"),
        ("find parking near me", "Test Parking"),
        ("what is the weather today?", "cloudy")
    ]

    server_proc = subprocess.Popen(
        [sys.executable, "-m", "src.server.main"],
        env=test_env,
    )

    try:
        wait_for_server(8000, "/orchestrator")

        for query, expected_keyword in test_cases:
            result = subprocess.run(
                [sys.executable, "src/utils/test_client.py"],
                input=f"{query}\n",
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=90,
                env=test_env,
            )

            assert result.returncode == 0, (
                f"Single app test client failed for query '{query}':\n{result.stderr}"
            )
            assert expected_keyword.lower() in result.stdout.lower(), (
                f"Expected '{expected_keyword}' in single app response for '{query}', got:\n{result.stdout}"
            )

    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_proc.kill()
