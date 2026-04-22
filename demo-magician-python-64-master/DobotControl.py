import DobotDllType as dType

# Load the API and establish a connection
api = dType.load()
state = dType.ConnectDobot(api, "", 115200)[0]

if state == dType.DobotConnect.DobotConnect_NoError:
    # Clear any previous commands in the queue
    dType.SetQueuedCmdClear(api)

    # Motion Parameter Settings (Standard for Magician)
    dType.SetHOMEParams(api, 200, 200, 50, 0, isQueued=1)
    dType.SetPTPJointParams(api, 200, 200, 200, 200, 200, 200, 200, 200, isQueued=1)
    dType.SetPTPCommonParams(api, 100, 100, isQueued=1)

    # Step 0: Perform Homing operation as required
    dType.SetHOMECmd(api, temp=0, isQueued=1)

    # Block coordinates and sequence
    # Note: All coordinates are within X: [200, 300] and Y: [-100, 100], so no swapping is needed.
    block_coords = [
        [267.5, 10.3],   # Block 0 (Blue)
        [246.0, 74.8],   # Block 1 (Green)
        [225.1, 45.7],   # Block 2 (Yellow)
        [270.9, -31.6],  # Block 3 (Yellow)
        [267.9, -69.9],  # Block 4 (Yellow)
        [226.1, -63.1],  # Block 5 (Red)
        [218.3, 5.7],    # Block 6 (Red)
        [238.6, -16.3]   # Block 7 (Red)
    ]

    target_x, target_y = 280.0, 85.0
    hover_z = 50.0
    pick_z = -50.0
    place_z_start = -50.0
    block_height = 25.4  # 1 inch in mm
    last_cmd_index = 0

    # Iteration through all 8 blocks
    for i in range(8):
        current_block_x = block_coords[i][0]
        current_block_y = block_coords[i][1]
        current_place_z = place_z_start + (i * block_height)

        # PICK UP SEQUENCE
        # Hover above the block
        dType.SetPTPCmd(api, dType.PTPMode.PTPMOVLXYZMode, current_block_x, current_block_y, hover_z, 0, isQueued=1)
        # Descend to the block
        dType.SetPTPCmd(api, dType.PTPMode.PTPMOVLXYZMode, current_block_x, current_block_y, pick_z, 0, isQueued=1)
        # Engage suction cup
        dType.SetEndEffectorSuctionCup(api, 1, 1, isQueued=1)
        # Lift block back to hover height
        dType.SetPTPCmd(api, dType.PTPMode.PTPMOVLXYZMode, current_block_x, current_block_y, hover_z, 0, isQueued=1)

        # PLACE SEQUENCE
        # Move to target location hover height
        dType.SetPTPCmd(api, dType.PTPMode.PTPMOVLXYZMode, target_x, target_y, hover_z, 0, isQueued=1)
        # Descend to the current stack height
        dType.SetPTPCmd(api, dType.PTPMode.PTPMOVLXYZMode, target_x, target_y, current_place_z, 0, isQueued=1)
        # Disengage suction cup
        dType.SetEndEffectorSuctionCup(api, 1, 0, isQueued=1)
        # Lift arm back to hover height for clearance
        last_cmd_index = dType.SetPTPCmd(api, dType.PTPMode.PTPMOVLXYZMode, target_x, target_y, hover_z, 0, isQueued=1)[0]

    # Final Move: Lift to a safe height and finish
    last_cmd_index = dType.SetPTPCmd(api, dType.PTPMode.PTPMOVLXYZMode, target_x, target_y, 160.0, 0, isQueued=1)[0]

    # Start executing the queued commands
    dType.SetQueuedCmdStartExec(api)

    # Wait until the last command in the sequence has finished
    while last_cmd_index > dType.GetQueuedCmdCurrentIndex(api)[0]:
        dType.dSleep(500)

    # Stop execution and clean up
    dType.SetQueuedCmdStopExec(api)
    dType.DisconnectDobot(api)
else:
    print("Failed to connect to Dobot.")