import tkinter as tk
import mss
import json
import os
import cv2
import numpy as np
from PIL import Image, ImageTk
from detector import rotate_image

CONFIG_FILE = "config.json"
ROI_KEYS = ["hero1", "hero2", "flop1", "flop2", "flop3", "turn", "river"]

def get_rotated_rect_points(x, y, w, h, angle_degrees):
    cx = x + w / 2
    cy = y + h / 2
    hw = w / 2
    hh = h / 2
    
    corners = [
        (-hw, -hh),
        (hw, -hh),
        (hw, hh),
        (-hw, hh)
    ]
    
    import math
    rad = math.radians(angle_degrees)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    
    rotated = []
    for dx, dy in corners:
        rx = cx + (dx * cos_a - dy * sin_a)
        ry = cy + (dx * sin_a + dy * cos_a)
        rotated.extend([rx, ry])
    return rotated

def get_rotated_split_line_points(x, y, w, h, split_ratio, angle_degrees):
    cx = x + w / 2
    cy = y + h / 2
    hw = w / 2
    hh = h / 2
    dy_split = -hh + h * split_ratio
    
    p1 = (-hw, dy_split)
    p2 = (hw, dy_split)
    
    import math
    rad = math.radians(angle_degrees)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    
    rx1 = cx + (p1[0] * cos_a - p1[1] * sin_a)
    ry1 = cy + (p1[0] * sin_a + p1[1] * cos_a)
    rx2 = cx + (p2[0] * cos_a - p2[1] * sin_a)
    ry2 = cy + (p2[0] * sin_a + p2[1] * cos_a)
    
    return [rx1, ry1, rx2, ry2]

