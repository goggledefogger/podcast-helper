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
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "https://podcast-helper.roytown.net"]}}, supports_credentials=True)

from api import routes

if __name__ == '__main__':
    app.run(debug=True, port=5001)
