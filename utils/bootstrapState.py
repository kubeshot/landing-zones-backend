import os
import re
import subprocess
import json
import shutil
from utils.github import push_to_plan_branch,clone_repo
from utils.copy import copy_folder_contents
from config import UPLOAD_FOLDER
from flask import jsonify

def strip_ansi_escape_codes(text):
    """Remove ANSI escape codes from a string."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)

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
        stderr_cleaned = strip_ansi_escape_codes(e.stderr)
        stdout_cleaned = strip_ansi_escape_codes(e.stdout)
        
        error_message = f"Terraform Plan Failed:\nSTDOUT:\n{stdout_cleaned}\n\nSTDERR:\n{stderr_cleaned}"
        
        update_queue.put(f"Terraform Plan failed: STDERR:{stderr_cleaned} STDOUT:{stdout_cleaned}")
        
        print(error_message)
        
        raise Exception(error_message) from e
    

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

def apply_and_migrate_bootstrap_state(update_queue):
    update_queue.put('terraform apply .... This may take a while, Please wait')
    bootstrap_data_path = "/app/uploads/bootstrap_data.json"
    gh_token_path = "/app/uploads/gh_token.txt"

    try:
        with open(bootstrap_data_path, "r") as bootstrap_file:
            bootstrap_data = json.load(bootstrap_file)
            bootstrap_repo = bootstrap_data.get("bootstrapRepo")
            if not bootstrap_repo:
                raise ValueError("bootstrapRepo not found in bootstrap_data.json")
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {bootstrap_data_path}")
    except json.JSONDecodeError:
        raise ValueError(f"Invalid JSON in file: {bootstrap_data_path}")  
    
    try:
        with open(gh_token_path, "r") as gh_token_file:
            github_access_token = gh_token_file.read().strip()
            if not github_access_token:
                raise ValueError("GitHub token is empty in gh_token.txt")
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {gh_token_path}")
    
    terraform_main_path = f"/app/lz_repos/{bootstrap_repo}/envs/shared"
    app_path = f"/app"
    if not os.path.exists('/app/stateFile'):
        os.makedirs('/app/stateFile')

    if os.path.exists(os.path.join(app_path,'stateFile','terraform.tfstate')):
        update_queue.put(f"State file already exists... Continuing the apply process from last endpoint")        
        shutil.copy(os.path.join(app_path,'stateFile','terraform.tfstate'), terraform_main_path)

    os.chdir(terraform_main_path)
    try:
        apply_process = subprocess.run(
            ["terraform", "destroy", '-auto-approve',f"-var=gh_token={github_access_token}"],
            check=True,
            capture_output=True,
            text=True
        )
        update_queue.put("Terraform Apply Successful.")

        output_process = subprocess.run(
            ["terraform", "output", "-json"],
            check=True,
            capture_output=True,
            text=True
        )
        
        with open("outputs.json", "w") as f:
            f.write(output_process.stdout)

        shutil.copy("outputs.json", "/app/stateFile/outputs.json")
        update_queue.put("Terraform output saved and copied to /app/stateFile.")
    except subprocess.CalledProcessError as e:
        stderr_cleaned = strip_ansi_escape_codes(e.stderr)
        stdout_cleaned = strip_ansi_escape_codes(e.stdout)
        
        error_message = f"Terraform Apply Failed:\nSTDOUT:\n{stdout_cleaned}\n\nSTDERR:\n{stderr_cleaned}"
        
        update_queue.put(f"Terraform Apply failed: STDERR:{stderr_cleaned} STDOUT:{stdout_cleaned}")
        
        print(error_message)
        
        raise Exception(error_message) from e
    
    source_file = "terraform.tfstate"  
    destination_dir = "/app/stateFile"  
    try:
        shutil.copy(source_file, destination_dir)
        update_queue.put(f"File '{source_file}' copied to '{destination_dir}' successfully.")
    except Exception as e:
        error_message = f"Failed to copy '{source_file}' to '{destination_dir}': {str(e)}"
        update_queue.put(error_message)
        raise Exception(error_message) from e
    
    json_file_path = '/app/stateFile/outputs.json'
    tf_file_path = os.path.join(terraform_main_path,'backend.tf')
    gcs_bucket = '/REPLACE/' 
    try:
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r') as f:
                data = json.load(f)
            
            if 'gcs_bucket_tfstate' in data:
                gcs_bucket_tfstate = data['gcs_bucket_tfstate']
                if isinstance(gcs_bucket_tfstate, dict) and 'value' in gcs_bucket_tfstate:
                    gcs_bucket = gcs_bucket_tfstate['value']
                else:
                    update_queue.put("'gcs_bucket_tfstate' key exists in outputs.json but does not contain a valid value.")
            else:
                update_queue.put("'gcs_bucket_tfstate' key not found in outputs.json. Using default value.")
        else:
            update_queue.put(f"File not found: {json_file_path}. Using default value.")

        new_backend_config = f""" terraform {{
        backend "gcs" {{
            bucket = "{gcs_bucket}"
            prefix = "terraform/bootstrap/state"
        }}
    }}"""

        with open(tf_file_path, 'w') as f:
            f.write(new_backend_config)
        
        update_queue.put(f"backend.tf updated with GCS bucket: {gcs_bucket}")

    except Exception as e:
        update_queue.put(f"Error: {e}")
        raise Exception from e

    update_queue.put('Migrating the state to backend')
    try:
        init_process = subprocess.run(
            ["terraform", "init", "-migrate-state"],
            check=True,
            capture_output=True,
            text=True
        )
        update_queue.put("Terraform Init - Migrate Successful.")
        
    except subprocess.CalledProcessError as e:
        stderr_cleaned = strip_ansi_escape_codes(e.stderr)
        stdout_cleaned = strip_ansi_escape_codes(e.stdout)
        
        error_message = f"Terraform Init - Migrate Failed:\nSTDOUT:\n{stdout_cleaned}\n\nSTDERR:\n{stderr_cleaned}"
        
        update_queue.put(f"Terraform Init - Migrate failed: STDERR:{stderr_cleaned} STDOUT:{stdout_cleaned}")
        
        print(error_message)
        
        raise Exception(error_message) from e
    

    os.chdir(app_path)
    local_path = os.path.join('/app','lz_repos',bootstrap_repo)
    os.chdir(local_path)
    update_queue.put(f"Changed directory to {local_path}.\n\n")
    update_queue.put(f"pushing to paln branch")
    # push_to_plan_branch(update_queue)

    os.chdir(app_path)
    
    return 'ok'

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
            with open(provider_tf_path, 'w') as f:
                f.write(provider_tf_content)
            update_queue.put(f'provider block updated')
        else:
            with open(provider_tf_path, 'w') as f:
                f.write(provider_tf_content)
            update_queue.put(f'provider block failed to update')


    except Exception as e:
        update_queue.put(f"Error updating provider.tf: {str(e)}\n\n")
        return f"Error: {str(e)}"
    
    return "Terraform variables updated successfully."
