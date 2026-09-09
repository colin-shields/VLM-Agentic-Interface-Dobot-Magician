import os
import re
import subprocess
import time
import json

import streamlit as st

import cv2
import numpy as np
from PIL import Image, ImageDraw
from dotenv import load_dotenv

from google import genai
from google.genai.errors import ServerError, ClientError

# CONFIG ###############################################################################################################

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error(
        "❌ GEMINI_API_KEY not found. "
        "Please create a `.env` file with GEMINI_API_KEY=your_key_here"
    )
    st.stop()

client = genai.Client(api_key=api_key)

# Modifiable constants.

MODEL_NAME = "gemini-3.1-flash-lite"

# Optional test image (for when webcam is not operational); set as None to use webcam (default)
TEST_IMG_PATH = None
# TEST_IMG_PATH = "test_images/oneBlueOneRed.jfif"

ROBOT_PORT = "COM7"
CAMERA_PORT = 1


# HELPER UTILITIES #####################################################################################################

def generate(prompt_parts: list) -> str:
    """Call the Gemini API and return the plain-text response."""
    global client, api_key
    wait_factor = 1
    while True:
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt_parts,
            )
            return response.text
        except ServerError as e:
            wait_factor *= 2
            st.write(f":red[Error, retrying request after {wait_factor}s: {e}]")
            time.sleep(wait_factor)
        except ClientError as e:
            st.write(f":red[Tokens exhausted. Check streamlit terminal to enter new API key.\n{e}]")
            api_key = input("Tokens exhausted, enter new API key: ")
            client = genai.Client(api_key=api_key)


def capture_image() -> str | None:
    """
    Capture a single frame from the default webcam (index 0).

    Returns:
        Path to the saved PNG, or ``None`` on failure.
    """
    if TEST_IMG_PATH is not None:
        im = Image.open(TEST_IMG_PATH)
        im.save(os.path.join(TEST_DIR, "captured_image.png"))
        return TEST_IMG_PATH

    st.write("Accessing webcam…")
    cap = cv2.VideoCapture(CAMERA_PORT)

    if not cap.isOpened():
        st.error("Could not access the webcam.")
        return None

    ret, frame = cap.read()
    cap.release()

    if not ret:
        st.error("Failed to capture image.")
        return None

    img_path = os.path.join(TEST_DIR, "captured_image.png")
    cv2.imwrite(img_path, frame)
    return img_path


def transform_coordinates(img_data: dict) -> dict:
    """
    Use a homography to map image-space corner points to robot-space coordinates.

    The four robot corners correspond to the physical paper boundary:
        (300,  100), (300, -100), (200,  100), (200, -100)
    """
    robot_corners = np.array(
        [[300, 100], [300, -100], [200, -100], [200, 100]],
        dtype=np.float32,
    )

    if len(img_data["paper"][0]) > 2:
        # Standardize the format to use list[tuple]
        try:
            x1, y1, x2, y2, x3, y3, x4, y4 = img_data["paper"][0]
            img_data["paper"] = [(x1, y1), (x2, y2), (x3, y3), (x4, y4)]
        except Exception as e:
            raise ValueError("Paper coordinates not returned in a parseable format.")

    image_corners = np.array(img_data["paper"], dtype=np.float32)
    H, _ = cv2.findHomography(image_corners, robot_corners)

    def _transform(pt):
        p = np.array([pt[0], pt[1], 1.0], dtype=np.float32)
        t = H @ p
        return (
            float(t[0] / t[2]),
            float(t[1] / t[2]),
        )

    result = {"paper": [_transform(point) for point in img_data["paper"]]}

    for key, value in img_data.items():
        if key == "paper":
            continue

        x1, y1, x2, y2 = value

        x1r, y1r = _transform((x1, y1))
        x2r, y2r = _transform((x2, y2))

        result[key] = [(x1r, y1r), (x2r, y2r)]

    return result


def run_file(path: str, print_result=True):
    print(f"Running {path}")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    run_path = os.path.join(current_dir, "demo-magician-python-64-master", path)
    cwd = os.path.dirname(run_path)
    result = subprocess.run(["python", run_path],
                            capture_output=True,
                            text=True,
                            encoding="utf-8",
                            errors="replace",
                            cwd=cwd,
                            env={**os.environ, "PYTHONUTF8": "1"})

    if print_result:
        if result.returncode != 0:
            st.error(f"{path} script exited with an error:\n{result.stderr}")
        else:
            st.success(f"{path} script executed successfully:")
            if result.stdout:
                st.code(result.stdout)


def draw_grid(img: Image.Image, grid_size: int = 100, save=True) -> Image.Image:
    img = img.copy()    # don't overwrite original image
    draw = ImageDraw.Draw(img)

    w, h = img.size
    for x in range(0, w, grid_size):
        draw.line([(x, 0), (x, h)], fill="gray", width=1)
    for y in range(0, h, grid_size):
        draw.line([(0, y), (w, y)], fill="gray", width=1)

    if save:
        img.save(os.path.join(TEST_DIR, "grid_image.png"))

    return img


def draw_bounding_boxes(img: Image.Image, data: dict, save=True) -> Image.Image:
    img = img.copy()
    draw = ImageDraw.Draw(img)

    for key, value in data.items():

        width, height = img.size

        def scale_point(x, y):
            return (
                x * width / 1000,
                y * height / 1000,
            )

        try:

            if key == "paper":
                points = [scale_point(x, y) for x, y in value]
                draw.polygon(points, outline="red", width=3)

            else:
                x0, y0, x1, y1 = value

                x0, y0 = scale_point(x0, y0)
                x1, y1 = scale_point(x1, y1)

                draw.rectangle(
                    [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)],
                    outline="red",
                    width=3,
                )

        except Exception as e:
            print(f"Could not draw bounding box for {key}: {e}")

    if save:
        img.save(os.path.join(TEST_DIR, "bounding_boxes.png"))

    return img


