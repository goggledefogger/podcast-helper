from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os
import multiprocessing
from utils import initialize_firebase  # Add this import

# Set the start method to 'spawn'
multiprocessing.set_start_method('spawn', force=True)

load_dotenv()

app = Flask(__name__)

# Initialize Firebase
initialize_firebase()

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

# Get the environment (default to 'development')
env = os.getenv('ENV', 'development')

# Get the domain from the environment variable
domain = os.getenv('DOMAIN')

if __name__ == '__main__':
    if env == 'production':
        # In production, use HTTPS with SSL certificates
        app.run(host='0.0.0.0', port=443, ssl_context=(
            f'/etc/letsencrypt/live/{domain}/fullchain.pem',
            f'/etc/letsencrypt/live/{domain}/privkey.pem'
        ))
    else:
        # In development, use HTTP
        app.run(host='0.0.0.0', port=5001, debug=True)
