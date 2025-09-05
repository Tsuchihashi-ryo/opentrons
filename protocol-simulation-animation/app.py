from flask import Flask, render_template, request, redirect, url_for, flash
import os
import sys
import json
import traceback

# Add the script's own directory to the python path to find visualizer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from . import visualizer

app = Flask(__name__)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
STATIC_FOLDER = os.path.join(APP_ROOT, 'static')
RUNLOG_FILE = os.path.join(APP_ROOT, 'sample_runlog.json')

app.config['SECRET_KEY'] = 'a very secret key'
os.makedirs(STATIC_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/animate', methods=['POST'])
def animate_protocol():
    animation_url = None
    try:
        print(f"Loading runlog from: {RUNLOG_FILE}")
        with open(RUNLOG_FILE, 'r') as f:
            runlog = json.load(f)

        flash(f"Runlog loaded successfully, found {len(runlog)} commands.", 'success')

        print("Generating animation...")
        animation_filename = visualizer.generate_animation(runlog, STATIC_FOLDER)

        if animation_filename:
            animation_url = url_for('static', filename=animation_filename)
            flash('Animation created successfully!', 'success')
        else:
            flash('Animation generation failed.', 'error')
            print("visualizer.generate_animation returned None.")

    except FileNotFoundError:
        print(f"Error: Could not find {RUNLOG_FILE}", file=sys.stderr)
        flash(f"Error: sample_runlog.json not found. Please generate it first.", 'error')
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        flash(f"An unexpected error occurred: {e}", 'error')

    return render_template('result.html', animation_url=animation_url)

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
