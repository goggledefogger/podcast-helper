from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os
import multiprocessing

# Set the start method to 'spawn'
multiprocessing.set_start_method('spawn', force=True)

load_dotenv()

app = Flask(__name__)

# Configure CORS
CORS(app, resources={
    r"/*": {
        "origins": [
            "http://localhost:3000",
            "https://podcast-helper-435105.web.app",
            "https://roytown.net"
        ]
    }
}, supports_credentials=True)

from api import routes

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5001)
