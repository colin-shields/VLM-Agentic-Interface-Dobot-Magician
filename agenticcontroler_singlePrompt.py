import os
import re
import subprocess

import cv2
import numpy as np
import streamlit as st
from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError, ClientError
import time
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

os.makedirs("Tests/1", exist_ok=True)

client = genai.Client(api_key=api_key)
# MODEL_NAME = "gemini-3-flash-preview"
MODEL_NAME = "gemini-3.1-flash-lite"

# Build a large color palette for bounding-box drawing
_EXTRA_COLORS = list(ImageColor.colormap.keys())
COLORS = [
             "red", "green", "blue", "yellow", "orange", "pink", "purple", "brown",
             "gray", "beige", "turquoise", "cyan", "magenta", "lime", "navy",
             "maroon", "teal", "olive", "coral", "lavender", "violet", "gold", "silver",
         ] + _EXTRA_COLORS

# Load prompt from file.
with open("prompt.md", 'r') as f:
    BASE_PROMPT = f.read()

# Optional test image (for when webcam is not operational); set as None to use webcam (default)
# TEST_IMG_PATH = None
TEST_IMG_PATH = "test_images/oneBlueOneRed.jfif"


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


def plot_bounding_boxes(
        im: Image.Image,
        noun_phrases_and_positions: list[tuple[str, tuple[int, int, int, int]]],
) -> str:
    """
    Draw labelled bounding boxes on *a copy* of ``im`` and save to disk.

    Args:
        im: Source PIL image.
        noun_phrases_and_positions: List of (label, (y1, x1, y2, x2)) tuples
            where coordinates are in the 0-1000 normalised space used by Gemini.

    Returns:
        Absolute path of the saved image.
    """
    img = im.copy()
    width, height = img.size
    draw = ImageDraw.Draw(img)

    for i, (label, (y1, x1, y2, x2)) in enumerate(noun_phrases_and_positions):
        color = COLORS[i % len(COLORS)]
        abs_x1 = int(x1 / 1000 * width)
        abs_y1 = int(y1 / 1000 * height)
        abs_x2 = int(x2 / 1000 * width)
        abs_y2 = int(y2 / 1000 * height)
        draw.rectangle(((abs_x1, abs_y1), (abs_x2, abs_y2)), outline=color, width=4)
        draw.text((abs_x1 + 8, abs_y1 + 6), label, fill=color)

    save_path = os.path.join(os.getcwd(), "Tests/1/image_with_bounding_boxes.png")
    img.save(save_path)
    return save_path


def parse_list_boxes(text: str) -> list[list[int]]:
    """
    Parse Gemini bounding-box output into a list of [ymin, xmin, ymax, xmax].

    Handles both:
      - ``[ymin, xmin, ymax, xmax](label)``
      - ``- [ymin, xmin, ymax, xmax](label)``
    """
    result: list[list[int]] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            numbers = line.split("[")[1].split("]")[0].split(",")
            result.append([int(n.strip()) for n in numbers])
        except (IndexError, ValueError):
            try:
                numbers = line.split("- ")[1].split(",")
                result.append([int(n.strip()) for n in numbers])
            except (IndexError, ValueError):
                continue  # skip malformed lines
    return result


def capture_image() -> str | None:
    """
    Capture a single frame from the default webcam (index 0).

    Returns:
        Path to the saved PNG, or ``None`` on failure.
    """
    if TEST_IMG_PATH is not None:
        im = Image.open(TEST_IMG_PATH)
        im.save(TEST_DIR, "captured_image.png")
        return TEST_IMG_PATH

    st.write("Accessing webcam…")
    cap = cv2.VideoCapture(1)

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


def corners_to_points(
        corners: list[int],
) -> list[tuple[int, int]]:
    """Convert [ymin, xmin, ymax, xmax] to four (x, y) corner points."""
    ymin, xmin, ymax, xmax = corners
    return [
        (xmin, ymin),  # top-left
        (xmax, ymin),  # top-right
        (xmin, ymax),  # bottom-left
        (xmax, ymax),  # bottom-right
    ]


def points_to_corners(
        points: list[tuple[float, float]],
) -> list[float]:
    """Convert four (x, y) corner points back to [ymin, xmin, ymax, xmax]."""
    top_left, top_right, bottom_left, bottom_right = points
    xmin, ymin = top_left
    xmax, ymax = bottom_right
    return [ymin, xmin, ymax, xmax]


