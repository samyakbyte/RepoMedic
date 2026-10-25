"""Diagnostics: run the project's pytest command and parse JUnit XML."""

import os
import signal
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional

from app.config import MAX_CAPTURE_CHARS, PYTEST_TIMEOUT_S
from app.core.security import scrubbed_env
from app.schemas.diagnostic import DiagnosticsResult, Failure


def _kill_process_tree(proc: "subprocess.Popen[bytes]") -> None:
    """Best-effort kill of the process and its children."""
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                capture_output=True,
            )
        except Exception:
            pass
    else:
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
        except ProcessLookupError:
            return
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        else:
            import time

            time.sleep(0.5)
            try:
                os.killpg(pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except Exception:
                pass


def _truncate(text: str, limit: int = MAX_CAPTURE_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[output truncated, {len(text) - limit} more chars]..."


def run_pytest(workspace_root: str | Path, command: List[str], timeout_s: float = PYTEST_TIMEOUT_S) -> DiagnosticsResult:
    """Run the predefined pytest command inside a workspace copy.

    The command comes from project.json; it is never AI-generated.
    Per spec 2.4 the command runs as [sys.executable, "-m", "pytest", ...],
    so a leading "pytest" in project.json is expanded accordingly.
    Returns a DiagnosticsResult parsed from the JUnit XML report.
    """
    workspace = Path(workspace_root)
    junit_path = workspace / ".repomedic" / "junit.xml"
    junit_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = list(command)
    if cmd and cmd[0] == "pytest":
        cmd = [sys.executable, "-m", "pytest"] + cmd[1:]
    full_command = cmd + ["-p", "no:cacheprovider", "--junitxml", str(junit_path)]

    env = scrubbed_env(workspace)
    result = DiagnosticsResult(exit_code=-1)

    proc: Optional[subprocess.Popen[bytes]] = None
    timeout_occurred = False
    try:
        if os.name == "nt":
            proc = subprocess.Popen(
                full_command,
                cwd=str(workspace),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            proc = subprocess.Popen(
                full_command,
                cwd=str(workspace),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True,
            )
        try:
            stdout, stderr = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timeout_occurred = True
            _kill_process_tree(proc)
            stdout, stderr = proc.communicate()
    except FileNotFoundError as exc:
        result.exit_code = -1
        result.error_type = "INTERNAL"
        result.raw_output = f"pytest/python not found: {exc}"
        return result
    except Exception as exc:  # noqa: BLE001
        result.exit_code = -1
        result.error_type = "INTERNAL"
        result.raw_output = f"failed to run pytest: {exc}"
        return result

    combined = (stdout or "") + "\n[STDERR]\n" + (stderr or "")
    result.raw_output = _truncate(combined)
    result.timeout_occurred = timeout_occurred
    result.exit_code = proc.returncode if proc.returncode is not None else -1

    if junit_path.exists():
        try:
            _parse_junit(junit_path, result)
        except Exception as exc:  # noqa: BLE001
            result.error_type = result.error_type or "INTERNAL"
            result.raw_output += f"\n[junit parse error: {exc}]"
    else:
        if result.exit_code == 5:
            result.error_type = "NO_TESTS_COLLECTED"
        elif timeout_occurred:
            result.error_type = "TIMEOUT"
        elif result.exit_code != 0:
            result.error_type = "INTERNAL"

    if timeout_occurred and result.error_type is None:
        result.error_type = "TIMEOUT"

    if result.error_type is None:
        text_lc = combined.lower()
        if "syntaxerror" in text_lc or "syntax error" in text_lc:
            result.error_type = "SYNTAX_ERROR"
        elif result.errors > 0 and result.passed == 0 and result.failed == 0:
            result.error_type = "SYNTAX_ERROR"

    return result


def _parse_junit(path: Path, result: DiagnosticsResult) -> None:
    tree = ET.parse(path)
    root = tree.getroot()
    suites = list(root) if root.tag == "testsuites" else [root]

    passed = failed = errors = skipped = 0
    failures: list[Failure] = []
    passing_tests: list[str] = []

    for suite in suites:
        if suite.tag != "testsuite":
            continue
        for tc in suite.iter("testcase"):
            name = tc.get("name", "")
            file_ = tc.get("file")
            line = tc.get("line")
            try:
                line_int = int(line) if line is not None else None
            except ValueError:
                line_int = None
            classname = tc.get("classname", "")
            test_id = f"{file_}::{name}" if file_ else (f"{classname}::{name}" if classname else name)

            failure_el = tc.find("failure")
            error_el = tc.find("error")
            skipped_el = tc.find("skipped")

            if failure_el is not None:
                failed += 1
                failures.append(
                    Failure(
                        test_id=test_id,
                        file=file_,
                        line=line_int,
                        message=failure_el.get("message", "") or "",
                        traceback=failure_el.text,
                    )
                )
            elif error_el is not None:
                errors += 1
                failures.append(
                    Failure(
                        test_id=test_id,
                        file=file_,
                        line=line_int,
                        message=error_el.get("message", "") or "",
                        traceback=error_el.text,
                    )
                )
            elif skipped_el is not None:
                skipped += 1
            else:
                passed += 1
                passing_tests.append(test_id)

    result.passed = passed
    result.failed = failed
    result.errors = errors
    result.skipped = skipped
    result.total = passed + failed + errors + skipped
    result.failures = failures
    result.passing_tests = passing_tests
    try:
        result.duration_s = float(root.get("time", "0") or 0)
    except ValueError:
        result.duration_s = 0.0
