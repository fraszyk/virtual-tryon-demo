import os
import sys

from flask import Flask, send_from_directory
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(__file__))

from api.routes import api_routes  # noqa: E402
from core.config import Config  # noqa: E402

BASE_DIR = os.path.dirname(__file__)

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)
app.register_blueprint(api_routes)


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=Config.DEBUG)

