"""Issue Worker - Automated issue processing with Claude-Flow hive-mind."""

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
class IssueInfo:
    """Information about a GitHub issue."""
    
    number: int
    title: str
    author: str
    state: str
    labels: List[str]
    body: str
    
    @classmethod
    def from_dict(cls, data: dict) -> "IssueInfo":
        """Create from dictionary."""
        return cls(
            number=data.get("number", 0),
            title=data.get("title", ""),
            author=data.get("author", {}).get("login", ""),
            state=data.get("state", "open"),
            labels=[label.get("name", "") for label in data.get("labels", [])],
            body=data.get("body", "")
        )


class IssueWorker:
    """Automated issue processing with intelligent implementation."""
    
    def __init__(self, config: GitHubConfig):
        """Initialize issue worker."""
        self.config = config
        self.git = GitRepository(".")
        timeout_config = TimeoutConfig()
        self.process_manager = ProcessManager(timeout_config)
        self.processed_issues: List[int] = []
        
    def run(self, issue_number: Optional[int] = None) -> None:
        """Process issues."""
        logger.info("🚀 Starting Issue Worker for %s", self.config.repository)
        
        if issue_number:
            # Process specific issue
            self._process_single_issue(issue_number)
        else:
            # Process all open issues based on priority
            self._process_all_issues()
            
    def _process_all_issues(self) -> None:
        """Process all open issues by priority."""
        while True:
            try:
                issues = self._get_open_issues()
                if not issues:
                    logger.info("No open issues to process")
                    break
                    
                # Sort by priority labels
                prioritized = self._prioritize_issues(issues)
                
                for issue_data in prioritized:
                    issue = IssueInfo.from_dict(issue_data)
                    if issue.number not in self.processed_issues:
                        success = self._process_issue(issue)
                        if success:
                            self.processed_issues.append(issue.number)
                        time.sleep(60)  # Pause between issues
                        
                # Wait before checking for new issues
                logger.info("Waiting 10 minutes before checking for new issues...")
                time.sleep(600)
                
            except KeyboardInterrupt:
                logger.info("Issue worker interrupted by user")
                break
            except Exception as e:
                logger.error("Error in main loop: %s", e, exc_info=True)
                time.sleep(60)
                
    def _process_single_issue(self, issue_number: int) -> None:
        """Process a single issue."""
        issue_data = self._get_issue_info(issue_number)
        if not issue_data:
            logger.error("Issue #%d not found", issue_number)
            return
            
        issue = IssueInfo.from_dict(issue_data)
        success = self._process_issue(issue)
        if success:
            logger.info("✅ Issue #%d processed successfully", issue_number)
        else:
            logger.warning("⚠️ Issue #%d requires manual review", issue_number)
            
    def _process_issue(self, issue: IssueInfo) -> bool:
        """Process a single issue."""
        logger.info("Processing Issue #%d: %s", issue.number, issue.title)
        
        # Skip if already has PR
        if self._has_linked_pr(issue.number):
            logger.info("Issue #%d already has a PR", issue.number)
            return True
            
        branch_name = f"issue-{issue.number}"
        
        # Create objective for hive-mind
        objective = self._create_issue_objective(issue, branch_name)
        
        try:
            # Spawn hive-mind to work on issue
            logger.info("🐝 Spawning hive-mind for Issue #%d", issue.number)
            
            result = self.process_manager.run_claude_flow(
                objective=objective,
                namespace=f"{self.config.hive_namespace}-issue-{issue.number}",
                agents=self.config.max_agents,
                auto_spawn=True,
                non_interactive=True,
                timeout=7200
            )
            
            # Check if PR was created
            return self._check_pr_created(branch_name, issue.number)
            
        except ProcessError as e:
            logger.error("Failed to process issue: %s", e)
            return False
            
    def _create_issue_objective(self, issue: IssueInfo, branch_name: str) -> str:
        """Create objective for issue processing."""
        return f"""Implement Issue #{issue.number}: {issue.title}

Repository: {self.config.repository}
Branch: {branch_name}

ISSUE DESCRIPTION:
{issue.body}

MANDATORY TASKS:
1. Create branch: {branch_name}
2. Implement complete solution per issue requirements
3. Write comprehensive tests (>80% coverage)
4. Ensure ALL tests pass
5. Update documentation if needed
6. Run linting and fix issues
7. Commit with conventional messages
8. Push branch
9. Create PR with "Closes #{issue.number}"

QUALITY REQUIREMENTS:
- Production-ready code
- Proper error handling
- Input validation
- TypeScript types (no 'any')
- Tests for edge cases
- Security best practices

SUCCESS CRITERIA:
- PR created with all checks passing
- Links to issue #{issue.number}
- Ready for review"""
        
    def _get_open_issues(self) -> List[Dict]:
        """Get all open issues."""
        try:
            cmd = [
                "gh", "issue", "list",
                "--repo", self.config.repository,
                "--state", "open",
                "--json", "number,title,author,state,labels,body",
                "--limit", "100"
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
            
    def _get_issue_info(self, issue_number: int) -> Optional[Dict]:
        """Get information for a specific issue."""
        try:
            cmd = [
                "gh", "issue", "view", str(issue_number),
                "--repo", self.config.repository,
                "--json", "number,title,author,state,labels,body"
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
            logger.error("Failed to get issue info: %s", e)
            return None
            
    def _prioritize_issues(self, issues: List[Dict]) -> List[Dict]:
        """Sort issues by priority labels."""
        def priority_score(issue: Dict) -> int:
            labels = [label.get("name", "").lower() for label in issue.get("labels", [])]
            score = 0
            
            # Priority scoring
            if "critical" in labels or "blocking" in labels:
                score += 1000
            if "high" in labels or "security" in labels:
                score += 500
            if "medium" in labels or "bug" in labels:
                score += 100
            if "low" in labels or "enhancement" in labels:
                score += 10
                
            return -score  # Negative for reverse sort
            
        return sorted(issues, key=priority_score)
        
    def _has_linked_pr(self, issue_number: int) -> bool:
        """Check if issue already has a linked PR."""
        try:
            # Search for PRs that mention this issue
            cmd = [
                "gh", "pr", "list",
                "--repo", self.config.repository,
                "--search", f"#{issue_number} in:body",
                "--json", "number"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            
            prs = json.loads(result.stdout)
            return len(prs) > 0
            
        except Exception as e:
            logger.error("Failed to check for linked PR: %s", e)
            return False
            
    def _check_pr_created(self, branch_name: str, issue_number: int) -> bool:
        """Check if PR was created for the branch."""
        try:
            cmd = [
                "gh", "pr", "list",
                "--repo", self.config.repository,
                "--head", branch_name,
                "--json", "number"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            
            prs = json.loads(result.stdout)
            if prs:
                pr_number = prs[0]["number"]
                logger.info("✅ PR #%d created for Issue #%d", pr_number, issue_number)
                return True
            else:
                logger.warning("No PR created for Issue #%d", issue_number)
                return False
                
        except Exception as e:
            logger.error("Failed to check for PR: %s", e)
            return False