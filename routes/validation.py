from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import json
import os
import subprocess
from config import UPLOAD_FOLDER
from google.oauth2 import service_account  
from google.cloud import storage 
from google.auth.exceptions import GoogleAuthError 

validation_bp = Blueprint('validation', __name__)

@validation_bp.route('/validate', methods=['POST'])
def validate_sa_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        file_content = file.read()
        json_data = json.loads(file_content)
        
        credentials = service_account.Credentials.from_service_account_info(json_data)
        storage_client = storage.Client(credentials=credentials)

        
        file_path = os.path.join(UPLOAD_FOLDER, "sa_key.json")
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        
        return jsonify({
            "message": "Service account key is valid and authenticated with GCP",
            "file_path": file_path
        }), 200
    
    except json.JSONDecodeError:
        return jsonify({"error": "File is not a valid JSON"}), 400
    
    except GoogleAuthError as e:
        return jsonify({"error": "Failed to authenticate with GCP", "details": str(e)}), 400
    
    except Exception as e:
        return jsonify({"error": "An unexpected error occurred "+str(e), "details": str(e)}), 500