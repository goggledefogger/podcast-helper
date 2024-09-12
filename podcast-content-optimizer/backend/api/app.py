from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

from api import routes

if __name__ == '__main__':
    app.run(debug=True, port=5000)
