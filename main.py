import threading
import time
import tkinter as tk
from tkinter import ttk

import pyautogui
from pynput import mouse, keyboard
from screeninfo import get_monitors

# Sécurité PyAutoGUI : laisse activé le fail-safe.
# Si tu envoies la souris dans un coin de l'écran principal,
# PyAutoGUI lèvera une exception et stoppera l'action.
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.02


class ClickRecorderApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Macro clics")
        self.root.resizable(False, False)
        self.root.attributes("-topmost", True)

        # État
        self.record_armed = False          # F8 appuyé, en attente du 1er clic
        self.is_recording = False          # enregistrement réellement lancé
        self.is_replaying = False          # replay en cours
        self.ignore_mouse_events = False   # pour ne pas réenregistrer pendant replay
        self.events = []                   # liste des clics enregistrés
        self.start_time = None             # démarrage réel au 1er clic
        self.last_recorded_time = None

        # Interface
        self.status_var = tk.StringVar(value="Prêt")
        self.count_var = tk.StringVar(value="0 clic enregistré")
        self.hotkeys_var = tk.StringVar(
            value="F8 = armer | F9 = stop | F10 = replay"
        )

        self.build_ui()
        self.place_on_primary_monitor()

        # Listeners
        self.mouse_listener = mouse.Listener(on_click=self.on_click)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press)

        self.mouse_listener.start()
        self.keyboard_listener.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Boucle de maintien sur écran principal / topmost
        self.keep_on_primary_monitor()

    def build_ui(self):
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)

        ttk.Label(frame, text="Enregistreur de parcours de clics").pack(anchor="w")
        ttk.Label(frame, textvariable=self.status_var).pack(anchor="w", pady=(8, 0))
        ttk.Label(frame, textvariable=self.count_var).pack(anchor="w", pady=(4, 0))
        ttk.Label(frame, textvariable=self.hotkeys_var).pack(anchor="w", pady=(8, 0))

        btns = ttk.Frame(frame)
        btns.pack(fill="x", pady=(12, 0))

        ttk.Button(btns, text="Armer (F8)", command=self.arm_recording).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(btns, text="Stop (F9)", command=self.stop_recording).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(btns, text="Replay (F10)", command=self.replay_recording).pack(
            side="left"
        )

    def get_primary_monitor(self):
        monitors = get_monitors()
        primary = next((m for m in monitors if getattr(m, "is_primary", False)), None)
        return primary if primary else monitors[0]

    def place_on_primary_monitor(self):
        monitor = self.get_primary_monitor()

        width = 360
        height = 150
        x = monitor.x + 20
        y = monitor.y + 20

        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.lift()
        self.root.attributes("-topmost", True)

    def keep_on_primary_monitor(self):
        """
        Réapplique régulièrement la position sur l'écran principal
        et garde la fenêtre au-dessus.
        """
        try:
            self.place_on_primary_monitor()
        except Exception:
            pass

        self.root.after(2000, self.keep_on_primary_monitor)

    def update_status(self, text: str):
        self.root.after(0, lambda: self.status_var.set(text))

    def update_count(self):
        text = f"{len(self.events)} clic{'s' if len(self.events) != 1 else ''} enregistré{'s' if len(self.events) != 1 else ''}"
        self.root.after(0, lambda: self.count_var.set(text))

    def arm_recording(self):
        if self.is_replaying:
            self.update_status("Replay en cours, impossible d'armer")
            return

        self.events.clear()
        self.start_time = None
        self.last_recorded_time = None
        self.record_armed = True
        self.is_recording = False
        self.update_count()
        self.update_status("Armé : en attente du 1er clic gauche")

    def stop_recording(self):
        was_recording = self.record_armed or self.is_recording
        self.record_armed = False
        self.is_recording = False

        if was_recording:
            if self.events:
                self.update_status("Enregistrement stoppé")
            else:
                self.update_status("Stop : aucun clic enregistré")
        else:
            self.update_status("Rien à stopper")

    def replay_recording(self):
        if self.is_recording or self.record_armed:
            self.update_status("Stoppe d'abord l'enregistrement")
            return

        if self.is_replaying:
            self.update_status("Replay déjà en cours")
            return

        if not self.events:
            self.update_status("Aucun enregistrement à rejouer")
            return

        thread = threading.Thread(target=self._replay_worker, daemon=True)
        thread.start()

    def _replay_worker(self):
        self.is_replaying = True
        self.ignore_mouse_events = True
        self.update_status("Replay en cours...")

        try:
            # On rejoue selon les délais capturés
            start = time.perf_counter()
            for event in self.events:
                target_t = event["t"]
                now = time.perf_counter() - start
                wait_time = target_t - now
                if wait_time > 0:
                    time.sleep(wait_time)

                x, y = event["x"], event["y"]
                button = event["button"]

                pyautogui.moveTo(x, y, duration=0)

                if button == "left":
                    pyautogui.click(x=x, y=y, button="left")
                elif button == "right":
                    pyautogui.click(x=x, y=y, button="right")
                elif button == "middle":
                    pyautogui.click(x=x, y=y, button="middle")

            self.update_status("Replay terminé")

        except pyautogui.FailSafeException:
            self.update_status("Replay arrêté par fail-safe (coin de l'écran)")
        except Exception as e:
            self.update_status(f"Erreur replay : {e}")
        finally:
            self.is_replaying = False
            # Petite pause pour éviter de reprendre un faux clic instantané
            time.sleep(0.2)
            self.ignore_mouse_events = False

    def on_click(self, x, y, button, pressed):
        # On n'enregistre que le clic au moment de l'appui
        if not pressed:
            return

        if self.ignore_mouse_events or self.is_replaying:
            return

        # On ne garde que les clics souris
        if button == mouse.Button.left:
            btn_name = "left"
        elif button == mouse.Button.right:
            btn_name = "right"
        elif button == mouse.Button.middle:
            btn_name = "middle"
        else:
            return

        # Si armé, le tout premier clic déclenche le vrai départ
        if self.record_armed and not self.is_recording:
            self.is_recording = True
            self.record_armed = False
            self.start_time = time.perf_counter()
            self.last_recorded_time = self.start_time
            self.update_status(f"Enregistrement lancé au 1er clic : ({x}, {y})")

        if not self.is_recording:
            return

        t = time.perf_counter() - self.start_time
        self.events.append({
            "t": t,
            "x": int(x),
            "y": int(y),
            "button": btn_name,
        })
        self.update_count()

    def on_key_press(self, key):
        try:
            if key == keyboard.Key.f8:
                self.arm_recording()
            elif key == keyboard.Key.f9:
                self.stop_recording()
            elif key == keyboard.Key.f10:
                self.replay_recording()
        except Exception as e:
            self.update_status(f"Erreur clavier : {e}")

    def on_close(self):
        try:
            if self.mouse_listener:
                self.mouse_listener.stop()
        except Exception:
            pass

        try:
            if self.keyboard_listener:
                self.keyboard_listener.stop()
        except Exception:
            pass

        self.root.destroy()


def main():
    root = tk.Tk()
    app = ClickRecorderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()