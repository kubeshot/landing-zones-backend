import requests
import subprocess

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

def push_to_plan_branch(update_queue):
            # Checkout the `plan` branch (create it if it doesn't exist)
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
