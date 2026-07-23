import os
import re
import subprocess
import time
import json

import cv2
import numpy as np
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError, ClientError
from PIL import Image, ImageColor, ImageDraw

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
MODEL_NAME = "gemini-3.1-flash-lite"

# Build a large color palette for bounding-box drawing
_EXTRA_COLORS = list(ImageColor.colormap.keys())
COLORS = [
             "red", "green", "blue", "yellow", "orange", "pink", "purple", "brown",
             "gray", "beige", "turquoise", "cyan", "magenta", "lime", "navy",
             "maroon", "teal", "olive", "coral", "lavender", "violet", "gold", "silver",
         ] + _EXTRA_COLORS

# Optional test image (for when webcam is not operational); set as None to use webcam (default)
TEST_IMG_PATH = None
# TEST_IMG_PATH = "test_images/oneBlueOneRed.jfif"


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


# def plot_bounding_boxes(
#         im: Image.Image,
#         noun_phrases_and_positions: list[tuple[str, tuple[int, int, int, int]]],
# ) -> str:
#     """
#     Draw labelled bounding boxes on *a copy* of ``im`` and save to disk.
#
#     Args:
#         im: Source PIL image.
#         noun_phrases_and_positions: List of (label, (y1, x1, y2, x2)) tuples
#             where coordinates are in the 0-1000 normalised space used by Gemini.
#
#     Returns:
#         Absolute path of the saved image.
#     """
#     img = im.copy()
#     width, height = img.size
#     draw = ImageDraw.Draw(img)
#
#     for i, (label, (y1, x1, y2, x2)) in enumerate(noun_phrases_and_positions):
#         color = COLORS[i % len(COLORS)]
#         abs_x1 = int(x1 / 1000 * width)
#         abs_y1 = int(y1 / 1000 * height)
#         abs_x2 = int(x2 / 1000 * width)
#         abs_y2 = int(y2 / 1000 * height)
#         draw.rectangle(((abs_x1, abs_y1), (abs_x2, abs_y2)), outline=color, width=4)
#         draw.text((abs_x1 + 8, abs_y1 + 6), label, fill=color)
#
#     save_path = os.path.join(os.getcwd(), "Tests/1/image_with_bounding_boxes.png")
#     img.save(save_path)
#     return save_path


# def parse_list_boxes(text: str) -> list[list[int]]:
#     """
#     Parse Gemini bounding-box output into a list of [ymin, xmin, ymax, xmax].
#
#     Handles both:
#       - ``[ymin, xmin, ymax, xmax](label)``
#       - ``- [ymin, xmin, ymax, xmax](label)``
#     """
#     result: list[list[int]] = []
#     for line in text.strip().splitlines():
#         line = line.strip()
#         if not line:
#             continue
#         try:
#             numbers = line.split("[")[1].split("]")[0].split(",")
#             result.append([int(n.strip()) for n in numbers])
#         except (IndexError, ValueError):
#             try:
#                 numbers = line.split("- ")[1].split(",")
#                 result.append([int(n.strip()) for n in numbers])
#             except (IndexError, ValueError):
#                 continue  # skip malformed lines
#     return result


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
    cap = cv2.VideoCapture(0)

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


# def corners_to_points(
#         corners: list[int],
# ) -> list[tuple[int, int]]:
#     """Convert [ymin, xmin, ymax, xmax] to four (x, y) corner points."""
#     ymin, xmin, ymax, xmax = corners
#     return [
#         (xmin, ymin),  # top-left
#         (xmax, ymin),  # top-right
#         (xmin, ymax),  # bottom-left
#         (xmax, ymax),  # bottom-right
#     ]


# def points_to_corners(
#         points: list[tuple[float, float]],
# ) -> list[float]:
#     """Convert four (x, y) corner points back to [ymin, xmin, ymax, xmax]."""
#     top_left, top_right, bottom_left, bottom_right = points
#     xmin, ymin = top_left
#     xmax, ymax = bottom_right
#     return [ymin, xmin, ymax, xmax]


def transform_coordinates(img_data: dict) -> dict:
    """
    Use a homography to map image-space corner points to robot-space coordinates.

    The four robot corners correspond to the physical paper boundary:
        (300,  100), (300, -100), (200,  100), (200, -100)
    """
    robot_corners = np.array(
        [[300, 100], [300, -100], [200, 100], [200, -100]],
        dtype=np.float32,
    )

    if len(img_data["paper"][0]) > 2:
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

        # value = [x1, y1, x2, y2]
        x1, y1, x2, y2 = value

        x1r, y1r = _transform((x1, y1))
        x2r, y2r = _transform((x2, y2))

        result[key] = [(x1r, y1r), (x2r, y2r)]

    return result


# def add_color_to_dict(
#         bounding_box_text: str,
#         converted_dict: dict[str, list],
# ) -> dict[str, dict]:
#     """
#     Attach colour labels (parsed from the Gemini response string) to the
#     transformed bounding-box dictionary.
#     """
#     pattern = r"-\s*\[.*?\]\((.*?)\)"
#     colors = re.findall(pattern, bounding_box_text)
#     colored: dict[str, dict] = {}
#     for i, color in enumerate(colors):
#         key = f"block_{i}"
#         if key in converted_dict:
#             colored[key] = {"coordinates": converted_dict[key], "color": color}
#     return colored


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


def draw_grid(img: Image.Image, grid_size: int = 100) -> Image.Image:
    img = img.copy()    # don't overwrite original image
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for x in range(0, w, grid_size):
        draw.line([(x, 0), (x, h)], fill="gray", width=1)
    for y in range(0, h, grid_size):
        draw.line([(0, y), (w, y)], fill="gray", width=1)
    img.save(os.path.join(TEST_DIR, "grid_image.png"))
    return img


