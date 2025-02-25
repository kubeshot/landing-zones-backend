from flask import Blueprint, request, jsonify, Response
from flask_cors import CORS  # Import CORS
from utils.github import check_repo_file
from config import TOKEN_FILE_PATH, UPLOAD_FOLDER
import os
import json
from werkzeug.utils import secure_filename

bootstrap_bp = Blueprint('bootstrap', __name__)
CORS(bootstrap_bp, resources={r"/*": {"origins": "*"}})  

@bootstrap_bp.route('/bootstrap', methods=['POST'])
def bootstrap():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No data received"}), 400

        github_access_token = data.pop('githubAccessToken', None)

        if not github_access_token:
            return jsonify({"error": "GitHub access token is required"}), 400

        with open(TOKEN_FILE_PATH, 'w') as f:
            f.write(github_access_token)

        os.chmod(TOKEN_FILE_PATH, 0o600)

        filename = secure_filename("bootstrap_data.json")
        file_path = os.path.join(UPLOAD_FOLDER, filename)

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)

        git_org_name = data.get('gitOrgName')
        bootstrap_repo = data.get('bootstrapRepo')

        if not git_org_name or not bootstrap_repo:
            return jsonify({"error": "gitOrgName or bootstrapRepo missing in data"}), 400

        file_to_check = "envs/shared/terraform.tfvars"
        if check_repo_file(github_access_token, git_org_name, bootstrap_repo, file_to_check):
            return jsonify({
                "status": "success",
                "message": "File already exists in the repository!"
            }), 200
        else:
            return jsonify({
                "status": "success",
                "message": "Repository is empty or file does not exist!"
            }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@bootstrap_bp.route('/bootstrap-stream')
def bootstrap_stream():
    def generate():
        try:
            yield "data: Data received successfully!\n\n"

            import time
            time.sleep(2)

            yield "data: Data saved successfully!\n\n"

            time.sleep(2)
            yield "data: Repository checked successfully!\n\n"

            time.sleep(2)
            yield "data: Process completed successfully!\n\n"

        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"

    return Response(generate(), mimetype='text/event-stream')
