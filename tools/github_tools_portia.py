import logging
from typing import Dict, Any, Optional

from github import Github
from portia import ToolRunContext
from portia.tool import Tool
from pydantic import BaseModel, Field

import config

logger = logging.getLogger(__name__)


class GitHubManager:
    """Enhanced GitHub manager for sophisticated issue management."""
    
    def __init__(self):
        self.github_client = None
        self.repo = None
        self._setup_github()
    
    def _setup_github(self):
        """Initialize GitHub client."""
        try:
            if not config.GITHUB_TOKEN:
                logger.error("GitHub token not configured")
                return
            
            self.github_client = Github(config.GITHUB_TOKEN)
            logger.info("✅ GitHub client initialized")
            
        except Exception as e:
            logger.error(f"GitHub setup failed: {e}")
    
    def _get_repo(self, repo_name: str = None):
        """Get repository instance."""
        if not self.github_client:
            raise Exception("GitHub client not initialized")
        
        # Use configured repo or provided repo name
        repo_name = repo_name or getattr(config, 'GITHUB_REPO', 'kunal-004/triage-ninja')
        
        try:
            self.repo = self.github_client.get_repo(repo_name)
            return self.repo
        except Exception as e:
            logger.error(f"Failed to get repo {repo_name}: {e}")
            raise
    
    def add_label(self, issue_number: int, label: str, repo_name: str = None) -> bool:
        """Add label to GitHub issue."""
        try:
            repo = self._get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            
            # Check if label exists in repo, create if not
            try:
                existing_label = repo.get_label(label)
                logger.info(f"Label '{label}' already exists")
            except Exception as label_error:
                # Create label if it doesn't exist
                logger.info(f"Creating new label: {label}")
                colors = {
                    "Critical": "d73a4a",  # Red
                    "High": "ff6600",      # Orange  
                    "Medium": "ffcc00",    # Yellow
                    "Low": "00cc66",       # Green
                    "Info": "0099cc",      # Blue
                    "duplicate": "cccccc"  # Gray
                }
                color = colors.get(label, "ffffff")
                try:
                    repo.create_label(label, color)
                    logger.info(f"✅ Created new label: {label}")
                except Exception as create_error:
                    logger.warning(f"Failed to create label '{label}': {create_error}")
                    # Continue anyway - maybe label exists but get_label failed
            
            # Add label to issue
            issue.add_to_labels(label)
            logger.info(f"✅ Added label '{label}' to issue #{issue_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add label '{label}' to issue #{issue_number}: {e}")
            return False
    
    def post_comment(self, issue_number: int, comment: str, repo_name: str = None) -> bool:
        """Post comment to GitHub issue."""
        try:
            repo = self._get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            
            issue.create_comment(comment)
            logger.info(f"✅ Posted comment to issue #{issue_number}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to post comment to issue #{issue_number}: {e}")
            return False
    
    def close_issue(self, issue_number: int, reason: str = "completed", repo_name: str = None) -> bool:
        """Close GitHub issue with reason."""
        try:
            repo = self._get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            
            # Close with reason (GitHub API supports: completed, not_planned)
            if reason == "duplicate":
                reason = "not_planned"  # GitHub doesn't have 'duplicate' reason
            
            issue.edit(state="closed", state_reason=reason)
            logger.info(f"✅ Closed issue #{issue_number} (reason: {reason})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to close issue #{issue_number}: {e}")
            return False
    
    def get_issue(self, issue_number: int, repo_name: str = None) -> Optional[Dict[str, Any]]:
        """Get issue information."""
        try:
            repo = self._get_repo(repo_name)
            issue = repo.get_issue(issue_number)
            
            return {
                'number': issue.number,
                'title': issue.title,
                'body': issue.body,
                'state': issue.state,
                'labels': [label.name for label in issue.labels],
                'html_url': issue.html_url
            }
            
        except Exception as e:
            logger.error(f"Failed to get issue #{issue_number}: {e}")
            return None


# Global GitHub manager instance
github_manager = GitHubManager()


class AddLabelSchema(BaseModel):
    """Input schema for adding labels to issues."""
    issue_number: int = Field(..., description="GitHub issue number")
    label: str = Field(..., description="Label to add to the issue")
    repo_name: Optional[str] = Field(default=None, description="Repository name (owner/repo)")


class AddCommentSchema(BaseModel):
    """Input schema for adding comments to issues."""
    issue_number: int = Field(..., description="GitHub issue number")
    comment: str = Field(..., description="Comment text to add")
    repo_name: Optional[str] = Field(default=None, description="Repository name (owner/repo)")


class CloseIssueSchema(BaseModel):
    """Input schema for closing issues."""
    issue_number: int = Field(..., description="GitHub issue number")
    reason: str = Field(default="completed", description="Reason for closing: completed, not_planned, duplicate")
    repo_name: Optional[str] = Field(default=None, description="Repository name (owner/repo)")


class GitHubAddLabelTool(Tool[str]):
    """Tool for adding labels to GitHub issues."""
    
    id: str = "github_add_label_tool"
    name: str = "GitHub Add Label Tool"
    description: str = "Adds labels to GitHub issues"
    args_schema: type[BaseModel] = AddLabelSchema

    def run(self, context: ToolRunContext, issue_number: int, label: str, repo_name: Optional[str] = None) -> str:
        """Add label to GitHub issue."""
        try:
            success = github_manager.add_label(issue_number, label, repo_name)
            if success:
                return f"✅ Added label '{label}' to issue #{issue_number}"
            else:
                return f"❌ Failed to add label '{label}' to issue #{issue_number}"
        except Exception as e:
            return f"❌ Error adding label: {e}"


