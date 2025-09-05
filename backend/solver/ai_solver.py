"""
AI Solver Adapter for YudaiV3
Integrates SWE-agent CLI for automated code solving without GitHub PR creation
"""

import asyncio
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from models import AIModel, AISolveEdit, AISolveSession, Issue, SWEAgentConfig
from schemas.ai_solver import EditType, SolveStatus
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("AISolver")


class AISolverError(Exception):
    """Custom exception for AI Solver errors"""

    pass


class AISolverAdapter:
    """
    Main AI Solver adapter that integrates with SWE-agent CLI
    Handles the complete solve workflow without GitHub integration
    """

    def __init__(self, db: Session):
        self.db = db
        self.config_path = os.getenv("SWEAGENT_CONFIG_PATH", "/app/solver/config.yaml")
        self.data_path = os.getenv("SWEAGENT_DATA_PATH", "/data/swe_runs")
        self.timeout = int(os.getenv("SOLVER_TIMEOUT_SECONDS", "1800"))  # 30 minutes
        self.max_cost = float(os.getenv("MAX_SOLVER_COST_USD", "10.0"))

        print(
            f"[AISolver] Initializing AI Solver with config_path={self.config_path}, data_path={self.data_path}"
        )
        logger.info(
            f"AISolver initialized: timeout={self.timeout}s, max_cost=${self.max_cost}"
        )

        # Ensure data directory exists
        try:
            os.makedirs(self.data_path, exist_ok=True)
            print(f"[AISolver] Data directory verified: {self.data_path}")
            logger.info(f"Data directory ready: {self.data_path}")
        except Exception as e:
            print(f"[AISolver] ERROR: Failed to create data directory: {e}")
            logger.error(f"Failed to create data directory {self.data_path}: {e}")
            raise

    async def run_solver(
        self,
        issue_id: Optional[int] = None,
        user_id: int = None,
        repo_url: str = None,
        branch: str = "main",
        issue_content: Optional[str] = None,
        issue_title: Optional[str] = None,
        ai_model_id: Optional[int] = None,
        swe_config_id: Optional[int] = None,
    ) -> int:
        """
        Main solver entry point - creates session and runs SWE-agent
        Returns session_id for tracking

        Args:
            issue_id: Optional database ID of the issue to solve
            user_id: Database ID of the user requesting the solve
            repo_url: Git repository URL to clone and work on
            branch: Git branch to work on (default: main)
            issue_content: Optional issue content/description for solving
            issue_title: Optional issue title
            ai_model_id: Optional AI model to use
            swe_config_id: Optional SWE-agent config to use

        Returns:
            int: Session ID for tracking progress
        """
        print(
            f"[AISolver] Starting solve session: issue_id={issue_id}, user_id={user_id}, repo={repo_url}"
        )
        logger.info(
            f"Starting AI solve session: issue_id={issue_id}, user_id={user_id}, repo={repo_url}, branch={branch}"
        )

        start_time = datetime.utcnow()

        # Create solve session
        session = AISolveSession(
            user_id=user_id,
            issue_id=issue_id,
            ai_model_id=ai_model_id,
            swe_config_id=swe_config_id,
            status=SolveStatus.PENDING,
            repo_url=repo_url,
            branch_name=branch,
            started_at=start_time,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        print(f"[AISolver] Created session {session.id} with status {session.status}")
        logger.info(
            f"Session {session.id} created: ai_model_id={ai_model_id}, swe_config_id={swe_config_id}"
        )

        try:
            # Update status to running
            session.status = SolveStatus.RUNNING
            self.db.commit()
            print(f"[AISolver] Session {session.id} status updated to RUNNING")
            logger.info(f"Session {session.id} status: RUNNING")

            # Get issue details - either from database or provided content
            if issue_id:
                issue = self.db.query(Issue).filter(Issue.id == issue_id).first()
                if not issue:
                    print(f"[AISolver] ERROR: Issue {issue_id} not found in database")
                    logger.error(f"Issue {issue_id} not found for session {session.id}")
                    raise AISolverError(f"Issue {issue_id} not found")
                issue_title = issue.title
                issue_body = issue.body or ""
                print(f"[AISolver] Found issue: '{issue.title}' for session {session.id}")
                logger.info(
                    f"Issue found for session {session.id}: title='{issue.title}', has_body={bool(issue.body)}"
                )
            elif issue_content and issue_title:
                issue_body = issue_content
                print(f"[AISolver] Using provided issue content: '{issue_title}' for session {session.id}")
                logger.info(
                    f"Using provided issue content for session {session.id}: title='{issue_title}'"
                )
            else:
                raise AISolverError("Either issue_id or both issue_content and issue_title must be provided")

            # Run SWE-agent
            print(f"[AISolver] Executing SWE-agent for session {session.id}")
            logger.info(f"Starting SWE-agent execution for session {session.id}")
            trajectory = await self._execute_sweagent(
                session.id,
                repo_url,
                issue_title,
                issue_body,
                branch,
                ai_model_id,
                swe_config_id,
            )
            print(f"[AISolver] SWE-agent execution completed for session {session.id}")
            logger.info(f"SWE-agent execution completed for session {session.id}")

            # Process trajectory and extract edits
            print(f"[AISolver] Processing trajectory for session {session.id}")
            logger.info(f"Processing trajectory for session {session.id}")
            await self._process_trajectory(session.id, trajectory)

            # Update session as completed
            session.status = SolveStatus.COMPLETED
            session.completed_at = datetime.utcnow()
            session.trajectory_data = trajectory

            duration = (session.completed_at - start_time).total_seconds()
            print(
                f"[AISolver] Session {session.id} completed successfully in {duration:.2f}s"
            )
            logger.info(
                f"Session {session.id} completed: duration={duration:.2f}s, trajectory_steps={len(trajectory.get('steps', []))}"
            )

        except Exception as e:
            # Update session as failed
            session.status = SolveStatus.FAILED
            session.error_message = str(e)
            session.completed_at = datetime.utcnow()

            duration = (session.completed_at - start_time).total_seconds()
            print(
                f"[AISolver] ERROR: Session {session.id} failed after {duration:.2f}s: {e}"
            )
            logger.error(
                f"Session {session.id} failed: duration={duration:.2f}s, error={str(e)}",
                exc_info=True,
            )

        finally:
            self.db.commit()
            print(f"[AISolver] Session {session.id} final status: {session.status}")
            logger.info(f"Session {session.id} finalized: status={session.status}")

        return session.id

    async def _execute_sweagent(
        self,
        session_id: int,
        repo_url: str,
        issue_title: str,
        issue_body: str,
        branch: str,
        ai_model_id: Optional[int] = None,
        swe_config_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Execute SWE-agent CLI command

        Args:
            session_id: Session ID for tracking
            repo_url: Repository URL to clone
            issue_title: Issue title
            issue_body: Issue description
            branch: Git branch to work on
            ai_model_id: Optional AI model ID
            swe_config_id: Optional SWE config ID

        Returns:
            Dict containing trajectory data
        """
        print(f"[AISolver] Executing SWE-agent for session {session_id}")
        logger.info(
            f"Starting SWE-agent execution: session_id={session_id}, repo_url={repo_url}"
        )

        # Create session-specific directory
        session_dir = Path(self.data_path) / f"session_{session_id}"
        session_dir.mkdir(exist_ok=True)
        print(f"[AISolver] Created session directory: {session_dir}")
        logger.info(f"Session directory created: {session_dir}")

        # Create temporary directory for repository
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_path = Path(temp_dir) / "repo"
            print(f"[AISolver] Using temp repo path: {repo_path}")
            logger.debug(f"Temp repo path: {repo_path}")

            try:
                # Clone repository
                print(f"[AISolver] Cloning repository for session {session_id}")
                logger.info(f"Cloning repository: {repo_url} branch:{branch}")
                await self._clone_repository(repo_url, repo_path, branch)
                print(
                    f"[AISolver] Repository cloned successfully for session {session_id}"
                )
                logger.info(f"Repository cloned successfully for session {session_id}")

                # Prepare configuration
                print(f"[AISolver] Preparing configuration for session {session_id}")
                logger.info(
                    f"Preparing config: ai_model_id={ai_model_id}, swe_config_id={swe_config_id}"
                )
                config_path = await self._prepare_config(
                    session_id, ai_model_id, swe_config_id
                )
                print(f"[AISolver] Configuration prepared: {config_path}")
                logger.info(f"Configuration prepared: {config_path}")

                # Prepare issue text for SWE-agent
                issue_text = self._format_issue_text(issue_title, issue_body)
                print(
                    f"[AISolver] Issue text prepared for session {session_id} (length: {len(issue_text)} chars)"
                )
                logger.debug(f"Issue text prepared for session {session_id}")

                # Run SWE-agent
                print(f"[AISolver] Running SWE-agent command for session {session_id}")
                logger.info(f"Executing SWE-agent command for session {session_id}")
                trajectory = await self._run_sweagent_command(
                    config_path=config_path,
                    repo_path=repo_path,
                    issue_text=issue_text,
                    session_dir=session_dir,
                )
                print(
                    f"[AISolver] SWE-agent command completed for session {session_id}"
                )
                logger.info(
                    f"SWE-agent command completed for session {session_id}: steps={len(trajectory.get('steps', []))}"
                )

                return trajectory

            except Exception as e:
                print(
                    f"[AISolver] ERROR: SWE-agent execution failed for session {session_id}: {e}"
                )
                logger.error(
                    f"SWE-agent execution failed for session {session_id}: {str(e)}",
                    exc_info=True,
                )
                raise AISolverError(f"SWE-agent execution failed: {str(e)}")

    async def _clone_repository(self, repo_url: str, repo_path: Path, branch: str):
        """Clone repository to local path"""
        print(f"[AISolver] Cloning repo: {repo_url} -> {repo_path}")
        logger.info(
            f"Cloning repository: url={repo_url}, path={repo_path}, branch={branch}"
        )

        clone_cmd = [
            "git",
            "clone",
            "--branch",
            branch,
            "--single-branch",
            "--depth",
            "1",  # Shallow clone for faster cloning
            repo_url,
            str(repo_path),
        ]

        try:
            result = await asyncio.create_subprocess_exec(
                *clone_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                result.communicate(),
                timeout=300,  # 5 minutes for cloning
            )

            if result.returncode != 0:
                raise AISolverError(f"Failed to clone repository: {stderr.decode()}")

        except asyncio.TimeoutError:
            raise AISolverError("Repository cloning timed out")

    async def _prepare_config(
        self, session_id: int, ai_model_id: Optional[int], swe_config_id: Optional[int]
    ) -> str:
        """
        Prepare SWE-agent configuration for this session

        Returns:
            str: Path to the prepared configuration file
        """
        # Load base configuration
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)

        # Override with AI model if specified
        if ai_model_id:
            ai_model = self.db.query(AIModel).filter(AIModel.id == ai_model_id).first()
            if ai_model and ai_model.is_active:
                config["agent"]["model"]["model_name"] = (
                    f"{ai_model.provider}/{ai_model.model_id}"
                )
                if ai_model.config:
                    config["agent"]["model"].update(ai_model.config)

        # Override with SWE config if specified
        if swe_config_id:
            swe_config = (
                self.db.query(SWEAgentConfig)
                .filter(SWEAgentConfig.id == swe_config_id)
                .first()
            )
            if swe_config and swe_config.parameters:
                # Merge SWE config parameters
                config.update(swe_config.parameters)

        # Set session-specific paths
        session_dir = Path(self.data_path) / f"session_{session_id}"
        config["environment"]["data_path"] = str(session_dir)
        config["logging"]["trajectory_path"] = str(session_dir / "trajectories")
        config["logging"]["log_file"] = str(session_dir / "solver.log")

        # Save session-specific config
        config_file = session_dir / "config.yaml"
        with open(config_file, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        return str(config_file)

    def _format_issue_text(self, title: str, body: str) -> str:
        """Format issue title and body for SWE-agent"""
        formatted = f"# {title}\n\n"
        if body:
            formatted += f"{body}\n\n"

        # Add some context for the AI
        formatted += "## Instructions\n"
        formatted += "Please analyze this issue and implement a solution. "
        formatted += (
            "Focus on making minimal, targeted changes that address the core problem. "
        )
        formatted += (
            "Ensure your changes are well-tested and follow existing code patterns.\n"
        )

        print(f"[AISolver] Issue text formatted: {len(formatted)} characters")
        logger.debug(f"Issue text formatted: length={len(formatted)}")

        return formatted

    async def _run_sweagent_command(
        self, config_path: str, repo_path: Path, issue_text: str, session_dir: Path
    ) -> Dict[str, Any]:
        """Execute the actual SWE-agent command"""

        # Prepare command
        sweagent_cmd = [
            "sweagent",
            "run",
            "--config",
            config_path,
            "--repo_path",
            str(repo_path),
            "--data_path",
            str(session_dir),
            "--problem_statement",
            issue_text,
            "--output_dir",
            str(session_dir / "output"),
        ]

        try:
            # Execute with timeout
            process = await asyncio.create_subprocess_exec(
                *sweagent_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(repo_path),
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout
            )

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise AISolverError(f"SWE-agent failed: {error_msg}")

            # Parse trajectory output
            trajectory_file = session_dir / "trajectory.json"
            if trajectory_file.exists():
                with open(trajectory_file) as f:
                    return json.load(f)
            else:
                # Fallback: create basic trajectory from stdout
                return {
                    "steps": [],
                    "final_state": "completed",
                    "stdout": stdout.decode(),
                    "stderr": stderr.decode(),
                    "session_id": str(session_dir.name),
                }

        except asyncio.TimeoutError:
            print(
                f"[AISolver] ERROR: SWE-agent execution timed out after {self.timeout}s"
            )
            logger.error(f"SWE-agent execution timed out after {self.timeout} seconds")
            if process:
                print(f"[AISolver] Killing timed-out process (PID: {process.pid})")
                logger.info(f"Killing timed-out SWE-agent process: PID={process.pid}")
                process.kill()
            raise AISolverError("SWE-agent execution timed out")
        except Exception as e:
            print(f"[AISolver] ERROR: Unexpected error during SWE-agent execution: {e}")
            logger.error(
                f"Unexpected error during SWE-agent execution: {str(e)}", exc_info=True
            )
            if process:
                try:
                    process.kill()
                except Exception as e:
                    print(f"[AISolver] ERROR: Unexpected error killing process: {e}")
                    logger.error(
                        f"Unexpected error killing process: {str(e)}", exc_info=True
                    )
                    pass
            raise

    async def _process_trajectory(self, session_id: int, trajectory: Dict[str, Any]):
        """
        Process trajectory and extract file edits

        Args:
            session_id: Session ID
            trajectory: Trajectory data from SWE-agent
        """

        steps = trajectory.get("steps", [])

        for step in steps:
            action = step.get("action", {})

            # Handle different types of actions
            if isinstance(action, dict):
                command = action.get("command")
                args = action.get("args", {})

                # Process file editing commands
                if command == "str_replace_editor":
                    await self._process_file_edit(session_id, step, args)
                elif command == "create_file":
                    await self._process_file_creation(session_id, step, args)
                elif command in ["edit_file", "modify_file"]:
                    await self._process_file_modification(session_id, step, args)

        self.db.commit()

    async def _process_file_edit(self, session_id: int, step: Dict, args: Dict):
        """Process a file edit operation"""
        file_path = args.get("path")
        if not file_path:
            return

        edit_type = EditType.MODIFY
        if "new_str" in args and "old_str" in args:
            original_content = args.get("old_str")
            new_content = args.get("new_str")
        else:
            original_content = None
            new_content = args.get("file_text", "")

        edit = AISolveEdit(
            session_id=session_id,
            file_path=file_path,
            edit_type=edit_type,
            original_content=original_content,
            new_content=new_content,
            edit_metadata={
                "step_index": step.get("step_index"),
                "timestamp": step.get("timestamp"),
                "command": args.get("command"),
                "action_type": "str_replace_editor",
            },
        )
        self.db.add(edit)

    async def _process_file_creation(self, session_id: int, step: Dict, args: Dict):
        """Process a file creation operation"""
        file_path = args.get("path")
        if not file_path:
            return

        edit = AISolveEdit(
            session_id=session_id,
            file_path=file_path,
            edit_type=EditType.CREATE,
            original_content=None,
            new_content=args.get("file_text", ""),
            edit_metadata={
                "step_index": step.get("step_index"),
                "timestamp": step.get("timestamp"),
                "command": "create_file",
                "action_type": "file_creation",
            },
        )
        self.db.add(edit)

    async def _process_file_modification(self, session_id: int, step: Dict, args: Dict):
        """Process a file modification operation"""
        file_path = args.get("path")
        if not file_path:
            return

        edit = AISolveEdit(
            session_id=session_id,
            file_path=file_path,
            edit_type=EditType.MODIFY,
            original_content=args.get("original_content"),
            new_content=args.get("new_content"),
            line_start=args.get("line_start"),
            line_end=args.get("line_end"),
            edit_metadata={
                "step_index": step.get("step_index"),
                "timestamp": step.get("timestamp"),
                "command": args.get("command"),
                "action_type": "file_modification",
            },
        )
        self.db.add(edit)

    def get_session_status(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        Get current status of a solve session

        Args:
            session_id: Session ID to check

        Returns:
            Dict with session status information or None if not found
        """
        session = (
            self.db.query(AISolveSession)
            .filter(AISolveSession.id == session_id)
            .first()
        )

        if not session:
            return None

        edits = (
            self.db.query(AISolveEdit)
            .filter(AISolveEdit.session_id == session_id)
            .all()
        )

        # Calculate statistics
        files_modified = len(set(edit.file_path for edit in edits))
        lines_added = sum(
            len(edit.new_content.split("\n")) if edit.new_content else 0
            for edit in edits
        )
        lines_removed = sum(
            len(edit.original_content.split("\n")) if edit.original_content else 0
            for edit in edits
        )

        # Calculate duration
        duration_seconds = None
        if session.started_at and session.completed_at:
            duration = session.completed_at - session.started_at
            duration_seconds = int(duration.total_seconds())

        return {
            "session_id": session.id,
            "status": session.status,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "error_message": session.error_message,
            "total_edits": len(edits),
            "files_modified": files_modified,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "duration_seconds": duration_seconds,
            "trajectory_steps": len(session.trajectory_data.get("steps", []))
            if session.trajectory_data
            else 0,
            "last_activity": session.updated_at or session.created_at,
        }

    async def cancel_session(self, session_id: int, user_id: int) -> bool:
        """
        Cancel a running solve session

        Args:
            session_id: Session ID to cancel
            user_id: User ID requesting cancellation (for authorization)

        Returns:
            bool: True if cancelled successfully
        """
        session = (
            self.db.query(AISolveSession)
            .filter(
                AISolveSession.id == session_id,
                AISolveSession.user_id == user_id,
                AISolveSession.status == SolveStatus.RUNNING,
            )
            .first()
        )

        if not session:
            return False

        # Update session status
        session.status = SolveStatus.CANCELLED
        session.completed_at = datetime.utcnow()
        session.error_message = "Cancelled by user"

        self.db.commit()

        # TODO: Implement actual process termination if needed
        # This would require tracking the actual subprocess PIDs

        return True
