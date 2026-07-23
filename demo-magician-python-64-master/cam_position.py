"""----------------------------------------------------------------------------------------
This file moves the robot's head to the center line and four corners of the working area
----------------------------------------------------------------------------------------"""
import DobotDllType as dType
from warnings import warn


def main():
    api = dType.load()

    state = dType.ConnectDobot(api, "COM7", 115200)[0]
    print("Connect status:", state)

    if not (state == dType.DobotConnect.DobotConnect_NoError):
        warn("Could not connect. Exiting...")
        exit()

    dType.SetQueuedCmdClear(api)

    # Async Motion Params Settings
    dType.SetHOMEParams(api, 200, 200, 100, 200, isQueued=1)
    dType.SetPTPJointParams(api, 200, 200, 200, 200, 200, 200, 200, 200, isQueued=1)
    dType.SetPTPCommonParams(api, 100, 100, isQueued=1)

    # Async PTP Motion Axes
    #   X-axis --> front to back (assuming the side with the cable ports is the back)
    #   Y-axis --> side to side
    #   Z-axis --> up & down
    # Move to the camera position.
    indexes = [dType.SetPTPCmd(api, dType.PTPMode.PTPMOVLXYZMode, 200, 0, 170, rHead=50, isQueued=1)[0]]
    last_index = indexes[-1]

    # Start executing Command Queue
    dType.SetQueuedCmdStartExec(api)

    # Wait for executing last command
    while last_index > dType.GetQueuedCmdCurrentIndex(api)[0]:
        dType.dSleep(1000)

    # Stop executing Command Queue
    dType.SetQueuedCmdStopExec(api)

    # Disconnect bot
    dType.DisconnectDobot(api)


if __name__ == "__main__":
    main()
