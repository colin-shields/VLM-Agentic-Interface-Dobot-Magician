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

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

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
MODEL_NAME = "gemini-3-flash-preview"

# Build a large color palette for bounding-box drawing
_EXTRA_COLORS = list(ImageColor.colormap.keys())
COLORS = [
    "red", "green", "blue", "yellow", "orange", "pink", "purple", "brown",
    "gray", "beige", "turquoise", "cyan", "magenta", "lime", "navy",
    "maroon", "teal", "olive", "coral", "lavender", "violet", "gold", "silver",
] + _EXTRA_COLORS


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

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

    img_path = "Tests/1/captured_image.png"
    cv2.imwrite(img_path, frame)
    return img_path


def corners_to_points(
    corners: list[int],
) -> list[tuple[int, int]]:
    """Convert [ymin, xmin, ymax, xmax] to four (x, y) corner points."""
    ymin, xmin, ymax, xmax = corners
    return [
        (xmin, ymin),   # top-left
        (xmax, ymin),   # top-right
        (xmin, ymax),   # bottom-left
        (xmax, ymax),   # bottom-right
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
        t = (homography @ p).flatten()   # shape (3,) — all elements are scalars
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


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------

st.title("VLM Agentic Interface for Dobot Magician")

user_command = st.text_input(
    "Enter your command:",
    "Move the yellow block to the right of the blue block. (Hint: the blocks are at z = -50)",
)
run_button = st.button("Run")

if run_button:
    # ── Step 1 ── Capture image ──────────────────────────────────────────────
    st.write("### Step 1 — Capture Image")
    img_path = capture_image()

    if img_path is None:
        st.error("Image capture failed. Please try again.")
        st.stop()

    st.success("Image captured successfully!")
    im = Image.open(img_path)
    st.image(im)

    # ── Step 2 ── Detect workspace ───────────────────────────────────────────
    st.write("### Step 2 — Detecting Workspace Boundary")
    workspace_response = generate([
        im,
        (
            "Return the bounding box for just the flat, white, rectangular paper "
            "in the picture using this exact format:\n"
            "[ymin, xmin, ymax, xmax]\n"
            "Do not change the format. Do not say anything else."
        ),
    ])
    st.write("**Workspace Bounding Box Agent:**")
    st.text(workspace_response)

    workspace_list = parse_list_boxes(workspace_response)
    if not workspace_list:
        st.error("Could not parse workspace bounding box. Check the image.")
        st.stop()
    workspace_dict: dict[str, list] = {"workspace": workspace_list[0]}

    # ── Step 3 ── Detect blocks ──────────────────────────────────────────────
    st.write("### Step 3 — Detecting Blocks")
    bounding_box_response = generate([
        im,
        (
            "Return bounding boxes for all the blocks as a list using this exact format:\n"
            "- [ymin, xmin, ymax, xmax](block_color)\n"
            "Always put - before each item. Do not change the format. Do not say anything else."
        ),
    ])
    st.write("**Bounding Boxes Agent:**")
    st.text(bounding_box_response)

    # ── Step 4 ── Spatial analysis ───────────────────────────────────────────
    st.write("### Step 4 — Spatial Analysis")
    spatial_response = generate([
        im,
        (
            f"Given the user's command for a robot arm: {user_command}\n"
            "Describe the spatial relationship between all the relevant objects in the scene.\n"
            "Do NOT include location/bounding boxes.\n"
            "Provide the approximate size (mm), shape (mm), orientation, and spatial relationship "
            "of each relevant object, plus anything else useful for planning the task."
        ),
    ])
    st.write("**Spatial Analysis Agent:**")
    st.text(spatial_response)

    # ── Draw bounding boxes on image ─────────────────────────────────────────
    boxes = parse_list_boxes(bounding_box_response)
    boxes_dict: dict[str, list] = {f"block_{i}": x for i, x in enumerate(boxes)}
    combined_dict = {**boxes_dict, **workspace_dict}

    try:
        processed_image_path = plot_bounding_boxes(im, list(combined_dict.items()))
        st.image(processed_image_path, caption="Image with Bounding Boxes")
    except ValueError as e:
        st.write(f":red[Could not generate image with bounding boxes >:( \n{e}]")

    # ── Step 5 ── Coordinate transformation ─────────────────────────────────
    st.write("### Step 5 — Transforming to Robot Coordinates")
    boxes_points = {label: corners_to_points(corners) for label, corners in boxes_dict.items()}
    workspace_dict["workspace"] = corners_to_points(workspace_dict["workspace"])

    transformed_boxes = transform_coordinates_dict(workspace_dict, boxes_points)
    st.text(f"Transformed (robot-space) boxes:\n{transformed_boxes}")

    transformed_corners = {
        label: points_to_corners(pts) for label, pts in transformed_boxes.items()
    }
    st.text(f"Back to corner format:\n{transformed_corners}")

    colored_dict = add_color_to_dict(bounding_box_response, transformed_corners)
    st.text(f"Color-labelled dict:\n{colored_dict}")

    # ── Step 6 ── Generate action plan ───────────────────────────────────────
    st.write("### Step 6 — Planning Steps")
    steps_response = generate([
        (
            f"Based on the scene below, generate a detailed, step-by-step plan to perform "
            f"this action using a Dobot Magician robot arm: {user_command}\n\n"
            f"Object locations/bounding boxes (use these exact values): {colored_dict}\n\n"
            f"Spatial analysis: {spatial_response}"
        ),
    ])
    st.write("**Logic Steps Agent:**")
    st.text(steps_response)

    # ── Step 7 ── Generate robot Python code ─────────────────────────────────
    st.write("### Step 7 — Generating Robot Control Code")
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

    code_response = generate([
        (
            f"Here are the steps to perform on a Dobot Magician robot arm:\n{steps_response}\n\n"
            "Write a complete Python program to execute these steps. For the z-coordinates, use 50.0 for hover and -50.0 to pick up the blocks. Use the suction cup attachment. Remember to call SetHOMECmd() before moving the robot.\n"
            "The y coordinates go from left-to-right. Left is positive, right is negative, the center is y=0. The x coordinates go from front-to-back in front of the bot."
            "The X-coordinates should range from 200 to 300, and the Y-coordinates should range from -100 to 100. If either are not in this range, swap the x coordinates and the y coordinates.\n"
            "Return ONLY Python code — use comments for explanations.\n"
            "Example code is appended below."
        ),
        example_code,
        dobot_dll,
        lecture_ppt
    ])
    st.write("**Coding Agent:**")
    st.code(code_response, language="python")

    # ── Step 8 ── Write and run the generated code ───────────────────────────
    file_path = os.path.join("demo-magician-python-64-master", "DobotControl.py")
    cleaned_code = (
        code_response.strip()
        .removeprefix("```python")
        .removesuffix("```")
        .strip()
    )

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(cleaned_code)
        st.success(f"Python code written to `{file_path}`")
    except OSError as exc:
        st.error(f"Could not write generated code: {exc}")
        st.stop()

    # Run generated code as subprocess.
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