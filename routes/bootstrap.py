from flask import Blueprint, request, jsonify, Response
from flask_cors import CORS  
from utils.github import check_repo_file
from utils.bootstrapState import create_bootstrap_state,update_bootstrap_state
from config import TOKEN_FILE_PATH, UPLOAD_FOLDER, TOKEN_FILE_PATH_BACKEND
import os
import json
import queue
from werkzeug.utils import secure_filename

bootstrap_bp = Blueprint('bootstrap', __name__)
CORS(bootstrap_bp, resources={r"/*": {"origins": "*"}})  

update_queue = queue.Queue()

@bootstrap_bp.route('/bootstrap', methods=['POST'])
def bootstrap():
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
            create_bootstrap_state(update_queue)

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

@bootstrap_bp.route('/bootstrap-stream')
def bootstrap_stream():
    def generate():
        while True:
            try:
                message = update_queue.get(timeout=10)  
                yield f"data: {message}\n\n"
            except queue.Empty:
                break  

    return Response(generate(), mimetype='text/event-stream')
