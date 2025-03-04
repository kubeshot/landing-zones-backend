from flask import Blueprint, request, jsonify, Response, send_file
from flask_cors import CORS  
from utils.github import check_repo_file
from utils.bootstrapState import create_bootstrap_state, update_bootstrap_state
from config import TOKEN_FILE_PATH, UPLOAD_FOLDER, TOKEN_FILE_PATH_BACKEND
import os
import json
import queue
from werkzeug.utils import secure_filename
from utils.bootstrapState import apply_and_migrate_bootstrap_state
from utils.terraformDestroy import terraform_destroy_bootstrap

bootstrap_bp = Blueprint('bootstrap', __name__)
CORS(bootstrap_bp, resources={r"/*": {"origins": "*"}})  

update_queue = queue.Queue()

@bootstrap_bp.route('/bootstrap', methods=['POST'])
def bootstrap():
    os.chdir('/app')
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data received"}), 400

        github_access_token = data.pop('githubAccessToken', None)
        github_access_token_for_backend = data.pop('githubAccessTokenForBackend', None)

        if not github_access_token and not github_access_token_for_backend:
            return jsonify({"error": "GitHub access token is required"}), 400

        with open(TOKEN_FILE_PATH, 'w') as f:
            f.write(github_access_token)
        with open(TOKEN_FILE_PATH_BACKEND, 'w') as f:
            f.write(github_access_token_for_backend)

        os.chmod(TOKEN_FILE_PATH, 0o600)
        os.chmod(TOKEN_FILE_PATH_BACKEND, 0o600)

        filename = secure_filename("bootstrap_data.json")
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)


        git_org_name = data.get('gitOrgName')
        bootstrap_repo = data.get('bootstrapRepo')

        if not git_org_name or not bootstrap_repo:
            return jsonify({"error": "gitOrgName or bootstrapRepo missing in data"}), 400

        file_to_check = "envs/shared/terraform.tfvars"

        update_queue.put("Checking the repository...\n\n")

        file_exists = check_repo_file(github_access_token_for_backend, git_org_name, bootstrap_repo, file_to_check)

        if file_exists:
            message = "Repository already initialized. Checking for changes"
            update_queue.put(f"{message}\n\n")
            update_bootstrap_state(update_queue,github_access_token_for_backend,git_org_name,bootstrap_repo,github_access_token)
        else:
            message = "Repository is empty. Initializing the Repositories"
            update_queue.put(f"{message}\n\n")
            create_bootstrap_state(github_access_token_for_backend,git_org_name,update_queue,bootstrap_repo,github_access_token)

        return jsonify({
            "status": "success",
            "message": message
        }), 200

    except Exception as e:
        update_queue.put(f"Error: {str(e)}\n\n")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    
@bootstrap_bp.route('/bootstrap/apply', methods=['POST'])
def bootstrap_apply_route():
    os.chdir('/app')
    try:
        update_queue.put("Starting bootstrap apply process...\n\n")
        apply_and_migrate_bootstrap_state(update_queue)

        return jsonify({"status": "success", "message": "Bootstrap apply initiated."}), 200
    except Exception as e:
        update_queue.put(f"Error: {str(e)}\n\n")
        return jsonify({"status": "error", "message": str(e)}), 500
    
@bootstrap_bp.route('/bootstrap/destroy', methods=['POST'])
def bootstrap_destroy_route():
    os.chdir('/app')
    try:
        update_queue.put("Starting bootstrap destroy process...\n\n")

        data = request.get_json()

        if not data:
            return jsonify({"error": "No data received"}), 400

        github_access_token = data.pop('githubAccessToken', None)
        github_access_token_for_backend = data.pop('githubAccessTokenForBackend', None)

        if not github_access_token and not github_access_token_for_backend:
            return jsonify({"error": "GitHub access token is required"}), 400

        with open(TOKEN_FILE_PATH, 'w') as f:
            f.write(github_access_token)
        with open(TOKEN_FILE_PATH_BACKEND, 'w') as f:
            f.write(github_access_token_for_backend)

        os.chmod(TOKEN_FILE_PATH, 0o600)
        os.chmod(TOKEN_FILE_PATH_BACKEND, 0o600)

        filename = secure_filename("bootstrap_data.json")
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)


        git_org_name = data.get('gitOrgName')
        bootstrap_repo = data.get('bootstrapRepo')

        if not git_org_name or not bootstrap_repo:
            return jsonify({"error": "gitOrgName or bootstrapRepo missing in data"}), 400
        
        terraform_destroy_bootstrap(update_queue,github_access_token,github_access_token_for_backend,git_org_name,bootstrap_repo)

        return jsonify({"status": "success", "message": "Bootstrap destroy initiated."}), 200
    except Exception as e:
        update_queue.put(f"Error: {str(e)}\n\n")
        return jsonify({"status": "error", "message": str(e)}), 500

@bootstrap_bp.route('/bootstrap-stream')
def bootstrap_stream():
    def generate():
        while True:
            try:
                message = update_queue.get(timeout=10000)  
                yield f"data: {message}\n\n"
            except queue.Empty:
                break  

    return Response(generate(), mimetype='text/event-stream')


@bootstrap_bp.route('/bootstrap/downloadplan', methods=['GET', 'OPTIONS'])
def download_plan():
    os.chdir('/app')
    try:
        plan_file_path = os.path.join(UPLOAD_FOLDER, 'plan.json')  

        if not os.path.exists(plan_file_path):
            return jsonify({"error": "Plan file not found"}), 404

        return send_file(
            plan_file_path,
            as_attachment=True,  
            download_name="bootstrap_plan.json"  
        )

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500