import requests
import subprocess
import os

def check_repo_file(github_access_token, git_org_name, bootstrap_repo, file_path):
    url = f"https://api.github.com/repos/{git_org_name}/{bootstrap_repo}/contents/{file_path}"
    headers = {
        "Authorization": f"token {github_access_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    
    response = requests.get(url, headers=headers)

    try:
        response_data = response.json() 
    except requests.exceptions.JSONDecodeError:
        response_data = {"error": "Invalid JSON response from GitHub"}

    return response.status_code==200


def clone_repo(update_queue, repo_url):
    repo_name = repo_url.split("/")[-1].replace(".git", "") 
    local_path = os.path.join("lz_repos", repo_name) 
    if os.path.exists(local_path):
        update_queue.put(f"Removing existing repository at {local_path}...\n\n")
        subprocess.run(["rm", "-rf", local_path], capture_output=True, text=True)
        update_queue.put(f"Repository at {local_path} removed.\n\n")

    update_queue.put(f"Cloning repository from {repo_url} to {local_path}...\n\n")
    result = subprocess.run(["git", "clone", repo_url, local_path], capture_output=True, text=True)

    if result.returncode != 0:
        if "repository is empty" in result.stderr or "does not appear to be a git repository" in result.stderr:
            update_queue.put(f"Warning: The repository {repo_url} is empty. Creating an empty folder instead.\n\n")
            os.makedirs(local_path, exist_ok=True)  
            return f"Warning: Repository {repo_name} is empty. Created an empty folder."
        update_queue.put(f"Error cloning repository: {result.stderr}\n\n")
        return "Error: Failed to clone repository."

    update_queue.put(f"Successfully Cloned: {repo_url}\n\n")
    update_queue.put("Analyzing the repo...\n\n")
    return "Success"


def push_to_plan_branch(update_queue):
        update_queue.put("Checking out or creating the 'plan' branch...\n\n")
        subprocess.run(
            ["git", "checkout", "-b", "plan"],
            capture_output=True,
            text=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Automated"],
            capture_output=True,
            text=True
        )
        subprocess.run(
            ["git", "config", "user.email", "actions@github.com"],
            capture_output=True,
            text=True
        )

        update_queue.put("Staging all changes...\n\n")
        subprocess.run(
            ["git", "add", "."],
            capture_output=True,
            text=True
        )

        commit_message = "Updated bootstrap variables and Terraform configuration"
        update_queue.put(f"Committing changes with message: {commit_message}\n\n")
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            capture_output=True,
            text=True
        )

        update_queue.put("Pushing changes to the 'plan' branch...\n\n")
        push_result = subprocess.run(
            ["git", "push", "origin", "plan"],
            capture_output=True,
            text=True
        )

        if push_result.returncode != 0:
            update_queue.put(f"Error pushing changes: {push_result.stderr}\n\n")
            return "Error: Failed to push changes to the 'plan' branch."

        update_queue.put("Changes pushed to the 'plan' branch successfully.\n\n")