def transform_coordinates_dict(
        workspace_dict: dict[str, list[tuple]],
        items_dict: dict[str, list[tuple]],
) -> dict[str, list[tuple[float, float]]]:
    """
    Use a homography to map image-space corner points to robot-space coordinates.

    The four robot corners correspond to the physical paper boundary:
        (300,  100), (300, -100), (200,  100), (200, -100)
    """
    robot_corners = np.array(
        [[300, 100], [300, -100], [200, 100], [200, -100]], dtype=np.float32
    )
    image_corners = np.array(workspace_dict["workspace"], dtype=np.float32)
    st.text(f"Image corners (pixel space):\n{image_corners}")

    homography, _ = cv2.findHomography(image_corners, robot_corners)

    def _transform(pt: tuple) -> tuple[float, float]:
        p = np.array([pt[0], pt[1], 1.0], dtype=np.float32).reshape(3, 1)
        t = (homography @ p).flatten()  # shape (3,) — all elements are scalars
        return float(t[0] / t[2]), float(t[1] / t[2])

    return {key: [_transform(p) for p in points] for key, points in items_dict.items()}


def add_color_to_dict(
        bounding_box_text: str,
        converted_dict: dict[str, list],
) -> dict[str, dict]:
    """
    Attach colour labels (parsed from the Gemini response string) to the
    transformed bounding-box dictionary.
    """
    pattern = r"-\s*\[.*?\]\((.*?)\)"
    colors = re.findall(pattern, bounding_box_text)
    colored: dict[str, dict] = {}
    for i, color in enumerate(colors):
        key = f"block_{i}"
        if key in converted_dict:
            colored[key] = {"coordinates": converted_dict[key], "color": color}
    return colored


# STREAMLIT ############################################################################################################

st.title("VLM Agentic Interface for Dobot Magician")

user_command = st.text_input(
    "Enter your command:",
    "Move the yellow block to the right of the blue block. (Hint: the blocks are at z = -50)",
)
run_button = st.button("Run")

if run_button:
    TIMESTAMP = int(time.time())

    # Create test folder for logging attempts.
    TEST_DIR = f"Tests/{TIMESTAMP}"
    os.makedirs("Tests", exist_ok=True)
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

    # ─ Load demo files ────────────────────────────────────────────────────────────────────────────────────────────────
    try:
        with open("python demo.txt", encoding="utf-8") as f:
            example_code = f.read()
        with open("DobotDllType.txt") as f:
            dobot_dll = f.read()
        with open("CMPSC 497 Robotics Lecture #5 Industrial Robots v3.3.txt", encoding="utf-8") as f:
            lecture_ppt = f.read()
    except FileNotFoundError as exc:
        st.error(f"Required reference file not found: {exc}")
        st.stop()

    # ─ Send to Gemini ─────────────────────────────────────────────────────────────────────────────────────────────────

    replaced_prompt = (
        BASE_PROMPT
        .replace("%USER_TASK%", user_command)
        .replace("%IMG_DIMENSIONS%", str(im.size))
    )

    response = generate([
        im,
        replaced_prompt,
        example_code,
        dobot_dll,
        lecture_ppt
    ])

    response_path = os.path.join(TEST_DIR, "response.md")
    with open(response_path, 'w') as f:
        f.write(response)

    config_path = os.path.join(TEST_DIR, "config.txt")
    with open(config_path, 'w') as f:
        f.write(f"TIMESTAMP: {TIMESTAMP}\n"
                f"MODEL: {MODEL_NAME}\n"
                f"PROMPT:\n{replaced_prompt}")

    st.divider()
    st.write("# Response from Gemini:")
    st.markdown(response)
    st.divider()

    # ─ Parse Code ─────────────────────────────────────────────────────────────────────────────────────────────────────

    code_pattern = re.compile(r"```python.*?```", re.DOTALL)
    code_match = re.search(code_pattern, response)

    code_path = os.path.join("demo-magician-python-64-master", "DobotControl.py")
    if code_match:
        with open(code_path, 'w', encoding="utf-8") as f:
            f.write(code_match.group(0)
                    .replace("```python\n", '')
                    .replace("```", ''))
        st.success(f"Python code written to `{code_path}`")
    else:
        st.error(f"Could not parse the generated code.")
        st.stop()

    # ─ Run generated code as subprocess ───────────────────────────────────────────────────────────────────────────────

    exec_button = st.button("Run the Code")
    if exec_button:
        print(f"Running {code_path}")
        current_dir = os.path.dirname(os.path.abspath(__file__))
        run_path = os.path.join(current_dir, "demo-magician-python-64-master", "DobotControl.py")
        cwd = os.path.dirname(run_path)
        result = subprocess.run(["python", run_path],
                                capture_output=True,
                                text=True,
                                encoding="utf-8",
                                errors="replace",
                                cwd=cwd,
                                env={**os.environ, "PYTHONUTF8": "1"})

        if result.returncode != 0:
            st.error(f"Robot script exited with an error:\n{result.stderr}")
        else:
            st.success("Robot script executed successfully.")
            if result.stdout:
                st.text(result.stdout)

########################################################################################################################
