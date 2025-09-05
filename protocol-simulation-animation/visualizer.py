import os
import sys
import uuid
import json
import traceback
import re
import shutil
import tempfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.animation as animation
from typing import Dict, Any, List, Optional

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

# --- State Management ---
class SimulationState:
    def __init__(self, labware_defs: Dict[str, Any]):
        self.labware_defs = labware_defs
        self.pipette_location: Dict[str, Any] = {'labware': None, 'well': None}
        self.liquid_levels: Dict[str, Dict[str, float]] = {}
        for labware_id, definition in labware_defs.items():
            self.liquid_levels[labware_id] = {well: 0 for well in definition['wells']}

    def set_initial_liquid(self, labware_id: str, well: str, volume: float):
        if labware_id in self.liquid_levels and well in self.liquid_levels[labware_id]:
            self.liquid_levels[labware_id][well] = volume

    def update_from_command(self, command: Dict[str, Any]):
        payload = command.get('payload', {})
        text = payload.get('text', '')
        info = get_labware_and_well_info(text)
        if not info: return
        labware_id = f"{info['labware']}_slot_{info['slot']}"
        if labware_id not in self.labware_defs: return
        self.pipette_location = {'labware': labware_id, 'well': info['well']}
        if 'aspirating' in text.lower():
            self.liquid_levels[labware_id][info['well']] -= payload.get('volume', 0)
        elif 'dispensing' in text.lower():
            self.liquid_levels[labware_id][info['well']] += payload.get('volume', 0)

# --- Labware & Drawing ---
def load_labware_definition(load_name: str) -> Optional[dict]:
    base_path = 'shared-data/labware/definitions/2/'
    labware_path = os.path.join(base_path, load_name)
    if not os.path.isdir(labware_path): return None
    versions = [d for d in os.listdir(labware_path) if d.endswith('.json')]
    if not versions: return None
    latest = sorted(versions, key=lambda v: int(os.path.splitext(v)[0]))[-1]
    with open(os.path.join(labware_path, latest), 'r') as f:
        return json.load(f)

def get_labware_and_well_info(text: str) -> Optional[Dict[str, str]]:
    match = re.search(r'(from|into|in) (.+?) of (.+?) on slot (\d+)', text)
    if match:
        _p, well, labware, slot = match.groups()
        return {'well': well, 'labware': labware, 'slot': slot}
    return None