class GitHubAddCommentTool(Tool[str]):
    """Tool for adding comments to GitHub issues."""
    
    id: str = "github_add_comment_tool"
    name: str = "GitHub Add Comment Tool"
    description: str = "Adds comments to GitHub issues"
    args_schema: type[BaseModel] = AddCommentSchema

    def run(self, context: ToolRunContext, issue_number: int, comment: str, repo_name: Optional[str] = None) -> str:
        """Add comment to GitHub issue."""
        try:
            success = github_manager.post_comment(issue_number, comment, repo_name)
            if success:
                return f"✅ Posted comment to issue #{issue_number}"
            else:
                return f"❌ Failed to post comment to issue #{issue_number}"
        except Exception as e:
            return f"❌ Error posting comment: {e}"


class GitHubCloseIssueTool(Tool[str]):
    """Tool for closing GitHub issues."""
    
    id: str = "github_close_issue_tool"
    name: str = "GitHub Close Issue Tool"
    description: str = "Closes GitHub issues with specified reason"
    args_schema: type[BaseModel] = CloseIssueSchema

    def run(self, context: ToolRunContext, issue_number: int, reason: str = "completed", repo_name: Optional[str] = None) -> str:
        """Close GitHub issue."""
        try:
            success = github_manager.close_issue(issue_number, reason, repo_name)
            if success:
                return f"✅ Closed issue #{issue_number} (reason: {reason})"
            else:
                return f"❌ Failed to close issue #{issue_number}"
        except Exception as e:
            return f"❌ Error closing issue: {e}"

    def _setup_github(self):
        """Initialize GitHub client."""
        try:
            self.github_client = Github(config.GITHUB_TOKEN)
            self.repo = self.github_client.get_repo(config.GITHUB_REPO)
            logger.info(f"Initialized GitHub manager for repository: {config.GITHUB_REPO}")
        except Exception as e:
            logger.error(f"Failed to initialize GitHub client: {e}")
            # Don't raise - let the tool handle errors gracefully

    def run(self, context: ToolRunContext, issue_number: int, label: str) -> str:
        """
        Perform GitHub operations on issues.
        
        Args:
            context: Portia tool run context
            issue_number: GitHub issue number
            label: Label to add to issue
            
        Returns:
            Result of the operation
        """
        try:
            if not self.repo:
                return f"GitHub not configured - cannot add label to issue #{issue_number}"
            
            issue = self.repo.get_issue(issue_number)
            issue.add_to_labels(label)
            result = f"Added label '{label}' to issue #{issue_number}"
            
            logger.info(result)
            return result
            
        except Exception as e:
            error_msg = f"GitHub operation failed for issue #{issue_number}: {e}"
            logger.error(error_msg)
            return error_msg


class GitHubLabelTool(Tool[str]):
    """Specialized tool for adding labels to GitHub issues."""
    
    id: str = "github_label_tool"
    name: str = "GitHub Label Tool"
    description: str = "Adds labels to GitHub issues"
    args_schema: type[BaseModel] = AddLabelSchema
    output_schema: tuple[str, str] = ("string", "Result of adding the label")

    def __init__(self):
        super().__init__()

    def run(self, context: ToolRunContext, issue_number: int, label: str) -> str:
        """Add a label to a GitHub issue."""
        try:
            if not hasattr(self, 'github_client'):
                self.github_client = Github(config.GITHUB_TOKEN)
                self.repo = self.github_client.get_repo(config.GITHUB_REPO)
            
            issue = self.repo.get_issue(issue_number)
            issue.add_to_labels(label)
            result = f"Added label '{label}' to issue #{issue_number}"
            logger.info(result)
            return result
        except Exception as e:
            error_msg = f"Failed to add label to issue #{issue_number}: {e}"
            logger.error(error_msg)
            return error_msg


class GitHubCommentTool(Tool[str]):
    """Specialized tool for adding comments to GitHub issues."""
    
    id: str = "github_comment_tool"
    name: str = "GitHub Comment Tool"
    description: str = "Adds comments to GitHub issues"
    args_schema: type[BaseModel] = AddCommentSchema
    output_schema: tuple[str, str] = ("string", "Result of adding the comment")

    def __init__(self):
        super().__init__()

    def run(self, context: ToolRunContext, issue_number: int, comment: str) -> str:
        """Add a comment to a GitHub issue."""
        try:
            if not hasattr(self, 'github_client'):
                self.github_client = Github(config.GITHUB_TOKEN)
                self.repo = self.github_client.get_repo(config.GITHUB_REPO)
            
            issue = self.repo.get_issue(issue_number)
            issue.create_comment(comment)
            result = f"Added comment to issue #{issue_number}"
            logger.info(result)
            return result
        except Exception as e:
            error_msg = f"Failed to add comment to issue #{issue_number}: {e}"
            logger.error(error_msg)
            return error_msg


class GitHubCloseTool(Tool[str]):
    """Specialized tool for closing GitHub issues."""
    
    id: str = "github_close_tool"
    name: str = "GitHub Close Tool"
    description: str = "Closes GitHub issues"
    args_schema: type[BaseModel] = CloseIssueSchema
    output_schema: tuple[str, str] = ("string", "Result of closing the issue")

    def __init__(self):
        super().__init__()

    def run(self, context: ToolRunContext, issue_number: int, reason: str = "completed") -> str:
        """Close a GitHub issue."""
        try:
            if not hasattr(self, 'github_client'):
                self.github_client = Github(config.GITHUB_TOKEN)
                self.repo = self.github_client.get_repo(config.GITHUB_REPO)
            
            issue = self.repo.get_issue(issue_number)
            issue.edit(state="closed")
            result = f"Closed issue #{issue_number} (reason: {reason})"
            logger.info(result)
            return result
        except Exception as e:
            error_msg = f"Failed to close issue #{issue_number}: {e}"
            logger.error(error_msg)
            return error_msg
