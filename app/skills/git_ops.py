"""
Git Operations Skill Module - DevOps Agent Toolset
===================================================
Provides git-related operations for the AI Engineering Team.
These functions can be called by Gemini via Function Calling.
"""

import subprocess
import os
from typing import Dict, Any

def git_status(repo_path: str = ".") -> Dict[str, Any]:
    """
    Returns the current git status of a repository.
    Shows modified, staged, and untracked files.
    
    Args:
        repo_path: Path to the git repository. Defaults to current directory.
    
    Returns:
        dict: Status information including branch, modified files, and staged files.
    """
    try:
        # Get current branch
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=repo_path
        ).stdout.strip()
        
        # Get status (short format)
        status_output = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=repo_path
        ).stdout.strip()
        
        modified = []
        staged = []
        untracked = []
        
        for line in status_output.split("\n"):
            if not line:
                continue
            status_code = line[:2]
            filename = line[3:]
            
            if status_code[0] != " " and status_code[0] != "?":
                staged.append(filename)
            if status_code[1] == "M":
                modified.append(filename)
            if status_code == "??":
                untracked.append(filename)
        
        return {
            "success": True,
            "branch": branch,
            "modified_files": modified,
            "staged_files": staged,
            "untracked_files": untracked[:10],  # Limit untracked to 10
            "total_changes": len(modified) + len(staged)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def git_log(repo_path: str = ".", count: int = 5) -> Dict[str, Any]:
    """
    Returns the recent commit history.
    
    Args:
        repo_path: Path to the git repository.
        count: Number of commits to retrieve (max 20).
    
    Returns:
        dict: List of recent commits with hash, author, date, and message.
    """
    try:
        count = min(count, 20)  # Safety limit
        
        log_output = subprocess.run(
            ["git", "log", f"--max-count={count}", "--pretty=format:%h|%an|%ar|%s"],
            capture_output=True, text=True, cwd=repo_path
        ).stdout.strip()
        
        commits = []
        for line in log_output.split("\n"):
            if not line:
                continue
            parts = line.split("|", 3)
            if len(parts) == 4:
                commits.append({
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3]
                })
        
        return {"success": True, "commits": commits, "count": len(commits)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def git_diff_summary(repo_path: str = ".") -> Dict[str, Any]:
    """
    Returns a summary of uncommitted changes (lines added/removed per file).
    
    Args:
        repo_path: Path to the git repository.
    
    Returns:
        dict: Diff statistics per file.
    """
    try:
        diff_output = subprocess.run(
            ["git", "diff", "--stat"],
            capture_output=True, text=True, cwd=repo_path
        ).stdout.strip()
        
        return {
            "success": True,
            "diff_summary": diff_output if diff_output else "No uncommitted changes.",
            "has_changes": bool(diff_output)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def git_add_and_commit(repo_path: str = ".", message: str = "Auto-commit by DevOps Agent") -> Dict[str, Any]:
    """
    Stages all changes and creates a commit.
    USE WITH CAUTION: This modifies the repository state.
    
    Args:
        repo_path: Path to the git repository.
        message: Commit message.
    
    Returns:
        dict: Result of the commit operation.
    """
    try:
        # Stage all changes
        add_result = subprocess.run(
            ["git", "add", "."],
            capture_output=True, text=True, cwd=repo_path
        )
        if add_result.returncode != 0:
            return {"success": False, "error": f"git add failed: {add_result.stderr}"}
        
        # Commit
        commit_result = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True, text=True, cwd=repo_path
        )
        
        if commit_result.returncode != 0:
            if "nothing to commit" in commit_result.stdout:
                return {"success": True, "message": "Nothing to commit, working tree clean."}
            return {"success": False, "error": commit_result.stderr}
        
        return {
            "success": True,
            "message": "Commit created successfully.",
            "output": commit_result.stdout.strip()
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def git_current_branch(repo_path: str = ".") -> str:
    """
    Returns just the current branch name.
    
    Args:
        repo_path: Path to the git repository.
    
    Returns:
        str: The current branch name.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=repo_path
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception as e:
        return f"Error: {e}"
