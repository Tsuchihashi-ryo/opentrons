import os
import sys
import traceback
import json
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, abort
from werkzeug.utils import secure_filename
from typing import Optional

# With editable installs, opentrons should be found automatically
from opentrons.simulate import simulate as do_simulation

def clean_runlog_for_json(runlog):
    cleaned_log = []
    for command in runlog:
        cleaned_command = {'level': command.get('level', 0), 'payload': {}, 'logs': []}
        payload = command.get('payload', {})
        if not isinstance(payload, dict):
            continue
        for key, value in payload.items():
            if isinstance(value, (dict, list, str, int, float, bool, type(None))):
                cleaned_command['payload'][key] = value
            else:
                cleaned_command['payload'][key] = str(value)
        cleaned_log.append(cleaned_command)
    return cleaned_log

def load_labware_definition(load_name: str) -> Optional[dict]:
    # Assumes script is run from the root of the opentrons repo
    base_path = 'shared-data/labware/definitions/2/'
    labware_path = os.path.join(base_path, load_name)
    if not os.path.isdir(labware_path): return None
    versions = [d for d in os.listdir(labware_path) if d.endswith('.json')]
    if not versions: return None
    latest = sorted(versions, key=lambda v: int(os.path.splitext(v)[0]))[-1]
    with open(os.path.join(labware_path, latest), 'r') as f:
        return json.load(f)

app = Flask(__name__)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(APP_ROOT, 'uploads')
ALLOWED_EXTENSIONS = {'py', 'json'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'a very secret key'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/labware/<path:load_name>')
def get_labware_definition(load_name):
    """API endpoint to fetch a labware definition."""
    definition = load_labware_definition(load_name)
    if definition:
        return jsonify(definition)
    else:
        abort(404, description="Labware definition not found.")

@app.route('/animate', methods=['POST'])
def animate_protocol():
    if 'protocol_file' not in request.files:
        return jsonify({"error": "No file part in the request"}), 400
    file = request.files['protocol_file']
    if file.filename == '':
        return jsonify({"error": "No file selected"}), 400
    if not file or not ('.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS):
        return jsonify({"error": "Invalid file type"}), 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    try:
        with open(filepath, 'rb') as protocol_file:
            runlog, _bundle = do_simulation(protocol_file=protocol_file, file_name=filename)
        cleaned_runlog = clean_runlog_for_json(runlog)
        return jsonify(cleaned_runlog)
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001, use_reloader=False)
