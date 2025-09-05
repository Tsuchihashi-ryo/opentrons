from opentrons import protocol_api

metadata = {
    'protocolName': 'Simple Test Protocol for Animation',
    'author': 'Jules the AI',
    'description': 'A simple protocol that loads labware to test the animation generator.',
    'apiLevel': '2.14'
}

def run(protocol: protocol_api.ProtocolContext):
    # Define liquids
    water = protocol.define_liquid(
        name="Water",
        description="A simple water sample.",
        display_color="#0000FF",  # Blue
    )
    reagent = protocol.define_liquid(
        name="Reagent A",
        description="A generic reagent.",
        display_color="#00FF00",  # Green
    )

    # Load labware
    plate = protocol.load_labware('corning_96_wellplate_360ul_flat', location='2')
    tiprack = protocol.load_labware('opentrons_96_tiprack_300ul', location='1')

    # Load instrument
    pipette = protocol.load_instrument('p300_single_gen2', 'right', tip_racks=[tiprack])

    # Load liquids into wells
    protocol.comment("Setting up initial liquid state.")
    plate.wells_by_name()['A1'].load_liquid(liquid=water, volume=150)
    plate.wells_by_name()['B2'].load_liquid(liquid=reagent, volume=100)

    # Perform pipetting
    protocol.comment("Starting pipetting.")
    pipette.pick_up_tip()
    pipette.aspirate(50, plate.wells_by_name()['A1'])
    pipette.dispense(50, plate.wells_by_name()['C3'])
    pipette.drop_tip()

    protocol.comment("Protocol complete.")
