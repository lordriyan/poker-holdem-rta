# CheatPoker - Texas Hold'em HUD & Equity Calculator

A real-time poker HUD overlay and screen recognition bot for Texas Hold'em. CheatPoker captures card areas (ROIs) on your screen, applies rotation alignment, recognizes card values using template matching (for J, Q, K, A and suits) or OCR (for numbers 2-10), and displays a real-time floating equity window.

---

## Features

- **Live Screen Grabbing**: Highly optimized desktop screen capturing via `mss`.
- **Advanced ROI Editor**:
  - Draw, move, and size region boxes for Hero cards and Board cards.
  - Rotate crops dynamically ($-180^\circ$ to $180^\circ$) to align tilted/angled cards on the table.
  - Drag sliders to split cards into rank (top) and suit (bottom).
  - Floating **ROI Live Preview** window showing binarized preprocessed feeds of the card, rank, and suit crops in real-time.
- **Hybrid Card Recognition**:
  - **Scale-Invariant Template Matching** on binary images for J, Q, K, A, and the four suits (`♠`, `♥`, `♦`, `♣`).
  - **Tesseract OCR** fallback for number ranks (2-10).
- **Floating HUD Overlay**:
  - Transparent overlay that sits on top of your poker client.
  - Displays recognized Hero cards, Board cards, and win/tie equities.
  - Interactive **Opponents Selector** (`[-] 1 [+]` buttons) to dynamically adjust simulated random opponents between 1 and 9 in real-time.
- **Robust Simulation Engine**: Calculates equity using efficient Monte Carlo simulations or exact combinations (exhaustive) post-flop.

---

## Prerequisites

1. **Python 3.8+**
2. **Tesseract-OCR**:
   - Install Tesseract-OCR on your system. On Windows, the default installation directory is assumed at `C:\Program Files\Tesseract-OCR\tesseract.exe`.
   - If installed elsewhere, update the path in `detector.py`:
     ```python
     pytesseract.pytesseract.tesseract_cmd = r'C:\Your\Path\To\tesseract.exe'
     ```

---

## Installation

1. Clone or download this repository.
2. Open your terminal in the directory and install python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

---

## How to Set Up & Use

### Step 1: Prepare Templates
Place the template images in the `templates/` directory:
- **Suits**: `s.png` (Spade), `h.png` (Heart), `d.png` (Diamond), `c.png` (Club).
- **JQKA Ranks**: `J.png`, `Q.png`, `K.png`, `A.png`.
*Note: Make sure these templates are cropped tightly to the symbol boundary with white backgrounds.*

### Step 2: Configure ROIs (Region of Interest)
Before running the bot, you must map the location of the cards on your poker client screen:
1. Run the editor:
   ```bash
   python main.py --roi
   ```
2. A fullscreen canvas and a floating **ROI Live Preview** window will appear.
3. Select an ROI target key from the control panel (e.g., `hero1`, `flop1`).
4. Click and drag on the screen to draw a box around the card.
5. If the card is tilted, adjust the **Rotation** slider or use the quick buttons (`+1°`, `-90°`, etc.) until the card appears straight in the live preview.
6. Adjust the **Split Ratio** slider so the dashed green line separates the rank text from the suit symbol.
7. Click **Save config.json** to save the coordinates. Once mapped, exit the editor.

### Step 3: Run the Bot
1. Run the bot overlay:
   ```bash
   python main.py
   ```
2. The HUD transparent window will float on top of your screen. You can drag and position it anywhere.
3. As cards appear on the screen inside the saved ROIs, the HUD will automatically detect the values, calculate equity, and update the win/tie percentages.
4. Click the `+` and `-` buttons in the overlay to change the number of active opponents. Equity calculations will adapt instantly.

---

## Project Structure

- `main.py`: Orchestrates the main loop, detection thread, equity thread, and HUD initialization.
- `roi_editor.py`: Tkinter-based fullscreen ROI configurator with rotation controls and live crop preview window.
- `detector.py`: Grabs screen content, applies rotation, splits regions, and recognizes card ranks/suits.
- `equity_engine.py`: Simulates Texas Hold'em hands using Monte Carlo and exhaustive hand combinations.
- `overlay.py`: Transparent floating GUI HUD with interactive opponents inputs.
- `config.json`: Stores custom coordinate boxes, rotation parameters, and split ratios.
- `templates/`: Directory containing templates for cards suits and JQKA ranks.

---

## Disclaimers
This software is intended purely for educational and research purposes. Using it in real-money poker clients may violate their terms of service and lead to account bans. Use at your own risk.