def draw_frame(fig: plt.Figure, state: SimulationState, command_text: str):
    fig.clear()
    gs = fig.add_gridspec(1, 2, width_ratios=[1.2, 1])
    ax_deck = fig.add_subplot(gs[0])
    ax_focus = fig.add_subplot(gs[1])
    ax_deck.set_title("Deck Overview", fontsize=10)
    ax_deck.set_aspect('equal')
    ax_deck.set_xlim(-10, 450)
    ax_deck.set_ylim(350, -10)
    slot_positions = {'1': (10, 10), '2': (145, 10), '3': (280, 10), '12': (280, 290)}
    for labware_id, definition in state.labware_defs.items():
        slot = labware_id.split('_slot_')[-1]
        x_offset, y_offset = slot_positions.get(slot, (10, 100))
        x_dim, y_dim = definition['dimensions']['xDimension'], definition['dimensions']['yDimension']
        is_active = labware_id == state.pipette_location.get('labware')
        outline = patches.Rectangle((x_offset, y_offset), x_dim, y_dim, lw=2 if is_active else 1, ec='red' if is_active else 'black', fc='lightgray')
        ax_deck.add_patch(outline)
        ax_deck.text(x_offset + x_dim/2, y_offset + y_dim/2, f"S{slot}", ha='center', va='center', fontsize=8)
    active_labware_id = state.pipette_location.get('labware')
    if active_labware_id and active_labware_id in state.labware_defs:
        labware_def = state.labware_defs[active_labware_id]
        ax_focus.set_title(f"Slot {active_labware_id.split('_slot_')[-1]} View", fontsize=10)
        ax_focus.set_aspect('equal')
        dims = labware_def['dimensions']
        x_dim, y_dim = dims['xDimension'], dims['yDimension']
        ax_focus.add_patch(patches.Rectangle((0, 0), x_dim, y_dim, lw=1, ec='black', fc='#cdd4d9'))
        for name, props in labware_def['wells'].items():
            x, y = props['x'], props['y']
            is_active_well = name == state.pipette_location.get('well')
            if props['shape'] == 'circular':
                d = props.get('diameter', 0)
                well_outline = patches.Circle((x, y), d/2, lw=2 if is_active_well else 1, ec='red' if is_active_well else 'gray', fc='white')
                ax_focus.add_patch(well_outline)
                volume = state.liquid_levels.get(active_labware_id, {}).get(name, 0)
                if volume > 0:
                    fill_radius = (d/2) * min(1, volume / props['totalLiquidVolume'])**0.5
                    ax_focus.add_patch(patches.Circle((x, y), fill_radius, fc='cyan', alpha=0.6))
            elif props['shape'] == 'rectangular':
                well_x, well_y = props['xDimension'], props['yDimension']
                well_outline = patches.Rectangle((x - well_x/2, y - well_y/2), well_x, well_y, lw=2 if is_active_well else 1, ec='red' if is_active_well else 'gray', fc='white')
                ax_focus.add_patch(well_outline)
                volume = state.liquid_levels.get(active_labware_id, {}).get(name, 0)
                if volume > 0:
                    fill_ratio = min(1, volume / props['totalLiquidVolume'])
                    ax_focus.add_patch(patches.Rectangle((x - well_x/2, y - well_y/2), well_x, well_y * fill_ratio, fc='cyan', alpha=0.6))
        ax_focus.set_xlim(-5, x_dim + 5)
        ax_focus.set_ylim(y_dim + 5, -5)
    else:
        ax_focus.set_title("Focused View", fontsize=10)
        ax_focus.text(0.5, 0.5, "No active labware", ha='center', va='center')
    fig.suptitle(f"Step: {command_text}", fontsize=12, y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.9])

# --- Main Animation Generation ---
def generate_animation(runlog: List[Dict[str, Any]], static_folder_path: str) -> Optional[str]:
    try:
        plate_def = load_labware_definition('corning_96_wellplate_360ul_flat')
        tiprack_def = load_labware_definition('opentrons_96_tiprack_300ul')
        trash_def = load_labware_definition('opentrons_1_trash_1100ml_fixed')
        labware_defs = {
            "Corning 96 Well Plate 360 µL Flat_slot_2": plate_def,
            "Opentrons OT-2 96 Tip Rack 300 µL_slot_1": tiprack_def,
            "Opentrons Fixed Trash_slot_12": trash_def
        }
        sim_state = SimulationState(labware_defs)
        sim_state.set_initial_liquid("Corning 96 Well Plate 360 µL Flat_slot_2", "A1", 150)
        sim_state.set_initial_liquid("Corning 96 Well Plate 360 µL Flat_slot_2", "B2", 100)
        fig = plt.figure(figsize=(10, 5))
        def update(frame_index):
            command = runlog[frame_index]
            sim_state.update_from_command(command)
            draw_frame(fig, sim_state, command.get('payload', {}).get('text', ''))
        ani = animation.FuncAnimation(fig, update, frames=len(runlog), interval=800)

        # Save to a temporary file outside the watched directories
        temp_dir = tempfile.gettempdir()
        temp_save_path = os.path.join(temp_dir, f"temp_animation_{uuid.uuid4().hex}.gif")
        print(f"Saving animation to temporary path: {temp_save_path}...")
        try:
            ani.save(temp_save_path, writer='imagemagick', fps=1.5)
        except Exception as e:
            print(f"imagemagick writer failed: {e}. Falling back to pillow.", file=sys.stderr)
            ani.save(temp_save_path, writer='pillow', fps=1.5)
        plt.close(fig)

        # Move the finished file to the static directory
        animation_filename = f"animation_{uuid.uuid4().hex}.gif"
        final_path = os.path.join(static_folder_path, animation_filename)
        print(f"Moving animation to final path: {final_path}")
        shutil.move(temp_save_path, final_path)

        return animation_filename
    except Exception as e:
        print(f"Error during visualization: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return None