def draw_bounding_boxes(img: Image.Image, data: dict) -> Image.Image:
    img = img.copy()
    draw = ImageDraw.Draw(img)

    for key, value in data.items():

        try:

            if key == "paper":
                prev = value[0]
                for point in value:
                    draw.line([prev, point], "red", 3)
                    prev = point
                draw.line([value[-1], value[1]], "red", 3)
            else:
                draw.rectangle(value, outline="red", width=3)

        except Exception as e:
            print(f"Could not draw bounding box for {key}: {e}")

    img.save(os.path.join(TEST_DIR, "bounding_boxes.png"))
    return img


# STREAMLIT ############################################################################################################

st.title("VLM Agentic Interface for Dobot Magician")

four_corners_btn = st.sidebar.button("Move robot to workspace corners")
if four_corners_btn:
    run_file("four_corners.py")
rerun_btn = st.sidebar.button("Rerun most recent code")
if rerun_btn:
    run_file("DobotControl.py")
cam_pos_btn = st.sidebar.button("Move to camera capture position")
if cam_pos_btn:
    run_file("cam_position.py")
autorun_tgl = st.sidebar.toggle("Auto-run code after generation", True)

user_command = st.text_input(
    "Enter your command:",
    "Move the yellow block to the right of the blue block. (Hint: the blocks are at z = -50)",
)
run_button = st.button("Run")

if run_button:
    TIMESTAMP = int(time.time())

    # Create test folder for logging attempts.
    TEST_DIR = f"Tests/single/07-22/{TIMESTAMP}"
    # os.makedirs("Tests/live-tests", exist_ok=True)
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
        im_grid,
        PROMPT_A
    ])

    st.write("# Object Data")
    st.markdown(response_a)

    # ─ Parse Object Data ──────────────────────────────────────────────────────────────────────────────────────────────

    data_img = dict(json.loads(response_a[8:-4]))
    data_robot = transform_coordinates(data_img)
    im_bb = draw_bounding_boxes(im_grid, data_robot)

    # ─ Send to Gemini (Code Generation) ───────────────────────────────────────────────────────────────────────────────

    # Open prompt.
    with open("prompt_b.md", 'r') as f:
        PROMPT_B = f.read()

    replaced_prompt_b = (
        PROMPT_B
        .replace("%USER_TASK%", user_command)
        .replace("%OBJECT_DATA%", str(data_robot))
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

    response_a_path = os.path.join(TEST_DIR, "response_a.md")
    with open(response_a_path, 'w', encoding="utf-8") as f:
        f.write(response_a)

    response_b_path = os.path.join(TEST_DIR, "response_b.md")
    with open(response_b_path, 'w', encoding="utf-8") as f:
        f.write(response_b)

    config_path = os.path.join(TEST_DIR, "config.txt")
    with open(config_path, 'w') as f:
        cur_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode('ascii').strip()
        f.write(f"TIMESTAMP: {TIMESTAMP}\n"
                f"MODEL: {MODEL_NAME}\n"
                f"GIT COMMIT: {cur_commit}\n\n"
                f"PROMPT A:\n{PROMPT_A}\n\n"
                f"PROMPT B:\n{replaced_prompt_b}")

    with open(os.path.join(TEST_DIR, "conclusions.txt"), 'w') as f:
        # TODO: Add this to streamlit as a text area. For now, enter conclusions manually.
        f.write("Write the results of executing the robot in this file.")

    # # ─ Parse Bounding Boxes ───────────────────────────────────────────────────────────────────────────────────────────
    #
    # json_pattern = re.compile(r"```json\n(.*?)```", re.DOTALL)
    # json_match = re.search(json_pattern, response)
    #
    # if json_match:
    #     st.write("# Bounding Boxes:")
    #     try:
    #         bboxes = json.loads(json_match.group(1))
    #         st.json(bboxes)
    #
    #         draw_im = cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)
    #         draw = ImageDraw.Draw(im)
    #         for obj, coords in dict(bboxes).items():
    #             draw.rectangle(coords, width=3)
    #             # coords = tuple(coords)
    #             # cv2.rectangle(draw_im, coords[:2], coords[-2:])
    #         im.save(os.path.join(TEST_DIR, "bounding_boxes.png"))
    #         st.image(im)
    #
    #     except Exception as e:
    #         st.error(f"Error parsing json: {e}")
    #         print(e)
    # else:
    #     st.error(f"Could not draw bounding boxes.")

    # ─ Parse Code ─────────────────────────────────────────────────────────────────────────────────────────────────────

    # code_pattern = re.compile(r"```python\n(.*?)```", re.DOTALL)
    # code_match = re.search(code_pattern, response)
    #
    # code_path = os.path.join("demo-magician-python-64-master", "DobotControl.py")
    # if code_match:
    #     with open(code_path, 'w', encoding="utf-8") as f:
    #         f.write(code_match.group(1))
    #     st.success(f"Python code written to `{code_path}`")
    # else:
    #     st.error(f"Could not parse the generated code.")
    #     st.stop()

    # ─ Run generated code as subprocess ───────────────────────────────────────────────────────────────────────────────

    # exec_button = st.button("Run the Code")
    # if exec_button:
    if autorun_tgl:
        run_file("DobotControl.py")
    else:
        st.success("Program finished. Press the 'Rerun most recent code' button in the sidebar to run the code.")

########################################################################################################################
