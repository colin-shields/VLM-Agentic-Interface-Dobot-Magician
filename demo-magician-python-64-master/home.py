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

    # Asynch Home
    #   NOTE: if the bot has just been reset, it will not run this (for some reason???)
    dType.SetHOMECmd(api, temp=0, isQueued=1)

    # Start executing Command Queue
    dType.SetQueuedCmdStartExec(api)

    # Disconnect bot
    dType.DisconnectDobot(api)


if __name__ == "__main__":
    main()
