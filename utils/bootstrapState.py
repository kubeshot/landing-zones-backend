import os
import subprocess
import json
from utils.github import push_to_plan_branch

def update_bootstrap_state(update_queue, github_access_token_for_backend, git_org_name, bootstrap_repo,github_access_token):
    try:
        update_queue.put("Infrastructure already exists. Checking for changes...\n\n")

        repo_url = f"https://{github_access_token_for_backend}@github.com/{git_org_name}/{bootstrap_repo}.git"
        local_path = os.path.join("lz_repos", bootstrap_repo)

        os.makedirs("lz_repos", exist_ok=True)

        if os.path.exists(local_path):
            update_queue.put(f"Removing existing repository at {local_path}...\n\n")
            subprocess.run(
                ["rm", "-rf", local_path],
                capture_output=True,
                text=True
            )
            update_queue.put(f"Repository at {local_path} removed.\n\n")

        update_queue.put(f"Cloning repository from {repo_url} to {local_path}...\n\n")
        result = subprocess.run(
            ["git", "clone", repo_url, local_path],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            update_queue.put(f"Error cloning repository: {result.stderr}\n\n")
            return "Error: Failed to clone repository."

        update_queue.put("Repository cloned successfully.\n\n")
        update_queue.put("Analyzing the bootstrap repo...\n\n")

        update_bootstrap_vars(update_queue,bootstrap_repo)

        os.environ["TF_VAR_gh_token"] = github_access_token
        os.chdir(local_path)
        update_queue.put(f"Changed directory to {local_path}.\n\n")

        push_to_plan_branch(update_queue)

        return "Bootstrap state updated successfully."

    except Exception as e:
        update_queue.put(f"Error updating bootstrap state: {str(e)}\n\n")
        return f"Error: {str(e)}"
    
def create_bootstrap_state(update_queue):
    update_queue.put("Creating bootstrap module")
    return 'creating bootstrap state'

def update_bootstrap_vars(update_queue, bootstrap_repo):
    try:
        tfvars_path = os.path.join("lz_repos", bootstrap_repo, "envs", "shared", "terraform.tfvars")
        
        bootstrap_data_path = os.path.join("uploads", "bootstrap_data.json")
        with open(bootstrap_data_path, "r") as f:
            bootstrap_data = json.load(f)

        org_id = bootstrap_data.get("orgId")
        billing_account = bootstrap_data.get("billingAccount")
        billing_project = bootstrap_data.get("billingProject")
        email_domain = bootstrap_data.get("emailDomain")
        git_org_name = bootstrap_data.get("gitOrgName")
        parent_folder = bootstrap_data.get("parentFolderID")
        repos = {
            "bootstrap": bootstrap_data.get("bootstrapRepo"),
            "organization": bootstrap_data.get("organizationRepo"),
            "environments": bootstrap_data.get("environmentsRepo"),
            "networks": bootstrap_data.get("networksRepo"),
            "projects": bootstrap_data.get("projectsRepo"),
        }

        if not os.path.exists(tfvars_path):
            update_queue.put(f"File {tfvars_path} does not exist.\n\n")
            return "Terraform variables file not found."

        with open(tfvars_path, "r") as f:
            tfvars_content = f.readlines()

        updated_content = []
        in_gh_repos = False

        for line in tfvars_content:
            if line.startswith("org_id"):
                updated_content.append(f"org_id = \"{org_id}\"\n")
                update_queue.put(f"Updated org_id to {org_id}.\n\n")

            elif line.startswith("billing_account"):
                updated_content.append(f"billing_account = \"{billing_account}\"\n")
                update_queue.put(f"Updated billing_account to {billing_account}.\n\n")

            elif line.startswith("parent_folder"):
                updated_content.append(f"parent_folder = \"{parent_folder}\"\n")
                update_queue.put(f"Updated parent_folder_id to {parent_folder}.\n\n")
            
            elif "billing_project" in line:
                updated_content.append(f"  billing_project        = \"{billing_project}\"\n")
                update_queue.put(f"Updated billing_project to {billing_project}.\n\n")

            elif "@" in line:
                updated_line = line.split("@", 1)[0] + f"@{email_domain}\"\n"  # Preserve everything before @ and add the new domain
                updated_content.append(updated_line)
                update_queue.put(f"Updated email domain in line: {line.strip()} -> {updated_line.strip()}\n\n")

            elif "gh_repos = {" in line:
                in_gh_repos = True
                updated_content.append(line)
            elif in_gh_repos and "}" in line:
                in_gh_repos = False
                updated_content.append(f"    owner        = \"{git_org_name}\",\n")
                updated_content.append(f"    bootstrap    = \"{repos['bootstrap']}\",\n")
                updated_content.append(f"    organization = \"{repos['organization']}\",\n")
                updated_content.append(f"    environments = \"{repos['environments']}\",\n")
                updated_content.append(f"    networks     = \"{repos['networks']}\",\n")
                updated_content.append(f"    projects     = \"{repos['projects']}\",\n")
                updated_content.append("}\n")
                update_queue.put("Updated gh_repos block.\n\n")
            elif in_gh_repos:
                continue

            else:
                updated_content.append(line)

        with open(tfvars_path, "w") as f:
            f.writelines(updated_content)

        update_queue.put("Terraform variables updated successfully.\n\n")
        return "Terraform variables updated successfully."

    except Exception as e:
        update_queue.put(f"Error updating terraform variables: {str(e)}\n\n")
        return f"Error: {str(e)}"