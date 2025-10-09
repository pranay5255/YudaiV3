import asyncio
import itertools
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

try:
    from e2b_code_interpreter import Sandbox
    E2B_AVAILABLE = True
except ImportError:
    E2B_AVAILABLE = False
    Sandbox = None
from models import Solve, SolveRun, SolveStatus
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from utils import utc_now

from .models import ExperimentMatrix, Limits

DEFAULT_MAX_PARALLEL = 2
logger = logging.getLogger(__name__)


def expand_matrix(matrix: ExperimentMatrix) -> List[Dict[str, Any]]:
    """Expand an experiment matrix into concrete experiment configs."""
    if (
        not matrix.models
        or not matrix.temps
        or not matrix.max_edits
        or not matrix.evolution
    ):
        raise ValueError("Experiment matrix must include at least one value for each axis")

    combinations = list(
        itertools.product(
            matrix.models, matrix.temps, matrix.max_edits, matrix.evolution
        )
    )

    expanded: List[Dict[str, Any]] = []
    for idx, (model, temp, max_edits, evolution) in enumerate(combinations):
        expanded.append(
            {
                "ordinal": idx,
                "model": model,
                "temperature": float(temp),
                "max_edits": int(max_edits),
                "evolution": evolution,
            }
        )

    return expanded


class ResultReducer:
    """Select the champion solve run based on heuristic ranking."""
    #TODO: this needs to be checked and stored in the json format for easy analysis 
    @staticmethod
    def select(runs: Sequence[SolveRun]) -> Optional[SolveRun]:
        successful = [run for run in runs if run.tests_passed]
        if not successful:
            return None

        def score(run: SolveRun) -> Tuple[float, float, float, float]:
            files = float(run.files_changed) if run.files_changed is not None else float("inf")
            loc = float(run.loc_changed) if run.loc_changed is not None else float("inf")
            latency = float(run.latency_ms) if run.latency_ms is not None else float("inf")
            temperature = float(run.temperature) if run.temperature is not None else 1.0
            return (files, loc, latency, temperature)

        return min(successful, key=score)


