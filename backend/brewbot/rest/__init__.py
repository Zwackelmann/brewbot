from flask import Flask
from brewbot.ard.api import api
import os
import json

app = Flask(__name__)

config_path = os.path.join(app.root_path, 'config.json')
if os.path.exists(config_path):
    app.config.from_file(config_path, load=json.load)

app.register_blueprint(api)
