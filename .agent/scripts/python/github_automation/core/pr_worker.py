"""PR Worker - Automated pull request processing with Claude-Flow hive-mind."""

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from github_automation.config.models import GitHubConfig, TimeoutConfig
from github_automation.core.exceptions import ProcessError, WorkflowError
from github_automation.core.git_utils import GitRepository
from github_automation.core.logging_setup import get_logger
from github_automation.core.process_manager import ProcessManager

logger = get_logger(__name__)


@dataclass
class PullRequestInfo:
    """Information about a pull request."""
    
    number: int
    title: str
    author: str
    branch: str
    base_branch: str
    mergeable: str
    merge_state_status: str
    labels: List[str]
    
    @classmethod
    def from_dict(cls, data: dict) -> "PullRequestInfo":
        """Create from dictionary."""
        return cls(
            number=data.get("number", 0),
            title=data.get("title", ""),
            author=data.get("author", {}).get("login", ""),
            branch=data.get("headRefName", ""),
            base_branch=data.get("baseRefName", "main"),
            mergeable=data.get("mergeable", "UNKNOWN"),
            merge_state_status=data.get("mergeStateStatus", "UNKNOWN"),
            labels=[label.get("name", "") for label in data.get("labels", [])]
        )


class PRWorker:
    """Automated PR processing with intelligent conflict resolution."""
    
    def __init__(self, config: GitHubConfig):
        """Initialize PR worker."""
        self.config = config
        self.git = GitRepository(".")
        timeout_config = TimeoutConfig()
        self.process_manager = ProcessManager(timeout_config)
        self.processed_prs: List[int] = []
        
    def run(self, pr_number: Optional[int] = None) -> None:
        """Process pull requests."""
        logger.info("🚀 Starting PR Worker for %s", self.config.repository)
        
        if pr_number:
            # Process specific PR
            self._process_single_pr(pr_number)
        else:
            # Process all open PRs
            self._process_all_prs()
            
    def _process_all_prs(self) -> None:
        """Process all open pull requests."""
        while True:
            try:
                prs = self._get_open_prs()
                if not prs:
                    logger.info("No open pull requests to process")
                    break
                    
                for pr_data in prs:
                    pr = PullRequestInfo.from_dict(pr_data)
                    if pr.number not in self.processed_prs:
                        success = self._process_pr(pr)
                        if success:
                            self.processed_prs.append(pr.number)
                        time.sleep(30)  # Brief pause between PRs
                        
                # Wait before checking for new PRs
                logger.info("Waiting 5 minutes before checking for new PRs...")
                time.sleep(300)
                
            except KeyboardInterrupt:
                logger.info("PR worker interrupted by user")
                break
            except Exception as e:
                logger.error("Error in main loop: %s", e, exc_info=True)
                time.sleep(60)
                
    def _process_single_pr(self, pr_number: int) -> None:
        """Process a single pull request."""
        pr_data = self._get_pr_info(pr_number)
        if not pr_data:
            logger.error("PR #%d not found", pr_number)
            return
            
        pr = PullRequestInfo.from_dict(pr_data)
        success = self._process_pr(pr)
        if success:
            logger.info("✅ PR #%d processed successfully", pr_number)
        else:
            logger.warning("⚠️ PR #%d requires manual review", pr_number)
            
    def _process_pr(self, pr: PullRequestInfo) -> bool:
        """Process a single PR."""
        logger.info("Processing PR #%d: %s", pr.number, pr.title)
        
        # Check if PR needs work
        if pr.mergeable == "MERGEABLE" and pr.merge_state_status == "CLEAN":
            logger.info("PR #%d is already mergeable", pr.number)
            return True
            
        # Create objective for hive-mind
        objective = self._create_pr_objective(pr)
        
        try:
            # Spawn hive-mind to work on PR
            logger.info("🐝 Spawning hive-mind for PR #%d", pr.number)
            
            result = self.process_manager.run_claude_flow(
                objective=objective,
                namespace=f"{self.config.hive_namespace}-pr-{pr.number}",
                agents=self.config.max_agents,
                auto_spawn=True,
                non_interactive=True,
                timeout=7200
            )
            
            # Check if PR is now mergeable
            return self._check_pr_ready(pr.number)
            
        except ProcessError as e:
            logger.error("Failed to process PR: %s", e)
            return False
            
    def _create_pr_objective(self, pr: PullRequestInfo) -> str:
        """Create objective for PR processing."""
        return f"""Process Pull Request #{pr.number}: {pr.title}

Repository: {self.config.repository}
Branch: {pr.branch} -> {pr.base_branch}
Current Status: {pr.merge_state_status}

MANDATORY TASKS:
1. Checkout PR branch: {pr.branch}
2. Identify and resolve ALL merge conflicts
3. Ensure ALL tests pass
4. Fix any linting issues
5. Update branch with base branch if behind
6. Push resolved changes

QUALITY REQUIREMENTS:
- Preserve all intended functionality
- Maintain test coverage
- Follow existing code patterns
- Proper conflict resolution (don't just accept one side)

SUCCESS CRITERIA:
- No merge conflicts
- All CI checks passing
- PR shows as mergeable in GitHub"""
        
    def _get_open_prs(self) -> List[Dict]:
        """Get all open pull requests."""
        try:
            cmd = [
                "gh", "pr", "list",
                "--repo", self.config.repository,
                "--state", "open",
                "--json", "number,title,author,labels,mergeable,mergeStateStatus,headRefName,baseRefName"
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
            logger.error("Failed to get PRs: %s", e)
            return []
            
    def _get_pr_info(self, pr_number: int) -> Optional[Dict]:
        """Get information for a specific PR."""
        try:
            cmd = [
                "gh", "pr", "view", str(pr_number),
                "--repo", self.config.repository,
                "--json", "number,title,author,labels,mergeable,mergeStateStatus,headRefName,baseRefName"
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
            logger.error("Failed to get PR info: %s", e)
            return None
            
    def _check_pr_ready(self, pr_number: int) -> bool:
        """Check if PR is ready to merge."""
        pr_data = self._get_pr_info(pr_number)
        if not pr_data:
            return False
            
        pr = PullRequestInfo.from_dict(pr_data)
        is_ready = (
            pr.mergeable == "MERGEABLE" and 
            pr.merge_state_status in ["CLEAN", "HAS_HOOKS"]
        )
        
        if is_ready:
            logger.info("✅ PR #%d is ready to merge", pr_number)
        else:
            logger.warning("PR #%d status - Mergeable: %s, State: %s", 
                         pr_number, pr.mergeable, pr.merge_state_status)
                         
        return is_ready