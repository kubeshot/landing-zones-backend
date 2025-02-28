import os
import subprocess
import json
import shutil
from utils.github import push_to_plan_branch,clone_repo
from utils.copy import copy_folder_contents
from config import UPLOAD_FOLDER

def update_bootstrap_state(update_queue, github_access_token_for_backend, git_org_name, bootstrap_repo,github_access_token):
    try:
        main_dir = os.getcwd()
        update_queue.put("Infrastructure already exists. Checking for changes...\n\n")
        bootstrap_repo_url = f"https://{github_access_token_for_backend}@github.com/{git_org_name}/{bootstrap_repo}.git"
        os.makedirs("lz_repos", exist_ok=True)
        local_path = os.path.join("lz_repos",bootstrap_repo_url)
        clone_repo(update_queue,bootstrap_repo_url)
        update_bootstrap_vars(update_queue,bootstrap_repo)

        os.environ["TF_VAR_gh_token"] = github_access_token
        os.chdir(local_path)
        update_queue.put(f"Changed directory to {local_path}.\n\n")

        push_to_plan_branch(update_queue)

        os.chdir(main_dir)


        return "Bootstrap state updated successfully."

    except Exception as e:
        update_queue.put(f"Error updating bootstrap state: {str(e)}\n\n")
        return f"Error: {str(e)}"
    