class SolveRunner:
    """Run mini-SWE-agent experiments in parallel E2B sandboxes."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        gh_token: str,
        template_id: str,
    ) -> None:
        if not E2B_AVAILABLE:
            raise RuntimeError("e2b-code-interpreter is not available. Install it with: pip install e2b-code-interpreter")
        
        if not gh_token:
            raise ValueError("GitHub token is required to run solve experiments")
        if not template_id:
            raise ValueError("E2B template identifier is required")

        api_key = os.getenv("E2B_API_KEY")
        if not api_key:
            raise RuntimeError("E2B_API_KEY environment variable is required")

        self._session_factory = session_factory
        self._gh_token = gh_token
        self._template_id = template_id
        self._api_key = api_key

    async def run(
        self,
        solve_id: str,
        base_cfg: Dict[str, Any],
        matrix: ExperimentMatrix,
        limits: Optional[Limits] = None,
    ) -> None:
        limits = limits or Limits()
        concurrency = limits.max_parallel or DEFAULT_MAX_PARALLEL

        try:
            expanded = expand_matrix(matrix)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to expand experiment matrix for solve %s: %s", solve_id, exc)
            self._mark_failed(solve_id, f"Matrix expansion failed: {exc}")
            return

        if not expanded:
            logger.error("Solve %s produced no experiments; marking as failed", solve_id)
            self._mark_failed(solve_id, "Experiment matrix produced no runs")
            return

        run_catalog: List[Tuple[str, Dict[str, Any]]] = []
        try:
            run_catalog = self._bootstrap_runs(solve_id, expanded, limits)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to bootstrap solve %s: %s", solve_id, exc)
            self._mark_failed(solve_id, f"Bootstrap failed: {exc}")
            return

        sem = asyncio.Semaphore(concurrency)
        tasks = [
            asyncio.create_task(self._guarded_run(solve_id, run_id, exp_cfg, base_cfg, sem))
            for run_id, exp_cfg in run_catalog
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for run_meta, result in zip(run_catalog, results):
            run_id, exp_cfg = run_meta
            if isinstance(result, Exception):
                logger.error(
                    "Solve run %s (%s/%s/%s) raised: %s",
                    run_id,
                    exp_cfg.get("model"),
                    exp_cfg.get("temperature"),
                    exp_cfg.get("evolution"),
                    result,
                )

        await self._finalise_solve(solve_id)

    def _bootstrap_runs(
        self,
        solve_id: str,
        expanded: List[Dict[str, Any]],
        limits: Limits,
    ) -> List[Tuple[str, Dict[str, Any]]]:
        db = self._session_factory()
        try:
            solve = (
                db.query(Solve)
                .filter(Solve.id == solve_id)
                .with_for_update()
                .one_or_none()
            )
            if not solve:
                raise ValueError(f"Solve {solve_id} not found")

            now = utc_now()
            solve.status = SolveStatus.RUNNING.value
            solve.started_at = now
            solve.updated_at = now
            solve.max_parallel = limits.max_parallel
            solve.time_budget_s = limits.time_budget_s
            solve.error_message = None

            run_catalog: List[Tuple[str, Dict[str, Any]]] = []
            for cfg in expanded:
                run_id = str(uuid4())
                run = SolveRun(
                    id=run_id,
                    solve_id=solve_id,
                    model=cfg["model"],
                    temperature=cfg["temperature"],
                    max_edits=cfg["max_edits"],
                    evolution=cfg["evolution"],
                    status=SolveStatus.PENDING.value,
                )
                db.add(run)
                run_catalog.append((run_id, cfg))

            db.commit()
            return run_catalog
        finally:
            db.close()

    async def _guarded_run(
        self,
        solve_id: str,
        run_id: str,
        exp_cfg: Dict[str, Any],
        base_cfg: Dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> None:
        async with semaphore:
            try:
                await self._execute_run(run_id, exp_cfg, base_cfg)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception("Run %s for solve %s failed: %s", run_id, solve_id, exc)
                self._safe_update_run(
                    run_id,
                    status=SolveStatus.FAILED.value,
                    tests_passed=False,
                    error_message=str(exc),
                    completed_at=utc_now(),
                )

    async def _execute_run(
        self,
        run_id: str,
        exp_cfg: Dict[str, Any],
        base_cfg: Dict[str, Any],
    ) -> None:
        start_time = utc_now()
        started_monotonic = time.monotonic()
        self._safe_update_run(
            run_id,
            status=SolveStatus.RUNNING.value,
            started_at=start_time,
        )

        sbx: Optional[Sandbox] = None
        sandbox_id: Optional[str] = None
        branch_name = f"yudai/fix-{base_cfg['issue_number']}-{run_id[:8]}"
        repo_url = base_cfg["repo_url"]
        base_branch = base_cfg["base_branch"]

        smoke_logs = agent_logs = tests_logs = numstat_logs = ""
        agent_err = tests_err = ""
        pr_url: Optional[str] = None
        files_changed: Optional[int] = None
        loc_changed: Optional[int] = None
        passed = False
        tests_result = None

        try:
            sbx = await Sandbox.create(template_id=self._template_id, api_key=self._api_key)
            sandbox_id = getattr(sbx, "id", None)

            await sbx.files.write("/root/.env", f"GITHUB_TOKEN={self._gh_token}")

            await sbx.commands.run(
                f"git clone {repo_url} repo && cd repo && git checkout {base_branch}"
            )

            await sbx.commands.run(
                "cd repo && if [ -f requirements.txt ]; then pip install -r requirements.txt; fi"
            )
            await sbx.commands.run(
                "cd repo && if [ -f package.json ]; then npm ci || pnpm i; fi"
            )

            smoke = await sbx.commands.run(
                "cd repo && (pytest -q || npm test --silent || true)"
            )
            smoke_logs = smoke.stdout[-2000:] if smoke.stdout else ""

            await sbx.commands.run(
                "cd / && rm -rf mini && git clone https://github.com/SWE-agent/mini-swe-agent mini"
            )
            agent_res = await sbx.commands.run(
                "cd repo && ../mini/bin/mini-swe "
                f"--issue {base_cfg['issue_number']} "
                f"--model \"{exp_cfg['model']}\" "
                f"--temperature {exp_cfg['temperature']} "
                f"--max-edits {exp_cfg['max_edits']} "
                f"--strategy \"{exp_cfg['evolution']}\" "
                f"--base \"{base_branch}\" "
                f"--branch \"{branch_name}\""
            )
            agent_logs = agent_res.stdout[-4000:] if agent_res.stdout else ""
            agent_err = agent_res.stderr[-2000:] if agent_res.stderr else ""

            numstat = await sbx.commands.run("cd repo && git diff --numstat || true")
            numstat_logs = numstat.stdout or ""
            files_changed, loc_changed = self._parse_diff_stats(numstat_logs)

            tests = await sbx.commands.run(
                "cd repo && (pytest -q || npm test --silent)"
            )
            tests_result = tests
            tests_logs = tests.stdout[-2000:] if tests.stdout else ""
            tests_err = tests.stderr[-2000:] if tests.stderr else ""
            passed = tests.exit_code == 0

            if passed:
                await sbx.commands.run(
                    "cd repo && git config user.email bot@yudai.app && git config user.name yudai-bot"
                )
                await sbx.commands.run("cd repo && git add -A")
                await sbx.commands.run(
                    "cd repo && git commit -m '[AI] Fix from YudaiV3 agent'"
                )
                await sbx.commands.run(f"cd repo && git push origin HEAD:{branch_name}")
                pr = await sbx.commands.run(
                    "cd repo && gh pr create "
                    f"-t \"[AI] Fix: #{base_cfg['issue_number']}\" "
                    f"-b \"Automated fix\" -B {base_branch}"
                )
                pr_url = pr.stdout.strip() if pr.stdout else None

            latency_ms = int((time.monotonic() - started_monotonic) * 1000)
            diagnostics = {
                "smoke": smoke_logs,
                "agent": agent_logs,
                "agent_stderr": agent_err,
                "tests": tests_logs,
                "tests_stderr": tests_err,
                "numstat": numstat_logs,
            }

            self._safe_update_run(
                run_id,
                status=SolveStatus.COMPLETED.value if passed else SolveStatus.FAILED.value,
                sandbox_id=sandbox_id,
                tests_passed=passed,
                pr_url=pr_url,
                files_changed=files_changed,
                loc_changed=loc_changed,
                latency_ms=latency_ms,
                diagnostics=diagnostics,
                completed_at=utc_now(),
                error_message=None if passed else (tests_err or agent_err),
            )
        finally:
            if sbx is not None:
                await sbx.close()

    async def _finalise_solve(self, solve_id: str) -> None:
        db = self._session_factory()
        try:
            solve = (
                db.query(Solve)
                .options(selectinload(Solve.runs))
                .filter(Solve.id == solve_id)
                .one_or_none()
            )
            if not solve:
                return

            champion = ResultReducer.select(solve.runs)
            now = utc_now()
            solve.completed_at = now
            solve.updated_at = now

            if champion:
                solve.status = SolveStatus.COMPLETED.value
                solve.champion_run_id = champion.id
                solve.error_message = None
            else:
                solve.status = SolveStatus.FAILED.value
                solve.champion_run_id = None
                if not solve.error_message:
                    solve.error_message = "No successful experiments"

            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Failed to finalize solve %s: %s", solve_id, exc)
        finally:
            db.close()

    def _mark_failed(self, solve_id: str, message: str) -> None:
        db = self._session_factory()
        try:
            solve = db.query(Solve).filter(Solve.id == solve_id).one_or_none()
            if not solve:
                return
            now = utc_now()
            solve.status = SolveStatus.FAILED.value
            solve.error_message = message
            solve.completed_at = now
            solve.updated_at = now
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Failed to mark solve %s as failed: %s", solve_id, exc)
        finally:
            db.close()

    def _safe_update_run(self, run_id: str, **fields: Any) -> None:
        db = self._session_factory()
        try:
            run = db.query(SolveRun).filter(SolveRun.id == run_id).one_or_none()
            if not run:
                logger.warning("Solve run %s not found during update", run_id)
                return
            for key, value in fields.items():
                setattr(run, key, value)
            run.updated_at = utc_now()
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            logger.exception("Failed to update solve run %s: %s", run_id, exc)
        finally:
            db.close()

    @staticmethod
    def _parse_diff_stats(numstat_output: str) -> Tuple[int, int]:
        files_changed = 0
        loc_changed = 0
        for line in numstat_output.splitlines():
            parts = line.strip().split("\t")
            if len(parts) < 3:
                continue
            try:
                adds = int(parts[0]) if parts[0] != "-" else 0
                dels = int(parts[1]) if parts[1] != "-" else 0
            except ValueError:
                continue
            files_changed += 1
            loc_changed += abs(adds) + abs(dels)
        return files_changed or 0, loc_changed or 0
