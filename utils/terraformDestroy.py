from utils.github import check_repo_file,clone_repo
import os,shutil
from utils.copy import copy_folder_contents
from utils.bootstrapState import update_bootstrap_vars
import subprocess
from utils.bootstrapState import strip_ansi_escape_codes

def terraform_destroy_bootstrap(update_queue,github_access_token,github_access_token_for_backend,git_org_name,bootstrap_repo):
    try:
        file_to_check = "envs/shared/terraform.tfvars"
        update_queue.put("Checking the repository...\n\n")
        file_exists = check_repo_file(github_access_token_for_backend, git_org_name, bootstrap_repo, file_to_check)
    except Exception as e:
        error_message = f"Failed to access the repositry"
        update_queue.put(error_message)
        raise Exception(error_message) from e
    
    ## step 1: Check the repo(check if it is empty or it has var file) -- done 

    if file_exists:
        ## clone the bootstrap repo
        try:
            update_queue.put('the file exists')
            bootstrap_repo_url = f"https://{github_access_token_for_backend}@github.com/{git_org_name}/{bootstrap_repo}.git"
            clone_repo(update_queue,bootstrap_repo_url)
        except Exception as e:
            error_message = f"Failed to access the repositry {bootstrap_repo}"
            update_queue.put(error_message)
            raise Exception(error_message) from e
    else:
        ##clone the base repo
        base_repo_url = 'https://github.com/kubeshot/gcp-0-bootstrap-repo.git'
        clone_repo(update_queue,base_repo_url)
        ##update the vars in bootstrap repo
        update_queue.put('the file does not exist')
        target_dir = "lz_repos"
        bootstrap_repo_path = os.path.join(target_dir, bootstrap_repo)
        if os.path.exists(bootstrap_repo_path):
            shutil.rmtree(bootstrap_repo_path)

        os.makedirs(bootstrap_repo_path, exist_ok=True)
        update_queue.put(f"Created directory: {bootstrap_repo_path}\n\n")

        src_path = os.path.join(target_dir,"gcp-0-bootstrap-repo")
        dest_path = os.path.join(target_dir,bootstrap_repo)
        try:
            copy_folder_contents(src_path,dest_path,update_queue)
            update_bootstrap_vars(update_queue,bootstrap_repo)
        except Exception as e:
            error_message = f"Error updating the infrastructure definition or updating the variable values"
            update_queue.put(error_message)
            raise Exception(error_message) from e
    ## step 2: if it has the var file then clone, if not then clone the base repo and update the vars--done 


    state_file_in_destroy_folder_exists = os.path.exists("/app/stateFile/bootstrapDestroy/terraform.tfstate")

    ## try except block ==> to update the backend.tf 
    tf_backend_file_path = os.path.join(target_dir,bootstrap_repo,"envs","shared",'backend.tf')
    try:
        new_backend_config = f""" terraform {{
        backend "local" {{
            path = "terraform.tfstate"
        }}
    }}"""

        with open(tf_backend_file_path, 'w') as f:
            f.write(new_backend_config)

    except Exception as e:
        error_message = f"Error updating the backend configurations"
        update_queue.put(error_message)
        raise Exception(error_message) from e
    

    if file_exists and not state_file_in_destroy_folder_exists:
        update_queue.put('Using the remote state file')
        ## when the file exist but no state file in destroy folder -- run terraform destroy directly (will need state migration)
      
    elif not file_exists and not state_file_in_destroy_folder_exists:
        update_queue.put('Using the local statefile')
        ## when the file doesnot exist and no state file in destory folder --  take state file for stateFile folder
        src_path = "/app/stateFile/terraform.tfstate"
        dest_path = os.path.join(target_dir,bootstrap_repo,"envs","shared")
        shutil.copy(src_path,dest_path)
    else:
        update_queue.put('Using the state file from previous endpoint')
        src_path = "/app/stateFile/bootstrapDestroy/terraform.tfstate"
        dest_path = os.path.join(target_dir,bootstrap_repo,"envs","shared")
        shutil.copy(src_path,dest_path)

    os.chdir(os.path.join(target_dir,bootstrap_repo,"envs","shared"))
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

    try:
        destroy_process = subprocess.run(
            ["terraform", "destroy", '-auto-approve',f"-var=gh_token={github_access_token}"],
            check=True,
            capture_output=True,
            text=True
        )
        update_queue.put("Terraform Destroy Successful.")

    except subprocess.CalledProcessError as e:
        stderr_cleaned = strip_ansi_escape_codes(e.stderr)
        stdout_cleaned = strip_ansi_escape_codes(e.stdout)        
        error_message = f"Terraform Destroy Failed:\nSTDOUT:\n{stdout_cleaned}\n\nSTDERR:\n{stderr_cleaned}"        
        update_queue.put(f"Terraform Destroy failed: STDERR:{stderr_cleaned} STDOUT:{stdout_cleaned}")        
        print(error_message)        
        raise Exception(error_message) from e
    finally:
        src_file = 'terraform.tfstate'
        dest_dir = '/app/stateFile/bootstrapDestroy'
        os.makedirs(dest_dir,exist_ok=True)
        shutil.copy(src_file,dest_dir)
        

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


    os.chdir("/app")


    ## step 3: check in the stateFile/bootstrapdestroy if statefile exists, if it exists then copy it to envs/shared

    ## step 4: Migrate state to local.run terraform destroy and copy the state file to stateFile folder

    ## step 5: remove the prevent_destroy infrastructure from state ==> destroy manually ==> re-run terraform destroy
    return 'ok'



def terraform_destroy_other(update_queue):
    ## step 1: Clone the github repo

    ## step 2: replace the apply pipeline with destroy pipeline

    ## step 3: push to plan and merge with production branch

    ## step 4: update pipeline in case of destroy failed with custom scripts to remove the prevent_destroy infra manually

    return 'ok'