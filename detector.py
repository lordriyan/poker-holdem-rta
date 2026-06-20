import cv2
import mss
import numpy as np
import os
import logging
import pytesseract

# IMPORTANT: You must install Tesseract-OCR on Windows.
# Update the path below if you install it in a different directory.
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def rotate_image(image, angle):
    if angle == 0:
        return image
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    
    # Sample background color from top-left corner
    if len(image.shape) == 3:
        bg_color = [int(c) for c in image[0, 0]]
    else:
        bg_color = int(image[0, 0])
        
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=bg_color)
    return rotated

class CardDetector:
    def __init__(self, templates_dir="templates", threshold=0.75, split_ratio=0.70):
        self.sct = mss.mss()
        self.templates_dir = templates_dir
        self.threshold = threshold
        self.split_ratio = split_ratio
        self.suit_templates = {}
        
        # Configure Tesseract for single line character reading
        self.ocr_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=2345678910JQKA'
        
        # Verify tesseract is installed
        if not os.path.exists(pytesseract.pytesseract.tesseract_cmd):
            logging.warning("[WARNING] Tesseract-OCR executable not found at C:\\Program Files\\Tesseract-OCR\\tesseract.exe")
            
        self.load_suit_templates()
        self.load_rank_templates()

    def load_suit_templates(self):
        """Loads the 4 suit templates: s.png, h.png, d.png, c.png"""
        if not os.path.exists(self.templates_dir):
            logging.warning(f"[WARNING] Templates directory '{self.templates_dir}' not found.")
            return
            
        loaded_count = 0
        for suit in ['s', 'h', 'd', 'c']:
            filename = f"{suit}.png"
            path = os.path.join(self.templates_dir, filename)
            if os.path.exists(path):
                img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    # Crop template to its exact bounding box to remove any user-added whitespace
                    _, thresh = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
                    x, y, w, h = cv2.boundingRect(thresh)
                    if w > 5 and h > 5:
                        self.suit_templates[suit] = img[y:y+h, x:x+w]
                    else:
                        self.suit_templates[suit] = img # fallback
                    loaded_count += 1
            else:
                logging.warning(f"[WARNING] Missing suit template: {filename}. Please create it!")
                
        logging.info(f"[INFO] Loaded {loaded_count}/4 suit templates.")

    def load_rank_templates(self):
        """Loads rank templates: J.png, Q.png, K.png, A.png"""
        self.rank_templates = {}
        if not os.path.exists(self.templates_dir):
            logging.warning(f"[WARNING] Templates directory '{self.templates_dir}' not found.")
            return
            
        loaded_count = 0
        for rank in ['J', 'Q', 'K', 'A']:
            found = False
            for ext in ['.png', '.PNG']:
                # Check uppercase and lowercase filenames
                for name in [f"{rank}{ext}", f"{rank.lower()}{ext}"]:
                    path = os.path.join(self.templates_dir, name)
                    if os.path.exists(path):
                        img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                        if img is not None:
                            # Crop template to its exact bounding box
                            _, thresh = cv2.threshold(img, 200, 255, cv2.THRESH_BINARY_INV)
                            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                            if contours:
                                c = max(contours, key=cv2.contourArea)
                                x, y, w, h = cv2.boundingRect(c)
                                if w > 5 and h > 5:
                                    self.rank_templates[rank] = img[y:y+h, x:x+w]
                                else:
                                    self.rank_templates[rank] = img
                            else:
                                self.rank_templates[rank] = img
                            loaded_count += 1
                            found = True
                            break
                if found:
                    break
            if not found:
                logging.warning(f"[WARNING] Missing rank template: {rank}.png. Please create it!")
                
        logging.info(f"[INFO] Loaded {loaded_count}/4 rank templates for JQKA.")

    def _detect_suit(self, image_bgr):
        """
        Detects the suit using OpenCV matchTemplate, with Red/Black pre-filtering.
        """
        if not self.suit_templates:
            return None
            
        # Determine if the symbol is Red or Black
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        lower_red1 = np.array([0, 50, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 50, 50])
        upper_red2 = np.array([180, 255, 255])
        
        mask_red = cv2.bitwise_or(cv2.inRange(hsv, lower_red1, upper_red1), 
                                  cv2.inRange(hsv, lower_red2, upper_red2))
                                  
        is_red = cv2.countNonZero(mask_red) > 20
        allowed_suits = ['h', 'd'] if is_red else ['s', 'c']
            
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        
        # Find the exact bounding box of the symbol in the image
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
            
        c = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(c)
        if w < 5 or h < 5:
            return None
            
        symbol_roi = gray[y:y+h, x:x+w]
        
        best_suit = None
        best_val = -1
        
        for suit, template in self.suit_templates.items():
            if suit not in allowed_suits:
                continue
                
            # Resize template to exactly match the symbol's width and height
            resized_template = cv2.resize(template, (w, h))
            res = cv2.matchTemplate(symbol_roi, resized_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            
            if max_val > best_val:
                best_val = max_val
                best_suit = suit
                
        # Lower strictness since we are forcing exact size matching
        if best_val >= 0.50:
            return best_suit
        return None
            
    def _detect_rank(self, image_bgr):
        """
        Detects the rank from the image. For J, Q, K, A, we use template matching.
        """
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        
        # Try template matching for JQKA first if templates exist
        if hasattr(self, 'rank_templates') and self.rank_templates:
            _, thresh_rank = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
            contours, _ = cv2.findContours(thresh_rank, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if contours:
                c = max(contours, key=cv2.contourArea)
                rx, ry, rw, rh = cv2.boundingRect(c)
                
                if rw > 5 and rh > 5:
                    rank_roi_binary = thresh_rank[ry:ry+rh, rx:rx+rw]
                    
                    best_rank = None
                    best_val = -1
                    
                    for rank, template in self.rank_templates.items():
                        _, template_binary = cv2.threshold(template, 200, 255, cv2.THRESH_BINARY_INV)
                        resized_template = cv2.resize(template_binary, (rw, rh))
                        
                        res = cv2.matchTemplate(rank_roi_binary, resized_template, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, _ = cv2.minMaxLoc(res)
                        
                        if max_val > best_val:
                            best_val = max_val
                            best_rank = rank
                            
                    # Using a threshold of 0.60 to confirm the match
                    if best_val >= 0.60:
                        gray_resized = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
                        _, thresh_debug = cv2.threshold(gray_resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                        thresh_debug = cv2.copyMakeBorder(thresh_debug, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=[255, 255, 255])
                        return best_rank, thresh_debug
                        
        # OCR Fallback for numbers (2-10) or if template match didn't succeed
        gray_resized = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        _, thresh = cv2.threshold(gray_resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        thresh = cv2.copyMakeBorder(thresh, 30, 30, 30, 30, cv2.BORDER_CONSTANT, value=[255, 255, 255])
        
        try:
            text = pytesseract.image_to_string(thresh, config=self.ocr_config)
            text = text.strip().upper()
            
            # Post-process common OCR misreads
            if '10' in text or text == '0' or text == '1': return 'T', thresh
            if text == 'I' or text == 'L': return '1', thresh
            if text == 'B' or text == '8': return '8', thresh
            if text == 'G' or text == '6': return '6', thresh
            if text == 'S' or text == '5': return '5', thresh
            if text == 'Z' or text == '2': return '2', thresh
            if text == 'A' or text == '4':
                if '4' in text: return '4', thresh
                return 'A', thresh
                
            # Clean string
            for char in text:
                if char in ['2','3','4','5','6','7','8','9','T','J','Q','K','A']:
                    return char, thresh
                    
        except Exception as e:
            logging.error(f"[ERROR] OCR Failed: {e}")
            
        return None, thresh

    def detect_card(self, image_bgr):
        """
        Returns the card string (e.g. "As") or None, along with debug images.
        """
        h, w = image_bgr.shape[:2]
        if h < 20 or w < 20:
            return None
            
        # Split image based on configured ratio
        split_y = int(h * self.split_ratio)
        
        rank_img = image_bgr[0:split_y, :]
        suit_img = image_bgr[split_y:h, :]
        
        rank, thresh = self._detect_rank(rank_img)
        suit = self._detect_suit(suit_img)
        
        if rank and suit:
            return rank + suit, thresh, suit_img, rank, suit
        return None, thresh, suit_img, rank, suit

    def capture_rois(self, rois):
        results = {}
        for name, info in rois.items():
            if isinstance(info, dict):
                bbox = info.get("bbox", [0, 0, 0, 0])
                rotation = info.get("rotation", 0)
            else:
                bbox = info
                rotation = 0
                
            x, y, w, h = bbox
            if w <= 0 or h <= 0:
                results[name] = None
                continue
            
            monitor = {"top": y, "left": x, "width": w, "height": h}
            try:
                img = np.array(self.sct.grab(monitor))
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                if rotation != 0:
                    img_bgr = rotate_image(img_bgr, rotation)
                results[name] = img_bgr
            except Exception as e:
                logging.error(f"[ERROR] Failed to capture ROI {name}: {e}")
                results[name] = None
                
        return results
