import time
import json
import threading
import ctypes
from pynput import mouse, keyboard

# =========================
# CONFIG
# =========================

OUTPUT_FILE = "recording.txt"

# =========================
# LOW LEVEL SENDINPUT
# =========================

PUL = ctypes.POINTER(ctypes.c_ulong)

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL),
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("mi", MOUSEINPUT),
    ]

INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100

XBUTTON1 = 0x0001
XBUTTON2 = 0x0002

def send_mouse_event(x, y, flags, data=0):
    screen_width = ctypes.windll.user32.GetSystemMetrics(0)
    screen_height = ctypes.windll.user32.GetSystemMetrics(1)

    abs_x = int(x * 65535 / screen_width)
    abs_y = int(y * 65535 / screen_height)

    inp = INPUT(
        type=INPUT_MOUSE,
        mi=MOUSEINPUT(
            dx=abs_x,
            dy=abs_y,
            mouseData=data,
            dwFlags=flags | MOUSEEVENTF_ABSOLUTE,
            time=0,
            dwExtraInfo=None,
        ),
    )

    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

# =========================
# RECORDER
# =========================

class Recorder:
    def __init__(self):
        self.recording = False
        self.start_time = None
        self.events = []

    def start(self):
        self.events = []
        self.start_time = time.perf_counter()
        self.recording = True
        print("REC START")

    def stop(self):
        self.recording = False
        print("REC STOP")
        self.save()

    def save(self):
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            for e in self.events:
                f.write(json.dumps(e) + "\n")
        print(f"Saved {len(self.events)} events")

    def record_move(self, x, y):
        if not self.recording:
            return

        t = time.perf_counter() - self.start_time
        self.events.append({
            "type": "move",
            "t": t,
            "x": x,
            "y": y
        })

    def record_click(self, x, y, button, pressed):
        if not self.recording:
            return

        t = time.perf_counter() - self.start_time

        btn = str(button)

        self.events.append({
            "type": "click",
            "t": t,
            "x": x,
            "y": y,
            "button": btn,
            "pressed": pressed
        })

# =========================
# PLAYER
# =========================

class Player:
    def __init__(self, file):
        self.file = file
        self.events = self.load()

    def load(self):
        events = []
        with open(self.file, "r", encoding="utf-8") as f:
            for line in f:
                events.append(json.loads(line))
        return events

    def play(self):
        print("PLAY START")
        start = time.perf_counter()

        for e in self.events:
            while time.perf_counter() - start < e["t"]:
                pass

            if e["type"] == "move":
                send_mouse_event(e["x"], e["y"], MOUSEEVENTF_MOVE)

            elif e["type"] == "click":
                btn = e["button"]

                if "left" in btn:
                    flag = MOUSEEVENTF_LEFTDOWN if e["pressed"] else MOUSEEVENTF_LEFTUP
                    send_mouse_event(e["x"], e["y"], flag)

                elif "right" in btn:
                    flag = MOUSEEVENTF_RIGHTDOWN if e["pressed"] else MOUSEEVENTF_RIGHTUP
                    send_mouse_event(e["x"], e["y"], flag)

                elif "middle" in btn:
                    flag = MOUSEEVENTF_MIDDLEDOWN if e["pressed"] else MOUSEEVENTF_MIDDLEUP
                    send_mouse_event(e["x"], e["y"], flag)

                elif "x1" in btn:
                    flag = MOUSEEVENTF_XDOWN if e["pressed"] else MOUSEEVENTF_XUP
                    send_mouse_event(e["x"], e["y"], flag, XBUTTON1)

                elif "x2" in btn:
                    flag = MOUSEEVENTF_XDOWN if e["pressed"] else MOUSEEVENTF_XUP
                    send_mouse_event(e["x"], e["y"], flag, XBUTTON2)

        print("PLAY END")

# =========================
# GLOBAL CONTROL
# =========================

rec = Recorder()

def on_move(x, y):
    rec.record_move(x, y)

def on_click(x, y, button, pressed):
    rec.record_click(x, y, button, pressed)

def on_key(key):
    global rec

    if key == keyboard.Key.f8:
        rec.start()

    elif key == keyboard.Key.f9:
        rec.stop()

    elif key == keyboard.Key.f10:
        Player(OUTPUT_FILE).play()

# =========================

mouse.Listener(on_move=on_move, on_click=on_click).start()
keyboard.Listener(on_press=on_key).start()

print("F8 = record | F9 = stop | F10 = play")

while True:
    time.sleep(1)