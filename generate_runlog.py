import os
import sys
import json
import traceback

# --- Path Setup & Dummy Files ---
# This setup is critical to finding the necessary local packages.
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP_ROOT)
sys.path.append(os.path.join(APP_ROOT, 'api/src'))
sys.path.append(os.path.join(APP_ROOT, 'shared-data/python'))
sys.path.append(os.path.join(APP_ROOT, 'robot-server/src'))

# --- Runlog Cleaning ---
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

# --- Main Logic ---
def main():
    try:
        from opentrons.simulate import simulate as do_simulation
    except ImportError as e:
        print(f"Failed to import opentrons.simulate: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1

    protocol_to_simulate = 'test_protocol.py'
    output_runlog_file = 'protocol-simulation-animation/sample_runlog.json'

    if not os.path.exists(protocol_to_simulate):
        print(f"Error: Protocol file not found at '{protocol_to_simulate}'", file=sys.stderr)
        return 1

    print(f"Simulating protocol: {protocol_to_simulate}")
    try:
        with open(protocol_to_simulate, 'rb') as f:
            runlog, _bundle = do_simulation(protocol_file=f, file_name=os.path.basename(protocol_to_simulate))

        print(f"Simulation successful. Found {len(runlog)} commands.")

        print("Cleaning runlog for JSON serialization...")
        cleaned_runlog = clean_runlog_for_json(runlog)

        print(f"Saving cleaned runlog to {output_runlog_file}")
        with open(output_runlog_file, 'w') as f:
            json.dump(cleaned_runlog, f, indent=2)

        print("Runlog saved successfully.")
        return 0

    except Exception as e:
        print(f"An error occurred during simulation: {e}", file=sys.stderr)
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
