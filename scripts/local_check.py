"""Local check (SK-2): build, lint, test, start the server, call one tool.

Run from the repo root:  python scripts/local_check.py
Prints PASS/FAIL for each step and exits 1 if any step fails.
"""

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
# fixture provider: no live API calls or quota (TQ-5)
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "YTMCP_PROVIDER": "fixture"}
FIXTURE_VIDEO_ID = "aaaaaaaaaaa"  # first video in tests/fixtures/videos.json
FIXTURE_CHANNEL = "@rustlab"  # in tests/fixtures/channels.json
SERVER_TIMEOUT_SECONDS = 15


def run(cmd: list[str]) -> tuple[bool, str]:
    result = subprocess.run(
        cmd, check=False, cwd=ROOT, env=ENV, capture_output=True, text=True
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output


def step_build() -> tuple[bool, str]:
    return run([sys.executable, "-c", "import ytmcp.server"])


def step_lint() -> tuple[bool, str]:
    return run([sys.executable, "-m", "ruff", "check", "."])


def step_brain() -> tuple[bool, str]:
    return run([sys.executable, "scripts/brain.py", "check"])


def step_tests() -> tuple[bool, str]:
    return run([sys.executable, "-m", "pytest", "-q", "--cov=src", "--cov-fail-under=80"])


EXPECTED_TOOLS = (
    "find_similar_videos",
    "find_similar_channels",
    "propose_playlist",
    "create_playlist",
    "recommend_videos",
    "analyze_engagement",
)


async def _call_server(database: str) -> str:
    # the child gets its own throwaway database, so the check never touches your real one
    env = {**ENV, "YTMCP_CACHE_PATH": database}
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "ytmcp.server"], env=env, cwd=ROOT
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = [t.name for t in (await session.list_tools()).tools]
        for name in EXPECTED_TOOLS:
            if name not in tools:
                raise RuntimeError(f"{name} not registered, got {tools}")
        result = await session.call_tool("find_similar_videos", {"video": FIXTURE_VIDEO_ID})
        is_error = getattr(result, "is_error", getattr(result, "isError", False))  # mcp 2.x / 1.x
        if is_error or "results" not in str(result.content):
            raise RuntimeError(f"unexpected tool result: {result.content}")
        channels = await session.call_tool("find_similar_channels", {"channel": FIXTURE_CHANNEL})
        if getattr(channels, "is_error", False) or "results" not in str(channels.content):
            raise RuntimeError(f"unexpected channel result: {channels.content}")
        # propose_playlist only plans: it creates nothing. create_playlist is never called here.
        plan = await session.call_tool("propose_playlist", {"topic": "rust", "total_minutes": 25})
        if getattr(plan, "is_error", False) or "proposal_id" not in str(plan.content):
            raise RuntimeError(f"unexpected proposal result: {plan.content}")
        return f"tools: {tools}; the read-only tools returned results"


def step_server() -> tuple[bool, str]:
    try:
        with tempfile.TemporaryDirectory() as folder:
            database = str(Path(folder) / "check.db")
            detail = asyncio.run(asyncio.wait_for(_call_server(database), SERVER_TIMEOUT_SECONDS))
        return True, detail
    except Exception as exc:  # noqa: BLE001 - any failure is reported as FAIL
        while isinstance(exc, ExceptionGroup):  # show the real error, not the group
            exc = exc.exceptions[0]
        return False, f"{type(exc).__name__}: {exc}"


STEPS = [
    ("build", step_build),
    ("lint", step_lint),
    ("brain notes and skills", step_brain),
    ("tests (coverage >= 80%)", step_tests),
    ("server + read-only tools", step_server),
]


def main() -> int:
    failed = False
    for name, step in STEPS:
        ok, output = step()
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            failed = True
            print("      " + output[-2000:].replace("\n", "\n      "))
    print("\nlocal-check:", "FAILED" if failed else "all steps passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
