from flask import Flask
from routes import register_routes
from flask_cors import CORS
from config import UPLOAD_FOLDER

app = Flask(__name__)
CORS(app)

@app.route('/')
def hello_world():
    return "Hello, World!"

register_routes(app)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