class ROIEditor:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ROI Editor")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg='black')
        
        self.config = self.load_config()
        
        # Normalize rois to dict format: {"bbox": [x, y, w, h], "rotation": angle}
        raw_rois = self.config.get("rois", {})
        self.rois = {}
        for k in ROI_KEYS:
            val = raw_rois.get(k, [0, 0, 100, 100])
            if isinstance(val, dict):
                self.rois[k] = {
                    "bbox": val.get("bbox", [0, 0, 100, 100]),
                    "rotation": val.get("rotation", 0)
                }
            else:
                self.rois[k] = {
                    "bbox": val,
                    "rotation": 0
                }
                
        self.split_ratio = tk.DoubleVar(value=self.config.get("split_ratio", 0.70))
        
        # Capture screenshot for background
        with mss.mss() as sct:
            monitor = sct.monitors[1] # Primary monitor
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            self.bg_image = ImageTk.PhotoImage(img)
            
        self.sct = mss.mss() # Persistent instance for live preview
        
        self.canvas = tk.Canvas(self.root, cursor="cross")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self.bg_image, anchor="nw")
        
        self.current_key = tk.StringVar(value=ROI_KEYS[0])
        self.current_key.trace_add("write", self.on_key_change)
        self.split_ratio.trace_add("write", self.on_key_change)
        
        self.rotation_var = tk.IntVar(value=self.rois[ROI_KEYS[0]]["rotation"])
        self.rotation_var.trace_add("write", self.on_rotation_change)
        
        self.setup_ui()
        self.setup_preview_window()
        self.draw_all_rects()
        
        # Start update preview loop
        self.update_preview_loop()
        
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {"threshold": 0.75, "rois": {}}
        
    def setup_ui(self):
        ui_frame = tk.Frame(self.root, bg="#222222", bd=2, relief="raised")
        ui_frame.place(x=20, y=20)
        
        tk.Label(ui_frame, text="Select ROI to edit:", bg="#222222", fg="white", font=("Arial", 12, "bold")).pack(pady=(10, 5), padx=10)
        
        for key in ROI_KEYS:
            tk.Radiobutton(ui_frame, text=key, variable=self.current_key, value=key, 
                           bg="#333333", fg="white", selectcolor="#555555", indicatoron=0, 
                           width=15, font=("Arial", 10)).pack(pady=2, padx=10)
                           
        tk.Label(ui_frame, text="Split Ratio (Rank/Suit):", bg="#222222", fg="white", font=("Arial", 10, "bold")).pack(pady=(15, 0), padx=10)
        self.slider = tk.Scale(ui_frame, variable=self.split_ratio, from_=0.1, to=0.9, resolution=0.05, orient="horizontal", bg="#222222", fg="white", highlightthickness=0)
        self.slider.pack(pady=(0, 10), padx=10, fill="x")
                           
        tk.Label(ui_frame, text="Rotation (Degrees):", bg="#222222", fg="white", font=("Arial", 10, "bold")).pack(pady=(10, 0), padx=10)
        self.rot_slider = tk.Scale(ui_frame, variable=self.rotation_var, from_=-180, to=180, resolution=1, orient="horizontal", bg="#222222", fg="white", highlightthickness=0)
        self.rot_slider.pack(pady=(0, 5), padx=10, fill="x")
        
        btn_frame = tk.Frame(ui_frame, bg="#222222")
        btn_frame.pack(pady=5, padx=10, fill="x")
        
        tk.Button(btn_frame, text="-90°", command=lambda: self.adjust_rotation(-90), bg="#444444", fg="white", font=("Arial", 9, "bold")).pack(side="left", expand=True, fill="x", padx=2)
        tk.Button(btn_frame, text="-1°", command=lambda: self.adjust_rotation(-1), bg="#444444", fg="white", font=("Arial", 9, "bold")).pack(side="left", expand=True, fill="x", padx=2)
        tk.Button(btn_frame, text="+1°", command=lambda: self.adjust_rotation(1), bg="#444444", fg="white", font=("Arial", 9, "bold")).pack(side="left", expand=True, fill="x", padx=2)
        tk.Button(btn_frame, text="+90°", command=lambda: self.adjust_rotation(90), bg="#444444", fg="white", font=("Arial", 9, "bold")).pack(side="left", expand=True, fill="x", padx=2)
        
        tk.Button(ui_frame, text="Toggle Live Preview", command=self.toggle_preview_window, 
                  bg="#17a2b8", fg="white", font=("Arial", 10, "bold")).pack(pady=(10, 10), padx=10, fill="x")
                           
        tk.Button(ui_frame, text="Save config.json", command=self.save_config, 
                  bg="#28a745", fg="white", font=("Arial", 10, "bold")).pack(pady=(15, 5), padx=10, fill="x")
        tk.Button(ui_frame, text="Exit Editor", command=self.root.destroy, 
                  bg="#dc3545", fg="white", font=("Arial", 10, "bold")).pack(pady=(5, 10), padx=10, fill="x")

    def on_key_change(self, *args):
        key = self.current_key.get()
        if key in self.rois:
            self.rotation_var.set(self.rois[key]["rotation"])
        self.draw_all_rects()
        
    def adjust_rotation(self, amount):
        curr = self.rotation_var.get()
        new_val = curr + amount
        if new_val > 180:
            new_val -= 360
        elif new_val < -180:
            new_val += 360
        self.rotation_var.set(new_val)
        
    def on_rotation_change(self, *args):
        key = self.current_key.get()
        if key in self.rois:
            self.rois[key]["rotation"] = self.rotation_var.get()
            self.draw_all_rects()

    def setup_preview_window(self):
        self.preview_window = tk.Toplevel(self.root)
        self.preview_window.title("ROI Live Preview")
        self.preview_window.geometry("640x340+100+100")
        self.preview_window.configure(bg='#1c1c1e')
        self.preview_window.attributes("-topmost", True)
        self.preview_window.protocol("WM_DELETE_WINDOW", self.on_preview_close)
        
        info_frame = tk.Frame(self.preview_window, bg='#1c1c1e')
        info_frame.pack(fill='x', pady=(10, 5))
        self.preview_info_label = tk.Label(
            info_frame, 
            text="Active ROI: None", 
            bg='#1c1c1e', 
            fg='#30d158',
            font=("Arial", 11, "bold")
        )
        self.preview_info_label.pack()
        
        panels_frame = tk.Frame(self.preview_window, bg='#1c1c1e')
        panels_frame.pack(fill='both', expand=True, padx=15, pady=10)
        
        panels_frame.columnconfigure(0, weight=1)
        panels_frame.columnconfigure(1, weight=1)
        panels_frame.columnconfigure(2, weight=1)
        
        self.panel_card = tk.Label(panels_frame, text="Card Crop", bg='#2c2c2e', fg='white', relief="solid", bd=1)
        self.panel_card.grid(row=0, column=0, padx=8, pady=5, sticky="nsew")
        
        self.panel_rank = tk.Label(panels_frame, text="Rank Preproc (OTSU)", bg='#2c2c2e', fg='white', relief="solid", bd=1)
        self.panel_rank.grid(row=0, column=1, padx=8, pady=5, sticky="nsew")
        
        self.panel_suit = tk.Label(panels_frame, text="Suit Preproc (INV)", bg='#2c2c2e', fg='white', relief="solid", bd=1)
        self.panel_suit.grid(row=0, column=2, padx=8, pady=5, sticky="nsew")
        
        tk.Label(panels_frame, text="Rotated Crop (with Split)", bg='#1c1c1e', fg='#aeaeae', font=("Arial", 9)).grid(row=1, column=0, pady=(2, 10))
        tk.Label(panels_frame, text="Rank (OCR / Template)", bg='#1c1c1e', fg='#aeaeae', font=("Arial", 9)).grid(row=1, column=1, pady=(2, 10))
        tk.Label(panels_frame, text="Suit (Template)", bg='#1c1c1e', fg='#aeaeae', font=("Arial", 9)).grid(row=1, column=2, pady=(2, 10))

    def on_preview_close(self):
        self.preview_window.withdraw()
        
    def toggle_preview_window(self):
        if self.preview_window.winfo_viewable():
            self.preview_window.withdraw()
        else:
            self.preview_window.deiconify()
            self.preview_window.attributes("-topmost", True)

    def update_preview_loop(self):
        if not self.root.winfo_exists():
            return
            
        key = self.current_key.get()
        info = self.rois.get(key, None)
        
        if info and self.preview_window.winfo_viewable():
            x, y, w, h = info["bbox"]
            rotation = info["rotation"]
            split_ratio = self.split_ratio.get()
            
            self.preview_info_label.configure(text=f"ROI: {key}  |  Rotation: {rotation}°  |  Split: {split_ratio:.2f}")
            
            if w > 10 and h > 10:
                try:
                    monitor = {"top": y, "left": x, "width": w, "height": h}
                    sct_img = self.sct.grab(monitor)
                    img_np = np.array(sct_img)
                    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
                    
                    if rotation != 0:
                        img_bgr = rotate_image(img_bgr, rotation)
                    
                    card_preview = img_bgr.copy()
                    ch, cw = card_preview.shape[:2]
                    split_y = int(ch * split_ratio)
                    cv2.line(card_preview, (0, split_y), (cw, split_y), (0, 255, 0), 2)
                    
                    rank_img = img_bgr[0:split_y, :]
                    suit_img = img_bgr[split_y:ch, :]
                    
                    if rank_img.size > 0:
                        rank_gray = cv2.cvtColor(rank_img, cv2.COLOR_BGR2GRAY)
                        rank_gray = cv2.resize(rank_gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                        _, rank_thresh = cv2.threshold(rank_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    else:
                        rank_thresh = np.zeros((100, 100), dtype=np.uint8)
                        
                    if suit_img.size > 0:
                        suit_gray = cv2.cvtColor(suit_img, cv2.COLOR_BGR2GRAY)
                        _, suit_thresh = cv2.threshold(suit_gray, 200, 255, cv2.THRESH_BINARY_INV)
                    else:
                        suit_thresh = np.zeros((100, 100), dtype=np.uint8)
                    
                    def prep_pil_image(cv_img, is_color=True):
                        if is_color:
                            rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
                            pil_img = Image.fromarray(rgb)
                        else:
                            pil_img = Image.fromarray(cv_img)
                        pil_img.thumbnail((160, 200))
                        return ImageTk.PhotoImage(pil_img)
                        
                    card_tk = prep_pil_image(card_preview, is_color=True)
                    rank_tk = prep_pil_image(rank_thresh, is_color=False)
                    suit_tk = prep_pil_image(suit_thresh, is_color=False)
                    
                    self._card_tk = card_tk
                    self._rank_tk = rank_tk
                    self._suit_tk = suit_tk
                    
                    self.panel_card.configure(image=card_tk, text="")
                    self.panel_rank.configure(image=rank_tk, text="")
                    self.panel_suit.configure(image=suit_tk, text="")
                except Exception as e:
                    self.panel_card.configure(text=f"Error: {e}", image="")
                    self.panel_rank.configure(text="", image="")
                    self.panel_suit.configure(text="", image="")
            else:
                self.panel_card.configure(text="ROI too small", image="")
                self.panel_rank.configure(text="", image="")
                self.panel_suit.configure(text="", image="")
        else:
            self.preview_info_label.configure(text="Active ROI: None (or Preview Hidden)")
            
        self.root.after(100, self.update_preview_loop)

    def draw_all_rects(self):
        self.canvas.delete("roi_rect")
        self.canvas.delete("roi_text")
        
        # Clean up any leftover temporary dragging items
        if hasattr(self, 'rect_id') and self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        if hasattr(self, 'line_id') and self.line_id:
            self.canvas.delete(self.line_id)
            self.line_id = None
            
        for key, info in self.rois.items():
            x, y, w, h = info["bbox"]
            rotation = info["rotation"]
            if w > 0 and h > 0:
                color = "#00FF00" if key == self.current_key.get() else "#FFFF00"
                width = 3 if key == self.current_key.get() else 1
                
                # Draw outer polygon rotated
                points = get_rotated_rect_points(x, y, w, h, rotation)
                self.canvas.create_polygon(points, fill='', outline=color, width=width, tags="roi_rect")
                
                # Draw split line rotated
                split_points = get_rotated_split_line_points(x, y, w, h, self.split_ratio.get(), rotation)
                self.canvas.create_line(split_points, fill=color, dash=(4,4), width=width, tags="roi_rect")
                
                # Draw text label at the top-left vertex of the rotated box for clarity
                lbl = f"{key} ({rotation}°)" if rotation != 0 else key
                text_id = self.canvas.create_text(points[0], points[1]-10, text=lbl, fill="black", anchor="w", font=("Arial", 12, "bold"), tags="roi_text")
                bbox_text = self.canvas.bbox(text_id)
                if bbox_text:
                    self.canvas.create_rectangle(bbox_text[0]-2, bbox_text[1]-2, bbox_text[2]+2, bbox_text[3]+2, fill=color, outline=color, tags="roi_text")
                    self.canvas.tag_raise(text_id)

    def on_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        
        key = self.current_key.get()
        info = self.rois.get(key, {"bbox": [0, 0, 0, 0], "rotation": 0})
        x, y, w, h = info["bbox"]
        
        self.mode = "draw"
        if w > 0 and h > 0:
            # Check if click is inside the currently selected ROI
            if x <= event.x <= x + w and y <= event.y <= y + h:
                self.mode = "move"
                self.orig_x = x
                self.orig_y = y
                # Hide all to show only the moving one
                self.canvas.delete("roi_rect")
                self.canvas.delete("roi_text")
                
                rotation = info["rotation"]
                points = get_rotated_rect_points(x, y, w, h, rotation)
                self.rect_id = self.canvas.create_polygon(points, fill='', outline="#00FF00", width=3)
                
                split_points = get_rotated_split_line_points(x, y, w, h, self.split_ratio.get(), rotation)
                self.line_id = self.canvas.create_line(split_points, fill="#00FF00", dash=(4,4), width=2)
                return
                
        # Draw mode: initial size 0, rotation 0
        points = get_rotated_rect_points(self.start_x, self.start_y, 0, 0, 0)
        self.rect_id = self.canvas.create_polygon(points, fill='', outline="#00FF00", width=3)
        self.line_id = self.canvas.create_line(self.start_x, self.start_y, self.start_x, self.start_y, fill="#00FF00", dash=(4,4), width=2)
        
    def on_drag(self, event):
        if getattr(self, 'mode', 'draw') == "move":
            dx = event.x - self.start_x
            dy = event.y - self.start_y
            x = self.orig_x + dx
            y = self.orig_y + dy
            key = self.current_key.get()
            w, h = self.rois[key]["bbox"][2], self.rois[key]["bbox"][3]
            rotation = self.rois[key]["rotation"]
            
            points = get_rotated_rect_points(x, y, w, h, rotation)
            self.canvas.coords(self.rect_id, *points)
            
            split_points = get_rotated_split_line_points(x, y, w, h, self.split_ratio.get(), rotation)
            self.canvas.coords(self.line_id, *split_points)
        else:
            cur_x, cur_y = (event.x, event.y)
            x = min(self.start_x, cur_x)
            y = min(self.start_y, cur_y)
            w = abs(cur_x - self.start_x)
            h = abs(cur_y - self.start_y)
            
            points = get_rotated_rect_points(x, y, w, h, 0)
            self.canvas.coords(self.rect_id, *points)
            
            min_y, max_y = min(self.start_y, cur_y), max(self.start_y, cur_y)
            min_x, max_x = min(self.start_x, cur_x), max(self.start_x, cur_x)
            split_y = min_y + int((max_y - min_y) * self.split_ratio.get())
            self.canvas.coords(self.line_id, min_x, split_y, max_x, split_y)
        
    def on_release(self, event):
        if getattr(self, 'mode', 'draw') == "move":
            dx = event.x - self.start_x
            dy = event.y - self.start_y
            x = self.orig_x + dx
            y = self.orig_y + dy
            
            # Keep within bounds roughly
            x = max(0, x)
            y = max(0, y)
            
            key = self.current_key.get()
            w, h = self.rois[key]["bbox"][2], self.rois[key]["bbox"][3]
            self.rois[key]["bbox"] = [x, y, w, h]
            self.mode = "draw"
        else:
            end_x, end_y = (event.x, event.y)
            x = min(self.start_x, end_x)
            y = min(self.start_y, end_y)
            w = abs(end_x - self.start_x)
            h = abs(end_y - self.start_y)
            
            # Avoid zero size
            if w < 5 or h < 5:
                if hasattr(self, 'rect_id') and self.rect_id: self.canvas.delete(self.rect_id)
                if hasattr(self, 'line_id') and self.line_id: self.canvas.delete(self.line_id)
                self.draw_all_rects()
                return
                
            key = self.current_key.get()
            old_rot = self.rois[key]["rotation"] if key in self.rois else 0
            self.rois[key] = {"bbox": [x, y, w, h], "rotation": old_rot}
            
        self.draw_all_rects()
        
    def save_config(self):
        self.config["rois"] = self.rois
        self.config["split_ratio"] = self.split_ratio.get()
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=4)
        print(f"[INFO] Saved {len(self.rois)} ROIs to {CONFIG_FILE}")
        # Show a brief "Saved!" feedback
        saved_label = tk.Label(self.root, text="Saved!", bg="#28a745", fg="white", font=("Arial", 14, "bold"))
        saved_label.place(relx=0.5, rely=0.1, anchor="center")
        self.root.after(1500, saved_label.destroy)
        
    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = ROIEditor()
    app.run()