def create_bootstrap_state(github_access_token_for_backend, git_org_name, update_queue, bootstrap_repo,github_access_token):
    
    update_queue.put("Creating bootstrap module\n\n")
    target_dir = "lz_repos"
    main_dir = os.getcwd()
    uploads_dir = os.path.join(main_dir,UPLOAD_FOLDER)
    os.makedirs(target_dir, exist_ok=True)

    base_repo_url = 'https://github.com/kubeshot/gcp-0-bootstrap-repo.git'
    clone_repo(update_queue,base_repo_url)

    base_repo = 'gcp-0-bootstrap-repo'
    update_bootstrap_vars(update_queue,base_repo)

    os.environ["TF_VAR_gh_token"] = github_access_token

    bootstrap_repo_path = os.path.join(target_dir, bootstrap_repo)
    if os.path.exists(bootstrap_repo_path):
        shutil.rmtree(bootstrap_repo_path)

    os.makedirs(bootstrap_repo_path, exist_ok=True)
    update_queue.put(f"Created directory: {bootstrap_repo_path}\n\n")

    os.chdir(bootstrap_repo_path)
    update_queue.put(f"Changed directory to {bootstrap_repo_path}\n\n")

    subprocess.run(["git", "init"], capture_output=True, text=True)
    update_queue.put("Initialized empty Git repository\n\n")

    bootstrap_repo_url = f"https://{github_access_token_for_backend}@github.com/{git_org_name}/{bootstrap_repo}.git"
    subprocess.run(["git", "remote", "add", "origin", bootstrap_repo_url], capture_output=True, text=True)
    update_queue.put(f"Added remote origin to {bootstrap_repo} repo\n\n")

    subprocess.run(["git", "branch", "-M", "main"], capture_output=True, text=True)
    subprocess.run(["git", "push", "--set-upstream", "origin", "main"], capture_output=True, text=True)
    update_queue.put("Pushed empty commit to main branch\n\n")

    subprocess.run(["git", "checkout", "-b", "production"], capture_output=True, text=True)
    subprocess.run(["git", "push", "--set-upstream", "origin", "production"], capture_output=True, text=True)
    update_queue.put("Created and pushed production branch\n\n")

    subprocess.run(["git", "checkout", "-b", "plan"], capture_output=True, text=True)
    update_queue.put("Created plan branch\n\n")

    os.chdir(main_dir)
    update_queue.put(f'changed to {main_dir} \n\n')

    src_path = os.path.join(target_dir,base_repo)
    dest_path = os.path.join(bootstrap_repo_path)
    copy_folder_contents(src_path,dest_path,update_queue)

    terraform_dir = os.path.join(bootstrap_repo_path,"envs","shared")
    update_queue.put(f'{terraform_dir} is current dir')
    os.chdir(terraform_dir)
    update_queue.put(f'Terraform init ...')

    try:
        result = subprocess.run(["terraform", "init"], capture_output=True, text=True)
        update_queue.put(f"Terraform init output:\n{result.stdout}")
        print(f"Terraform init output:\n{result.stdout}")

        update_queue.put("Terraform init Done")
        
    except subprocess.CalledProcessError as e:
        update_queue.put(f"Terraform init failed: {e.stderr}")
        print(f"Terraform init failed: {e.stderr}")

    plan_output_file = os.path.join("plan.out")
    json_output_file = os.path.join(uploads_dir, "plan.json")
    if not os.path.exists(json_output_file):
        with open(json_output_file, "w") as f:
            json.dump({}, f)

    update_queue.put("Generating Plan ...")
    try:
        plan_process = subprocess.run(
            ["terraform", "plan", f"-out={plan_output_file}", f"-var=gh_token={github_access_token}"],
            check=True,
            capture_output=True,
            text=True
        )
        update_queue.put("Terraform Plan Generated Successfully.")
    except subprocess.CalledProcessError as e:
        update_queue.put(f"Terraform Plan Failed: {e.stderr}")  
        print(f"Terraform Plan Failed: {e.stderr}")
        raise  

    try:
        with open(json_output_file, "w") as json_file:
            subprocess.run(
                ["terraform", "show", "-json", plan_output_file],
                check=True,
                stdout=json_file,  
                stderr=subprocess.PIPE, 
                text=True 
            )
        update_queue.put("Terraform Plan Converted to JSON Successfully.")
    except subprocess.CalledProcessError as e:
        update_queue.put(f"Terraform Show Failed: {e.stderr}")
        print(f"Terraform Show Failed: {e.stderr}")
        raise

    update_queue.put("Plan has been generated")
    os.chdir(main_dir)


    return "Bootstrap state creation complete."



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

    except Exception as e:
        update_queue.put(f"Error updating terraform variables: {str(e)}\n\n")
        return f"Error: {str(e)}"

    try:
        file_path = os.path.join("lz_repos", bootstrap_repo, "envs", "shared", "github.tf")
        if not os.path.exists(file_path):
            update_queue.put(f"File {file_path} does not exist.\n\n")
            return "Error: File not found."

        with open(file_path, "r") as f:
            lines = f.readlines()

        updated_lines = []
        for line in lines:
            if 'attribute_condition = "assertion.repository_owner ==' in line:
                updated_line = line.replace("/GIT ORG NAME/", git_org_name)
                update_queue.put(f"Updated line: {line.strip()} -> {updated_line.strip()}\n\n")
                updated_lines.append(updated_line)
            else:
                updated_lines.append(line)

        with open(file_path, "w") as f:
            f.writelines(updated_lines)

        update_queue.put("Updated github.tf successfully.\n\n")
    except Exception as e:
        update_queue.put(f"Error updating github.tf: {str(e)}\n\n")
        return f"Error: {str(e)}"
    
    try:
        provider_tf_path = os.path.join("lz_repos", bootstrap_repo, "envs", "shared", "provider.tf")
        service_account_path = os.path.join('/app', 'uploads', 'sa_key.json')
        bootstrap_data_path = os.path.join('/app','uploads','bootstrap_data.json')
        def get_project_id():
            try:
                with open(bootstrap_data_path, 'r') as f:
                    data = json.load(f)
                    project_id = data.get('billingProject')
                    
                    if project_id:
                        return project_id
                    else:
                        raise KeyError("billingProject  not found in the JSON file.")
            
            except FileNotFoundError:
                print(f"Error: The file {bootstrap_data_path} was not found.")
            except json.JSONDecodeError:
                print("Error: Failed to decode the JSON file.")
            except KeyError as e:
                print(e)

        project_id = get_project_id()
        provider_tf_content = f"""
            provider "google" {{
            credentials = "{service_account_path}"  
            project     = "{project_id}"            
            region      = "northamerica-northeast1"                
            }}

            provider "google-beta" {{
            credentials = "{service_account_path}"  
            project     = "{project_id}"           
            region      = "northamerica-northeast1"              
            }}
            """
        
        if os.path.exists(provider_tf_path):
            # Open the provider.tf file and write the new content
            with open(provider_tf_path, 'w') as f:
                f.write(provider_tf_content)
            update_queue.put(f'provider block updated')
        else:
            # If the file doesn't exist, create and write the content
            with open(provider_tf_path, 'w') as f:
                f.write(provider_tf_content)
            update_queue.put(f'provider block failed to update')


    except Exception as e:
        update_queue.put(f"Error updating provider.tf: {str(e)}\n\n")
        return f"Error: {str(e)}"
    
    return "Terraform variables updated successfully."
