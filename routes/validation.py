from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
import json
import os
from config import UPLOAD_FOLDER

validation_bp = Blueprint('validation', __name__)

@validation_bp.route('/validate', methods=['POST'])
def validate_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    try:
        filename = secure_filename(file.filename)
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        
        file.save(file_path)
        
        with open(file_path, 'r') as f:
            file_content = f.read()
        
        json_data = json.loads(file_content)
        
        return jsonify({
            "message": "File is valid and saved successfully",
            "content": json_data,
            "file_path": file_path
        }), 200
    
    except json.JSONDecodeError:
        return jsonify({"error": "File is not a valid JSON"}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500
