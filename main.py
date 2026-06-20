import sys
import threading
import time
import json
import logging
import cv2
import numpy as np
from detector import CardDetector
from equity_engine import EquityCalculator
from overlay import OverlayWindow

# Setup logging
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

class PokerBot:
    def __init__(self):
        self.running = True
        
        # Shared state
        self.cards = {
            "hero1": None, "hero2": None,
            "flop1": None, "flop2": None, "flop3": None,
            "turn": None, "river": None
        }
        
        self.equity_result = {"hero": 0.0, "tie": 0.0}
        self.calculating = False
        self.needs_recalc = True
        self.debug_mode = "--debug" in sys.argv
        
        # Load config
        self.config = self.load_config()
        self.rois = self.config.get("rois", {})
        self.threshold = self.config.get("threshold", 0.75)
        self.split_ratio = self.config.get("split_ratio", 0.70)
        
        # Components
        self.detector = CardDetector(threshold=self.threshold, split_ratio=self.split_ratio)
        self.calculator = EquityCalculator()
        self.overlay = OverlayWindow()
        
    def load_config(self):
        try:
            with open("config.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logging.error("[ERROR] config.json not found. Run with --roi to create one.")
            return {"rois": {}, "threshold": 0.85}

    def detection_loop(self):
        if self.debug_mode:
            cv2.namedWindow("CheatPoker Debug", cv2.WINDOW_NORMAL)
        while self.running:
            start_time = time.time()
            
            # Capture ROIs
            roi_images = self.detector.capture_rois(self.rois)
            
            changed = False
            debug_images = []
            
            for key, img in roi_images.items():
                if img is None:
                    continue
                card_str, thresh, suit_img, rank_match, suit_match = self.detector.detect_card(img)
                
                if self.debug_mode:
                    # --- DEBUG VIEW ---
                    thresh_bgr = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
                    h_s, w_s = suit_img.shape[:2]
                    h_t, w_t = thresh_bgr.shape[:2]
                    
                    if w_s > 0 and h_s > 0:
                        suit_resized = cv2.resize(suit_img, (w_t, int(h_s * (w_t/w_s))))
                        stacked = np.vstack((thresh_bgr, suit_resized))
                    else:
                        stacked = thresh_bgr
                        
                    # Show exactly what OCR and Template Match found
                    r_text = rank_match if rank_match else "?"
                    s_text = suit_match if suit_match else "?"
                    label1 = f"{key}: {card_str if card_str else '??'}"
                    label2 = f"R:{r_text} S:{s_text}"
                    
                    cv2.putText(stacked, label1, (5, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    cv2.putText(stacked, label2, (5, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                    
                    debug_images.append(cv2.resize(stacked, (150, 250)))

                if self.cards.get(key) != card_str:
                    self.cards[key] = card_str
                    changed = True
            
            if self.debug_mode and debug_images:
                debug_canvas = np.hstack(debug_images)
                cv2.imshow("CheatPoker Debug", debug_canvas)
                cv2.waitKey(1)
                    
            if changed:
                logging.info(f"[INFO] Cards updated: {self.cards}")
                self.needs_recalc = True
                
            # Target ~10 FPS
            elapsed = time.time() - start_time
            sleep_time = max(0, 0.1 - elapsed)
            time.sleep(sleep_time)

    def equity_loop(self):
        logging.info("[INFO] Started equity thread.")
        while self.running:
            if self.needs_recalc:
                self.needs_recalc = False
                self.calculating = True
                
                hero_cards = []
                if self.cards["hero1"]: hero_cards.append(self.cards["hero1"])
                if self.cards["hero2"]: hero_cards.append(self.cards["hero2"])
                
                board_cards = []
                for k in ["flop1", "flop2", "flop3", "turn", "river"]:
                    if self.cards[k]: board_cards.append(self.cards[k])
                
                if len(hero_cards) == 2:
                    # Decide mode
                    # If board is full or almost full, exhaustive is fast.
                    # Preflop -> monte carlo
                    mode = "exhaustive" if len(board_cards) >= 3 else "monte_carlo"
                    iterations = 10000 if mode == "monte_carlo" else 0
                    
                    try:
                        # Allow max 0.2s for calculations to stay responsive
                        res = self.calculator._calculate([hero_cards], board_cards, mode=mode, iterations=iterations, max_time=0.2)
                        self.equity_result = {"hero": res["hero"], "tie": res["tie"]}
                    except Exception as e:
                        logging.error(f"[ERROR] Error calculating equity: {e}")
                else:
                    self.equity_result = {"hero": 0.0, "tie": 0.0}
                    
                self.calculating = False
                
            time.sleep(0.05)
            
    def update_overlay(self):
        if not self.running:
            return
            
        hero = []
        if self.cards["hero1"]: hero.append(self.cards["hero1"])
        if self.cards["hero2"]: hero.append(self.cards["hero2"])
        
        board = []
        for k in ["flop1", "flop2", "flop3", "turn", "river"]:
            if self.cards[k]: board.append(self.cards[k])
            
        if self.calculating:
            self.overlay.update_data(hero, board, None, None)
        else:
            self.overlay.update_data(hero, board, self.equity_result["hero"], self.equity_result["tie"])
            
        # Update UI every 100ms
        self.overlay.root.after(100, self.update_overlay)

    def run(self):
        # Start background threads
        det_thread = threading.Thread(target=self.detection_loop, daemon=True)
        eq_thread = threading.Thread(target=self.equity_loop, daemon=True)
        
        det_thread.start()
        eq_thread.start()
        
        # Start overlay event loop in the main thread
        self.update_overlay()
        
        try:
            self.overlay.start()
        except KeyboardInterrupt:
            logging.info("[INFO] Shutting down...")
        finally:
            self.running = False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--roi":
        logging.info("[INFO] Starting ROI Editor...")
        from roi_editor import ROIEditor
        app = ROIEditor()
        app.run()
    else:
        logging.info("[INFO] Starting Texas Hold'em Bot...")
        bot = PokerBot()
        bot.run()
