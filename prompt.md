Attached is an image of a workspace containing any number of blocks on top of a flat, white, rectangular paper. Also attached are a robotics lecture, a demo Python script for controlling a Dobot Magician robot arm, and the full API for controlling the robot arm. Using these, your ultimate task is to generate a complete Python program that executes the following task(s): %USER_TASK%

You should analyze the image in steps: 
- Find the bounding box of the paper and all boxes resting on it.
  - The dimensions of the image are %IMG_DIMENSIONS%.
  - Do NOT estimate.
- Analyze the spatial relationships between all the relevant objects in the image.
- Transform the image coordinates to robot coordinates.
  - | Paper Corner | Robot Coordinate (x, y) |
    |--------------|-------------------------|
    | Top-left     | (300, -100)             |
    | Top-right    | (300, 100)              |
    | Bottom-left  | (200, -100)             |
    | Bottom-right | (200, 100)              |
- Come up with a detailed, step-by-step action plan for taking the necessary steps to move the arm to execute the task.
- Generate the robot control code.
  - For the z-coordinates, use 50.0 for hover and -50.0 to pick up the blocks. 
  - Use the suction cup attachment. 
  - Remember to call SetHOMECmd() before moving the robot. 
  - The y coordinates go from left-to-right. Left is positive, right is negative, the center is y=0. The x coordinates go from front-to-back in front of the bot.
  - Always set the `isQueued` parameter as `1`.
  - Do not use `dType.SetQueuedCmdStartExec(api)` or `dType.SetQueuedCmdStopExec(api)`.

Once again, this is the task to execute: %USER_TASK%
