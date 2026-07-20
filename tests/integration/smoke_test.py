from socket import timeout
import subprocess
import sys
import time


def test_gas_request():
    processes = []

    try:
        gas_agent = subprocess.Popen(
            [sys.executable, "-m", "agents.gas_agent"]
        )
        processes.append(gas_agent)

        food_agent = subprocess.Popen(
            [sys.executable, "-m", "agents.food_agent"]
        )
        processes.append(food_agent)

        orchestrator = subprocess.Popen(
            [sys.executable, "-m", "agents.orchestrator"]
        )
        processes.append(orchestrator)

        time.sleep(3)

        result = subprocess.run(
            [sys.executable, "src/utils/test_client.py"],
            input="gas\n",
            text=True,
            capture_output=True,
            timeout=20,
        )

        assert result.returncode == 0
        assert "station a" in result.stdout.lower()

    finally:
        for process in reversed(processes):
            process.terminate()

        for process in reversed(processes):
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
