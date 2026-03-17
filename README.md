# VLM Agentic Interface for Dobot Magician

A Streamlit web app that uses your webcam and Google's Gemini AI to let you control a **Dobot Magician** robot arm with plain-English commands like *"Move the yellow block to the right of the blue block."*

The system automatically:
1. Captures a photo of the workspace
2. Detects objects using AI vision
3. Maps pixel positions to real robot coordinates
4. Generates and runs Python robot-control code — all in one click

---

## Table of Contents

1. [How It Works](#how-it-works)
2. [Prerequisites](#prerequisites)
3. [Step-by-Step Installation](#step-by-step-installation)
4. [Getting a Free Gemini API Key](#getting-a-free-gemini-api-key)
5. [Hardware Setup](#hardware-setup)
6. [Running the App](#running-the-app)
7. [Using the App](#using-the-app)
8. [Troubleshooting](#troubleshooting)
9. [Project Structure](#project-structure)

---

## How It Works

```
You type a command
        ↓
Webcam captures the workspace
        ↓
Gemini AI identifies objects and their positions
        ↓
Pixel coordinates → robot coordinates (homography)
        ↓
Gemini AI writes Python code for the robot
        ↓
Code runs automatically on the Dobot Magician
```

---

## Prerequisites

Before you start, make sure you have the following.

### Software
| Requirement | Version | How to check / download |
|---|---|---|
| Python | 3.14 or newer | `python --version` — [Download](https://www.python.org/downloads/) |
| pip | any recent version | `pip --version` (included with Python) |
| Git | any | `git --version` — [Download](https://git-scm.com/downloads) |
| Visual Studio Code | any recent | [Download](https://code.visualstudio.com/) |

> **Windows — Python install tip:** During the Python installer, check the box **"Add Python to PATH"** before clicking Install. If you skip this, commands like `python` and `pip` won't be found in the terminal.

> **Why VS Code?** It is the recommended editor for this project. It has a built-in terminal, great Python support, and makes working with virtual environments easy. After installing VS Code, open it and install the **Python extension**: click the Extensions icon in the left sidebar (or press `Ctrl+Shift+X`), search for **Python**, and click Install on the Microsoft one.

### Hardware
- Dobot Magician robot arm with its USB cable
- Dobot Magician drivers installed (included on the USB drive that came with the robot)
- A USB webcam (or a built-in laptop camera)
- One sheet of **plain white paper, 8" × 5"** (this is the workspace the robot can see)
- Coloured foam blocks (optional — any small colourful objects work)

---

## Step-by-Step Installation

### 1 — Clone the repository

Open a terminal (Mac/Linux) or Command Prompt / PowerShell (Windows) and run:

```bash
git clone https://github.com/JaredD-SWENG/VLM-Agentic-Interface-Dobot-Magician.git
cd VLM-Agentic-Interface-Dobot-Magician
```

> **What is `git clone`?** It downloads a copy of all the project files to your computer.

---

### 2 — Create a virtual environment (strongly recommended)

A virtual environment keeps this project's packages separate from everything else on your computer so nothing conflicts.

**Mac / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

> **Windows PowerShell — "running scripts is disabled" error:** If you see a message like *"cannot be loaded because running scripts is disabled on this system"*, PowerShell is blocking the activation script. Run this command **first** (it only affects the current terminal window, not your whole system), then try activating again:
> ```powershell
> Set-ExecutionPolicy Unrestricted -Scope Process
> ```
> After that runs, re-run `.\venv\Scripts\Activate.ps1` and it should work.

> You should now see `(venv)` at the start of your terminal prompt. This means the virtual environment is active. You need to re-run the activation command each time you open a new terminal.

---

### 3 — Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs everything the project needs (Streamlit, OpenCV, Pillow, the Gemini SDK, etc.). It may take a minute or two.

---

### 4 — Get a Gemini API key

See the [Getting a Free Gemini API Key](#getting-a-free-gemini-api-key) section below, then come back here.

---

### 5 — Create a `.env` file

In the **root folder of the project** (the same folder as `agenticcontroller.py`), create a new plain-text file called exactly `.env` (note the leading dot, no other extension).

Paste this single line into it, replacing the placeholder with your real key:

```
GEMINI_API_KEY=your_actual_api_key_here
```

> **Example:**
> ```
> GEMINI_API_KEY=AIzaSyABC123XYZ...
> ```

> **⚠️ Keep this file private.** Never commit it to Git or share it. The `.gitignore` in this repo already excludes it.

---

## Getting a Free Gemini API Key

1. Go to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Sign in with a Google account
3. Click **"Create API key"**
4. Copy the key that appears — it starts with `AIza…`
5. Paste it into your `.env` file as shown above

> The free tier of the Gemini API is more than sufficient for this project.

---

## Hardware Setup

### Connect the Dobot Magician

1. Plug the Dobot Magician into your computer using the USB cable
2. Power on the robot using the switch on its base
3. Verify the drivers are installed:
   - **Windows:** Open Device Manager → you should see the Dobot listed under "Ports (COM & LPT)" without any warning icons
   - **Mac/Linux:** Run `ls /dev/tty.*` — you should see something like `/dev/ttyUSB0`

### Connect the webcam

Plug in your USB webcam. If you're using a built-in laptop camera, no action is needed — it's automatically detected as camera index `0`.

### Set up the workspace

Place the **8" × 5" white paper** flat on the table directly in front of the robot arm. The four corners of the paper must map to these robot coordinates:

```
Paper corner          Robot coordinate (X, Y)
──────────────────────────────────────────────
Top-left              (300, -100)
Top-right             (300,  100)
Bottom-left           (200, -100)
Bottom-right          (200,  100)
```

Position the paper so the robot arm can physically reach all four corners. Place your coloured foam blocks on the paper.

> **Tip:** Use small pieces of tape to mark the paper corners on the table so the workspace stays consistent between sessions.

---

## Running the App

Make sure your virtual environment is active (`(venv)` in your prompt), then run:

```bash
streamlit run agenticcontroller.py
```

Streamlit will print a local URL like:

```
  Local URL: http://localhost:8501
```

Open that URL in your browser. The app will load automatically.

---

## Using the App

1. **Type your command** in the text box, for example:
   ```
   Move the yellow block to the right of the blue block. (Hint: the blocks are at z = -50)
   ```
2. Click **Run**
3. Watch the pipeline execute step-by-step in the browser:

| Step | What happens |
|---|---|
| **1 — Capture Image** | Webcam takes a photo of the workspace |
| **2 — Workspace Detection** | AI finds the white paper boundary |
| **3 — Block Detection** | AI identifies all coloured blocks and their positions |
| **4 — Spatial Analysis** | AI describes the physical layout in natural language |
| **5 — Coordinate Transform** | Pixel positions are converted to robot X/Y millimetres |
| **6 — Plan Steps** | AI generates a human-readable action plan |
| **7 — Generate Code** | AI writes Python code to command the robot |
| **8 — Execute** | The generated code runs and the robot moves |

> **The `z` hint:** The Dobot Magician needs to know the height of the objects. Measure the height of your blocks above the table in millimetres and include it in the `z = -50` hint (adjust the number to match your blocks).

---

## Troubleshooting

### "GEMINI_API_KEY not found"
- Make sure the `.env` file is in the **same folder** as `agenticcontroller.py`
- Make sure the file is named `.env` and not `env.txt` or `.env.txt`
- Make sure the line reads `GEMINI_API_KEY=your_key` with **no spaces** around the `=`

### "Could not access the webcam"
- Make sure no other application (Zoom, Teams, etc.) is using the camera
- Try changing `cv2.VideoCapture(0)` to `cv2.VideoCapture(1)` in the code if you have multiple cameras

### "Could not parse workspace bounding box"
- The white paper may be out of frame or poorly lit — try better lighting
- Make sure the paper is clearly visible and contrasts with the table surface

### The robot doesn't move / robot script errors
- Verify the Dobot is powered on and the USB cable is plugged in
- Check that the Dobot drivers are installed correctly
- Make sure you're running the app from the project root directory

### Package import errors after installing
- Make sure your virtual environment is activated — you should see `(venv)` in your prompt
- Re-run `pip install -r requirements.txt` with the virtual environment active

---

## Project Structure

```
VLM-Agentic-Interface-Dobot-Magician/
│
├── agenticcontroller.py                          # Main app — start here
├── requirements.txt                              # Python package list
├── .env                                          # Your API key (you create this)
│
├── DobotDllType.txt                              # Dobot API reference for AI
├── CMPSC 497 Robotics Lecture #5 ...txt          # Example code for AI
│
└── demo-magician-python-64-master/
    ├── DobotControl.py                           # AI-generated code goes here
    └── ...                                       # Dobot SDK DLLs and drivers
```

---

## Acknowledgements

- [Google AI Studio](https://aistudio.google.com/) — Gemini 2.5 Flash Preview API
- [Dobot](https://www.dobot-robots.com/) — Magician robot arm and SDK
- [Streamlit](https://streamlit.io/) — web app framework