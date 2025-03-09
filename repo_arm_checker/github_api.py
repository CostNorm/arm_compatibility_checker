import os
import base64
import requests
from config import GITHUB_TOKEN


def get_github_headers():
    """Get headers for GitHub API requests."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def get_repository_info(owner, repo):
    """Get basic information about a repository."""
    url = f"https://api.github.com/repos/{owner}/{repo}"
    response = requests.get(url, headers=get_github_headers())

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error getting repository info: {response.status_code}")
        return {}


def get_repository_tree(owner, repo, branch="main"):
    """Get the file tree of a repository."""
    # First, get the branch information to get the latest commit SHA
    branch_url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}"
    branch_response = requests.get(branch_url, headers=get_github_headers())

    if branch_response.status_code != 200:
        print(f"Error getting branch info: {branch_response.status_code}")
        return {}

    branch_data = branch_response.json()
    commit_sha = branch_data.get("commit", {}).get("sha")

    if not commit_sha:
        print("Could not find commit SHA")
        return {}

    # Now, get the tree using the commit SHA
    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{commit_sha}?recursive=1"
    tree_response = requests.get(tree_url, headers=get_github_headers())

    if tree_response.status_code == 200:
        return tree_response.json()
    else:
        print(f"Error getting repository tree: {tree_response.status_code}")
        return {}


def get_file_content(owner, repo, path, branch="main"):
    """Get the content of a specific file."""
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"
    response = requests.get(url, headers=get_github_headers())

    if response.status_code == 200:
        content_data = response.json()
        # GitHub API returns base64 encoded content
        if content_data.get("encoding") == "base64" and content_data.get("content"):
            try:
                decoded_content = base64.b64decode(content_data["content"]).decode(
                    "utf-8"
                )
                return decoded_content
            except Exception as e:
                print(f"Error decoding content: {str(e)}")
        return None
    else:
        print(f"Error getting file content: {response.status_code}")
        return None
