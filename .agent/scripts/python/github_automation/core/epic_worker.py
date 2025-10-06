"""Epic Worker - Intelligent epic and issue prioritization with autonomous completion."""

import json
import logging
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from github_automation.config.models import GitHubConfig, TimeoutConfig
from github_automation.core.exceptions import ProcessError, WorkflowError
from github_automation.core.git_utils import GitRepository
from github_automation.core.logging_setup import get_logger
from github_automation.core.process_manager import ProcessManager

logger = get_logger(__name__)


@dataclass
class IssueSelection:
    """Selected issue with priority information."""
    
    issue_number: int
    issue_title: str
    epic_title: Optional[str]
    priority_score: int
    reasoning: str
    labels: List[str]
    
    @classmethod
    def from_dict(cls, data: dict) -> "IssueSelection":
        """Create from dictionary."""
        return cls(
            issue_number=data.get("issue_number", 0),
            issue_title=data.get("issue_title", ""),
            epic_title=data.get("epic_title"),
            priority_score=data.get("priority_score", 0),
            reasoning=data.get("reasoning", ""),
            labels=data.get("labels", [])
        )


class EpicWorker:
    """Autonomously work through epics and issues with intelligent prioritization."""
    
    def __init__(self, config: GitHubConfig):
        """Initialize epic worker."""
        self.config = config
        # Use current directory as repository path (we're running inside the repo)
        self.git = GitRepository(".")
        # Create timeout config for ProcessManager
        timeout_config = TimeoutConfig()
        self.process_manager = ProcessManager(timeout_config)
        self.completed_issues: List[int] = []
        
    def run(self) -> None:
        """Main loop to process all epics and issues."""
        logger.info("🚀 Starting Epic Worker for %s", self.config.repository)
        
        while True:
            try:
                # Check for open issues
                open_issues = self._get_open_issues()
                if not open_issues:
                    logger.info("🎉 ALL ISSUES COMPLETE! Project fully implemented!")
                    break
                
                logger.info("Found %d open issues", len(open_issues))
                
                # Select next issue using Claude
                selection = self._select_next_issue(open_issues)
                if not selection or selection.issue_number == 0:
                    logger.warning("Failed to select issue, retrying in 60s...")
                    time.sleep(60)
                    continue
                
                logger.info(
                    "📌 Selected Issue #%d: %s (Priority: %d)",
                    selection.issue_number,
                    selection.issue_title,
                    selection.priority_score
                )
                logger.info("   Reason: %s", selection.reasoning)
                
                # Work on the selected issue
                success = self._work_on_issue(selection)
                
                if success:
                    self.completed_issues.append(selection.issue_number)
                    logger.info("✅ Issue #%d completed!", selection.issue_number)
                else:
                    logger.warning("⚠️ Issue #%d needs manual review", selection.issue_number)
                
                # Brief pause before next cycle
                logger.info("Pausing 30s before next cycle...")
                time.sleep(30)
                
            except KeyboardInterrupt:
                logger.info("Epic worker interrupted by user")
                break
            except Exception as e:
                logger.error("Error in main loop: %s", e, exc_info=True)
                time.sleep(60)
        
        logger.info("🏁 Epic worker complete - processed %d issues", len(self.completed_issues))
    
    def _get_open_issues(self) -> List[Dict]:
        """Get all open issues from repository."""
        try:
            cmd = [
                "gh", "issue", "list",
                "--repo", self.config.repository,
                "--state", "open",
                "--json", "number,title,labels,body",
                "--limit", "200"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            
            return json.loads(result.stdout)
            
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.error("Failed to get issues: %s", e)
            return []
    
    def _select_next_issue(self, issues: List[Dict]) -> Optional[IssueSelection]:
        """Use Claude swarm to intelligently select the next issue to work on."""
        logger.info("🤖 Using Claude to select most important issue...")
        
        # Create selection objective for Claude
        objective = self._create_selection_objective(issues)
        
        try:
            # Use claude-flow swarm for quick selection task
            result = self.process_manager.run_claude_swarm(
                task=objective,
                timeout=120  # 2 minutes for selection
            )
            
            # Parse Claude's response to find JSON
            if result.stdout:
                selection_json = self._extract_json_from_response(result.stdout)
                if selection_json:
                    return IssueSelection.from_dict(selection_json)
                    
        except ProcessError as e:
            logger.error("Failed to select issue: %s", e)
        
        # Fallback: select first issue with certain labels
        return self._fallback_selection(issues)
    def _create_selection_objective(self, issues: List[Dict]) -> str:
        """Create concise objective for Claude to analyze and select issues."""
        # Truncate issues list if too long
        max_issues = 20
        if len(issues) > max_issues:
            issues = issues[:max_issues]
        
        issues_summary = json.dumps(issues, indent=None)  # Compact JSON
        
        return f"""Select the most important issue to work on.

ISSUES: {issues_summary}

PRIORITY: Security > Blocking > Core Features > Tests > Docs

OUTPUT JSON ONLY:
{{"issue_number": <number>, "issue_title": "<title>", "priority_score": <0-100>, "reasoning": "<why>", "labels": ["label1"]}}"""
    
    def _extract_json_from_response(self, response: str) -> Optional[Dict]:
        """Extract JSON from Claude's response."""
        # Try to find JSON in the response
        json_pattern = r'\{[^{}]*"issue_number"[^{}]*\}'
        matches = re.findall(json_pattern, response, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                if "issue_number" in data:
                    return data
            except json.JSONDecodeError:
                continue
        
        return None
    
    def _fallback_selection(self, issues: List[Dict]) -> Optional[IssueSelection]:
        """Fallback selection when Claude fails - prioritize by labels."""
        priority_labels = [
            "blocking", "critical", "security", "foundation",
            "epic", "dependency", "core", "required"
        ]
        
        for issue in issues:
            labels = [label["name"].lower() for label in issue.get("labels", [])]
            
            for priority_label in priority_labels:
                if any(priority_label in label for label in labels):
                    return IssueSelection(
                        issue_number=issue["number"],
                        issue_title=issue["title"],
                        epic_title=None,
                        priority_score=80,
                        reasoning=f"Selected due to '{priority_label}' label (fallback selection)",
                        labels=labels
                    )
        
        # Last resort: pick first issue
        if issues:
            first = issues[0]
            return IssueSelection(
                issue_number=first["number"],
                issue_title=first["title"],
                epic_title=None,
                priority_score=50,
                reasoning="First available issue (fallback selection)",
                labels=[label["name"] for label in first.get("labels", [])]
            )
        
        return None
    
    def _work_on_issue(self, selection: IssueSelection) -> bool:
        """Work on the selected issue to completion."""
        logger.info("🔧 Starting work on Issue #%d: %s", 
                   selection.issue_number, selection.issue_title)
        
        branch_name = f"issue-{selection.issue_number}"
        
        # Create comprehensive objective
        objective = self._create_work_objective(selection, branch_name)
        
        try:
            # Use swarm to actually work on the issue
            logger.info("🐝 Starting swarm work on Issue #%d", selection.issue_number)
            
            # IMPORTANT: For actual work, we use swarm, not hive-mind spawn
            # Hive-mind spawn just creates coordination infrastructure but doesn't do work
            result = self.process_manager.run_claude_swarm(
                task=objective,
                timeout=7200  # 2 hours max
            )
            
            # Check if hive-mind started successfully
            from ..core.process_manager import ProcessStatus
            if result.status != ProcessStatus.COMPLETED:
                logger.error("❌ Failed to spawn hive-mind: exit code %s", result.exit_code)
                if result.stderr:
                    logger.error("Error output: %s", result.stderr[:1000])
                if result.stdout:
                    logger.debug("Standard output: %s", result.stdout[:1000])
                return False
            
            # Wait for PR to be ready
            return self._wait_for_pr_ready(branch_name, selection.issue_number)
            
        except ProcessError as e:
            logger.error("Failed to work on issue: %s", e)
            return False
    
    def _create_work_objective(self, selection: IssueSelection, branch_name: str) -> str:
        """Create concise work objective for issue."""
        return f"""Implement Issue #{selection.issue_number}: {selection.issue_title}

Repository: {self.config.repository}
Branch: {branch_name}

Tasks:
1. Create branch {branch_name}
2. Implement solution with tests
3. Create PR that closes #{selection.issue_number}
4. Ensure all CI checks pass

Quality: Production-ready TypeScript with >80% test coverage."""
    
    def _wait_for_pr_ready(self, branch_name: str, issue_number: int) -> bool:
        """Wait for PR to be created and ready to merge."""
        logger.info("⏳ Waiting for PR to be ready...")
        
        start_time = time.time()
        max_wait = 7200  # 2 hours
        
        while time.time() - start_time < max_wait:
            pr_info = self._get_pr_info(branch_name)
            
            if not pr_info:
                logger.debug("PR not created yet, waiting...")
                time.sleep(30)
                continue
            
            pr_number = pr_info.get("number", 0)
            merge_state = pr_info.get("mergeStateStatus", "UNKNOWN")
            mergeable = pr_info.get("mergeable", "UNKNOWN")
            
            logger.info("PR #%d - Mergeable: %s, State: %s", 
                       pr_number, mergeable, merge_state)
            
            # Check CI status
            checks_status = self._get_ci_status(pr_info)
            
            if checks_status == "FAILED":
                logger.warning("PR #%d has failing checks, spawning repair swarm...", pr_number)
                repair_success = self._repair_failing_checks(pr_number, branch_name, issue_number)
                if repair_success:
                    logger.info("✅ Repair swarm completed, checking PR status again...")
                    time.sleep(30)  # Brief wait for CI to re-run
                    continue
                else:
                    logger.error("❌ Repair swarm failed, waiting before retry...")
                    time.sleep(120)  # Longer wait before retry
                    continue
            
            if checks_status == "PENDING":
                logger.info("PR #%d has pending checks, waiting...", pr_number)
                time.sleep(30)
                continue
            
            # All checks passed
            if merge_state in ["CLEAN", "HAS_HOOKS"]:
                logger.info("✅ PR #%d is ready to merge!", pr_number)
                
                if self.config.auto_merge:
                    return self._merge_pr(pr_number, issue_number)
                else:
                    logger.info("📋 PR #%d ready for manual review", pr_number)
                    return True
            
            time.sleep(30)
        
        logger.error("Timeout waiting for PR to be ready")
        return False
    
    def _repair_failing_checks(self, pr_number: int, branch_name: str, issue_number: int) -> bool:
        """Spawn repair swarm to fix failing CI checks."""
        logger.info("🔧 Spawning repair swarm for PR #%d with failing checks", pr_number)
        
        # Create repair objective
        repair_objective = f"""Fix failing CI checks for PR #{pr_number}
        
Repository: {self.config.repository}
Branch: {branch_name}
Issue: #{issue_number}

Tasks:
1. Check out branch {branch_name}
2. Analyze failing CI checks and errors
3. Fix all failing tests, linting, and build issues
4. Commit fixes and push to update PR
5. Ensure all CI checks pass

Focus on TypeScript compilation errors, test failures, and linting issues."""
        
        try:
            # Use swarm to fix the failing checks
            result = self.process_manager.run_claude_swarm(
                task=repair_objective,
                timeout=7200  # 2 hours max for repairs (activity-based timeout will kick in if stuck)
            )
            
            from ..core.process_manager import ProcessStatus
            if result.status == ProcessStatus.COMPLETED:
                logger.info("✅ Repair swarm completed successfully")
                return True
            else:
                logger.error("❌ Repair swarm failed: exit code %s", result.exit_code)
                if result.stderr:
                    logger.error("Repair error output: %s", result.stderr[:500])
                return False
                
        except Exception as e:
            logger.error("Failed to run repair swarm: %s", e)
            return False
    
    def _get_pr_info(self, branch_name: str) -> Optional[Dict]:
        """Get PR information for branch."""
        try:
            cmd = [
                "gh", "pr", "list",
                "--repo", self.config.repository,
                "--head", branch_name,
                "--json", "number,mergeable,mergeStateStatus,statusCheckRollup",
                "--limit", "1"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            
            prs = json.loads(result.stdout)
            return prs[0] if prs else None
            
        except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
            logger.error("Failed to get PR info: %s", e)
            return None
    
    def _get_ci_status(self, pr_info: Dict) -> str:
        """Determine CI status from PR info."""
        rollup = pr_info.get("statusCheckRollup", [])
        
        has_pending = any(
            check.get("status") in ["PENDING", "IN_PROGRESS", "QUEUED"] or
            check.get("conclusion") is None
            for check in rollup
        )
        
        has_failed = any(
            check.get("conclusion") in ["FAILURE", "CANCELLED", "TIMED_OUT"]
            for check in rollup
        )
        
        if has_failed:
            return "FAILED"
        elif has_pending:
            return "PENDING"
        else:
            return "SUCCESS"
    
    def _merge_pr(self, pr_number: int, issue_number: int) -> bool:
        """Merge PR and close issue."""
        try:
            logger.info("🔀 Auto-merging PR #%d...", pr_number)
            
            # Merge PR
            subprocess.run(
                [
                    "gh", "pr", "merge", str(pr_number),
                    "--repo", self.config.repository,
                    "--squash",
                    "--delete-branch"
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=True
            )
            
            # Close issue
            subprocess.run(
                [
                    "gh", "issue", "close", str(issue_number),
                    "--repo", self.config.repository,
                    "--comment", f"Completed via PR #{pr_number} by autonomous epic worker"
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            
            logger.info("✅ PR #%d merged and Issue #%d closed!", pr_number, issue_number)
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error("Failed to merge PR: %s", e)
            return False