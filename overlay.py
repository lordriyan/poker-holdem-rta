import tkinter as tk
import os

class OverlayWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Poker Equity Overlay")
        
        # Transparent and always on top
        self.root.attributes("-topmost", True)
        self.root.overrideredirect(True) # Remove borders
        self.root.attributes("-alpha", 0.85)
        self.root.configure(bg='black')
        
        # Position initially at top-left
        self.root.geometry("+50+50")
        
        # Draggable logic
        self.root.bind("<ButtonPress-1>", self.start_move)
        self.root.bind("<ButtonRelease-1>", self.stop_move)
        self.root.bind("<B1-Motion>", self.do_move)
        
        self.x = 0
        self.y = 0
        
        # UI Elements
        font_style = ("Consolas", 14, "bold")
        
        self.status_label = tk.Label(self.root, text="Status: LIVE", fg="#00FF00", bg="black", font=("Consolas", 10, "bold"))
        self.status_label.pack(anchor="w", padx=10, pady=(10, 0))
        
        self.hero_label = tk.Label(self.root, text="Hero: ?? ??", fg="white", bg="black", font=font_style)
        self.hero_label.pack(anchor="w", padx=10)
        
        self.board_label = tk.Label(self.root, text="Board: ", fg="white", bg="black", font=font_style)
        self.board_label.pack(anchor="w", padx=10)
        
        # Frame for Villains selection
        self.on_villains_change = None
        villains_frame = tk.Frame(self.root, bg="black")
        villains_frame.pack(anchor="w", padx=10, pady=(5, 5))
        
        tk.Label(villains_frame, text="Opponents: ", fg="#aeaeae", bg="black", font=("Consolas", 10, "bold")).pack(side="left")
        
        self.dec_btn = tk.Button(villains_frame, text="-", command=self.dec_villains, bg="#2c2c2e", fg="white", bd=0, width=2, font=("Consolas", 9, "bold"))
        self.dec_btn.pack(side="left", padx=2)
        
        self.villains_var = tk.IntVar(value=1)
        self.villains_label = tk.Label(villains_frame, text="1", fg="#30d158", bg="black", font=("Consolas", 10, "bold"), width=2)
        self.villains_label.pack(side="left")
        
        self.inc_btn = tk.Button(villains_frame, text="+", command=self.inc_villains, bg="#2c2c2e", fg="white", bd=0, width=2, font=("Consolas", 9, "bold"))
        self.inc_btn.pack(side="left", padx=2)
        
        self.equity_label = tk.Label(self.root, text="Win: --.-% | Tie: --.-%", fg="#FFD700", bg="black", font=("Consolas", 16, "bold"))
        self.equity_label.pack(anchor="w", padx=10, pady=(0, 10))
        
        # Exit button
        self.exit_btn = tk.Button(self.root, text="X", command=self.close, bg="#FF4444", fg="white", bd=0, font=("Consolas", 10, "bold"))
        self.exit_btn.place(relx=1.0, x=-5, y=5, anchor="ne")
        
        # Keep window topmost periodically
        self.keep_topmost()

    def keep_topmost(self):
        self.root.attributes("-topmost", True)
        self.root.after(1000, self.keep_topmost)

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def stop_move(self, event):
        self.x = None
        self.y = None

    def do_move(self, event):
        if self.x is not None and self.y is not None:
            deltax = event.x - self.x
            deltay = event.y - self.y
            x = self.root.winfo_x() + deltax
            y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{x}+{y}")

    def update_data(self, hero_cards, board_cards, equity, tie):
        suit_map = {'s': '♤', 'h': '♥', 'd': '♢', 'c': '♧'}
        
        def format_cards(cards):
            if not cards: return []
            formatted = []
            for c in cards:
                if len(c) == 2:
                    rank = '10' if c[0] == 'T' else c[0]
                    suit = suit_map.get(c[1], c[1])
                    formatted.append(rank + suit)
                else:
                    formatted.append(c)
            return formatted
            
        hero_str = " ".join(format_cards(hero_cards)) if hero_cards else "?? ??"
        board_str = " ".join(format_cards(board_cards)) if board_cards else "Preflop"
        
        self.hero_label.config(text=f"Hero: {hero_str}")
        self.board_label.config(text=f"Board: {board_str}")
        
        if equity is not None and tie is not None:
            self.equity_label.config(text=f"Win: {equity:.1f}% | Tie: {tie:.1f}%")
        else:
            self.equity_label.config(text="Calculating...")

    def dec_villains(self):
        val = self.villains_var.get()
        if val > 1:
            self.villains_var.set(val - 1)
            self.villains_label.config(text=str(val - 1))
            self.on_villains_change_internal()

    def inc_villains(self):
        val = self.villains_var.get()
        if val < 9:
            self.villains_var.set(val + 1)
            self.villains_label.config(text=str(val + 1))
            self.on_villains_change_internal()

    def on_villains_change_internal(self):
        if self.on_villains_change:
            self.on_villains_change(self.villains_var.get())

    def close(self):
        self.root.destroy()
        os._exit(0) # Force quit all threads
        
    def start(self):
        self.root.mainloop()
