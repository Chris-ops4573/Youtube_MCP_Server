"""CLI commands: quota status, serve, local-check (UI-4)."""

import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

from ytmcp import cli, config
from ytmcp.cli import PACIFIC, main
from ytmcp.database import Database
from ytmcp.quota import QuotaTracker


def noon(day: str = "2026-11-24", hour: int = 12, minute: int = 0) -> datetime:
    y, m, d = (int(x) for x in day.split("-"))
    return datetime(y, m, d, hour, minute, tzinfo=PACIFIC)


def run_quota(spent: int, clock_time: datetime, tmp_path: Path):
    database = Database(tmp_path / "q.db")
    database.add_spent(clock_time.date().isoformat(), spent)
    lines: list[str] = []
    code = main(
        ["quota", "status"],
        out=lines.append,
        quota_factory=lambda today: QuotaTracker(cache=database, today=today),
        clock=lambda: clock_time,
    )
    return code, "\n".join(lines)


def test_quota_status_shows_used_reserve_left_and_reset_time(tmp_path):
    code, text = run_quota(1234, noon(hour=18, minute=15), tmp_path)
    assert code == 0
    assert "Quota for 2026-11-24 (Pacific time)" in text
    assert "Used: 1234 of 10000 units" in text
    assert "Reserve kept back: 500 units" in text
    assert "Left to use: 8266 units" in text
    assert "Resets in 5 h 45 min" in text
    assert "Only calls made by this server are counted" in text


def test_quota_status_with_nothing_used(tmp_path):
    _, text = run_quota(0, noon(), tmp_path)
    assert "Used: 0 of 10000 units" in text
    assert "Left to use: 9500 units" in text


def test_quota_status_uses_the_pacific_day_not_the_utc_day(tmp_path):
    # 22:00 Pacific on the 24th is already the 25th in UTC; the count must be the 24th's
    _, text = run_quota(77, noon(hour=22), tmp_path)
    assert "Quota for 2026-11-24" in text and "Used: 77 of" in text
    assert "Resets in 2 h 0 min" in text


def test_quota_reset_time_is_right_on_the_day_the_clocks_change(tmp_path):
    # 2026-11-01: clocks go back, so that Pacific day has 25 hours: 00:30 is 24 h 30 min before midnight
    _, text = run_quota(0, datetime(2026, 11, 1, 0, 30, tzinfo=PACIFIC), tmp_path)
    assert "Resets in 24 h 30 min" in text


def test_quota_status_reads_the_real_database_file(tmp_path, monkeypatch):
    monkeypatch.setenv("YTMCP_CACHE_PATH", str(tmp_path / "real.db"))
    Database(tmp_path / "real.db").add_spent("2026-11-24", 40)
    lines: list[str] = []
    assert main(["quota", "status"], out=lines.append, clock=lambda: noon()) == 0
    assert "Used: 40 of 10000 units" in "\n".join(lines)


def test_the_default_clock_is_pacific_time():
    assert cli._pacific_now().tzinfo == PACIFIC


def test_build_quota_tracker_defaults_to_todays_pacific_date(tmp_path, monkeypatch):
    monkeypatch.setenv("YTMCP_CACHE_PATH", str(tmp_path / "x.db"))
    assert config.build_quota_tracker().spent == 0
    assert config.build_quota_tracker(lambda: date(2026, 1, 1)).spent == 0


def test_quota_needs_an_action():
    with pytest.raises(SystemExit):
        main(["quota"])


def test_serve_starts_the_server():
    calls = []
    assert main(["serve"], serve=lambda: calls.append("served") or 0) == 0
    assert calls == ["served"]


def test_serve_default_calls_server_main(monkeypatch):
    from ytmcp import server

    called = []
    monkeypatch.setattr(server, "main", lambda: called.append(True))
    assert main(["serve"]) == 0
    assert called == [True]


def test_local_check_runs_the_script_and_returns_its_exit_code():
    seen = []

    def run(command):
        seen.append(list(command))
        return 3

    assert main(["local-check"], run_command=run) == 3
    assert seen[0][0] == sys.executable
    assert seen[0][1].endswith("scripts/local_check.py")


def test_local_check_without_the_script_is_a_clear_error(tmp_path):
    lines: list[str] = []
    assert cli._run_local_check(lambda c: 0, lines.append, tmp_path) == 1
    assert "Cannot find" in lines[0] and "local_check.py" in lines[0]


def test_the_default_runner_runs_a_command_in_the_project_folder(monkeypatch):
    seen = {}

    def fake_run(command, cwd, check):
        seen.update(command=command, cwd=cwd, check=check)
        return subprocess.CompletedProcess(command, 7)

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert cli._run_subprocess(["x"]) == 7
    assert seen == {"command": ["x"], "cwd": cli.ROOT, "check": False}
