import os
import subprocess
import sys
import time


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
        ("gas", "orlen"),
        ("food", "kitchen"),
        ("parking", "parking"),
        ("weather", "thundery"),
    ]
    
    try:
        for module in agent_modules:
            proc = subprocess.Popen(
                [sys.executable, "-m", module],
                env=test_env,
            )
            processes.append(proc)

        time.sleep(3)

        for query, expected_keyword in test_cases:
            result = subprocess.run(
                [sys.executable, "src/utils/test_client.py"],
                input=f"{query}\n",
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=15,
                env=test_env,
            )

            assert result.returncode == 0, (
                f"Test client failed for query '{query}':\n{result.stderr}"
            )
            assert expected_keyword in result.stdout.lower(), (
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
        ("gas", "orlen"),
        ("food", "kitchen"),
        ("parking", "parking"),
        ("weather", "thundery"),
    ]

    server_proc = subprocess.Popen(
        [sys.executable, "-m", "src.server.main"],
        env=test_env,
    )

    try:
        time.sleep(3)

        for query, expected_keyword in test_cases:
            result = subprocess.run(
                [sys.executable, "src/utils/test_client.py"],
                input=f"{query}\n",
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=15,
                env=test_env,
            )

            assert result.returncode == 0, (
                f"Single app test client failed for query '{query}':\n{result.stderr}"
            )
            assert expected_keyword in result.stdout.lower(), (
                f"Expected '{expected_keyword}' in single app response for '{query}', got:\n{result.stdout}"
            )

    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            server_proc.kill()