# STREAMLIT & PIPELINE #################################################################################################

st.title("VLM Agentic Interface for Dobot Magician")

home_btn = st.sidebar.button("Home robot")
if home_btn:
    run_file("home.py")
four_corners_btn = st.sidebar.button("Move robot to workspace corners")
if four_corners_btn:
    run_file("four_corners.py")
cam_pos_btn = st.sidebar.button("Move robot to camera-capture position")
if cam_pos_btn:
    run_file("cam_position.py")
rerun_btn = st.sidebar.button("Run most recent code")
if rerun_btn:
    run_file("DobotControl.py")
autorun_tgl = st.sidebar.toggle("Auto-run code after generation", True)

user_command = st.text_input(
    "Enter your command:",
    "Move the yellow block to the right of the blue block. (Hint: the blocks are at z = -50)",
)
run_button = st.button("Run")

if run_button:
    TIMESTAMP = int(time.time())

    # Create test folder for logging attempts.
    TEST_DIR = f"Tests/v2/08-12/1/{TIMESTAMP}"
    os.makedirs(TEST_DIR, exist_ok=False)

    # ─ Capture image ──────────────────────────────────────────────────────────────────────────────────────────────────
    st.write("### Step 1 — Capture Image")
    img_path = capture_image()

    if img_path is None:
        st.error("Image capture failed. Please try again.")
        st.stop()

    st.success("Image captured successfully!")
    im = Image.open(img_path)
    st.image(im)
    im_grid = draw_grid(im)

    # ─ Load demo files ────────────────────────────────────────────────────────────────────────────────────────────────
    try:
        with open("python demo.txt", encoding="utf-8") as f:
            example_code = f.read()
        with open("DobotDllType.txt", encoding="utf-8") as f:
            dobot_dll = f.read()
        with open("CMPSC 497 Robotics Lecture #5 Industrial Robots v3.3.txt", encoding="utf-8") as f:
            lecture_ppt = f.read()
    except FileNotFoundError as exc:
        st.error(f"Required reference file not found: {exc}")
        st.stop()

    # ─ Send to Gemini (Object Detection) ──────────────────────────────────────────────────────────────────────────────

    # Open prompt.
    with open("prompt_a.md", 'r') as f:
        PROMPT_A = f.read()

    response_a = generate([
        im,
        PROMPT_A
    ])

    st.write("# Object Data")
    st.markdown(response_a)

    # ─ Parse Object Data ──────────────────────────────────────────────────────────────────────────────────────────────

    data_img = dict(json.loads(response_a[8:-4]))
    data_robot = transform_coordinates(data_img)

    im_bb = draw_bounding_boxes(im_grid, data_img)
    st.write("## Bounding Boxes")
    st.image(im_bb)

    # ─ Send to Gemini (Code Generation) ───────────────────────────────────────────────────────────────────────────────

    # Open prompt.
    with open("prompt_b.md", 'r') as f:
        PROMPT_B = f.read()

    replaced_prompt_b = (
        PROMPT_B
        .replace("%USER_TASK%", user_command)
        .replace("%OBJECT_DATA%", str(data_robot))
        .replace("%COM_PORT%", ROBOT_PORT)
    )

    response_b = generate([
        replaced_prompt_b,
        example_code,
        dobot_dll,
        lecture_ppt
    ])

    st.write("# Generated Code")
    st.markdown(response_b)

    # ─ Parse Code ─────────────────────────────────────────────────────────────────────────────────────────────────────

    code_pattern = re.compile(r"```python\n(.*?)```", re.DOTALL)
    code_match = re.search(code_pattern, response_b)

    code_path = os.path.join("demo-magician-python-64-master", "DobotControl.py")
    if code_match:
        with open(code_path, 'w', encoding="utf-8") as f:
            f.write(code_match.group(1))
        st.success(f"Python code written to `{code_path}`")
    else:
        st.error(f"Could not parse the generated code.")
        st.stop()

    # ─ Logging ────────────────────────────────────────────────────────────────────────────────────────────────────────

    outputs_path = os.path.join(TEST_DIR, "outputs.md")
    with open(outputs_path, 'w', encoding="utf-8") as f:
        cur_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
        f.write(f"# Set-up:\n"
                f"  - TIMESTAMP: `{TIMESTAMP}`\n"
                f"  - MODEL: `{MODEL_NAME}`\n"
                f"  - GIT COMMIT: `{cur_commit}`\n\n"
                f"# Prompts:\n\n"
                f"## PROMPT A:\n\n{PROMPT_A}\n\n"
                f"## PROMPT B:\n\n{replaced_prompt_b}\n\n"
                f"# Outputs\n\n"
                f"## Robot Coordinates:\n\n```json\n{data_robot}\n```\n\n"
                f"## Response A:\n{response_a}\n\n"
                f"## Response B:\n{response_b}\n")

    with open(os.path.join(TEST_DIR, "conclusions.txt"), 'w') as f:
        # TODO: Add this to streamlit as a text area. For now, enter conclusions manually.
        # Write the results of executing the robot in this file.
        pass

    # ─ Run generated code as subprocess ───────────────────────────────────────────────────────────────────────────────

    if autorun_tgl:
        run_file("DobotControl.py")
    else:
        st.success("Program finished. Press the 'Rerun most recent code' button in the sidebar to run the code.")

########################################################################################################################
