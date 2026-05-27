# main.py

import sys
import time
import threading
import ctypes
import json
import os
import psutil
import pystray
import tkinter as tk
from tkinter import simpledialog, messagebox
from PIL import Image, ImageDraw

from LenovoEnergyDriver import LenovoEnergyDriver
from fsm import BatteryFSM, Mode, HardwareAction, State
from events import PowerEventReceiver
from dialogs import ThresholdDialog
from admin import require_admin

SETTINGS_FILE = "settings.json"

class BatteryApp:
    def __init__(self):
        self.driver = LenovoEnergyDriver()
        self.fsm = BatteryFSM()
        self.running = True
        
        # Load user settings from JSON if available
        self.load_settings()
        
        # Setup Event Receiver with the bridge callback
        self.receiver = PowerEventReceiver(self.on_power_event)
        
        # Setup Tray Icon
        self.icon = pystray.Icon(
            "LenovoBatteryManager",
            self.create_icon_image(),
            title="Initializing...",
            menu=self.build_menu()
        )

    def load_settings(self):
        """ Loads thresholds and mode from the JSON settings file. """
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    
                    if "lower_threshold" in data and "upper_threshold" in data:
                        self.fsm.set_thresholds(data["lower_threshold"], data["upper_threshold"])
                        
                    if "mode" in data:
                        # Ensures the loaded mode exists in the Mode enum
                        self.fsm.set_mode(Mode(data["mode"]))
                    
                    # if the settings file is corrupted, save the fallback values
                    self.save_settings()
            except Exception as e:
                print(f"Failed to load settings: {e}")

    def save_settings(self):
        """ Saves the current thresholds and mode to the JSON settings file. """
        data = {
            "mode": self.fsm.current_mode.value,
            "lower_threshold": self.fsm.lower_threshold,
            "upper_threshold": self.fsm.upper_threshold
        }
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def on_power_event(self):
        """ 
        Callback triggered by Windows events (AC plug/unplug, % change)
        or manual UI interactions. Fetches telemetry and ticks the FSM.
        """
        battery = psutil.sensors_battery()
        
        #if not battery:
        #    return

        percent = battery.percent if battery else None
        is_plugged = battery.power_plugged
        hw_cons_active = self.driver.get_conservation_status()

        # Step 1: Feed FSM with real data
        action = self.fsm.evaluate_state(
            percent=percent, 
            is_plugged=is_plugged, 
            hw_cons_active=hw_cons_active, 
        )

        # Step 2: Apply required hardware actions
        if action == HardwareAction.ENABLE_CONSERVATION:
            self.driver.set_conservation(True)
        elif action == HardwareAction.DISABLE_CONSERVATION:
            self.driver.set_conservation(False)

        # Step 3: Refresh UI
        self.update_tray()

    def create_icon_image(self, percent: int = 100, fill_color: str = "white", overlay: str = None):
        """ 
        Generates a dynamic battery tray icon. 
        Optimized 'Chunky' design with maximized fill area.
        """
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # 1. Main battery body extended to the right (X from 0 to 58)
        draw.rectangle([0, 10, 58, 54], outline="white", width=6)
        
        # 2. Smaller positive tip (X from 58 to 64, shorter Y span)
        draw.rectangle([58, 24, 64, 40], fill="white")
        
        # 3. Fill Area: increased max_width to 46px
        if percent > 0:
            max_width = 46
            current_width = int((percent / 100.0) * max_width)
            current_width = max(1, current_width) 
            
            draw.rectangle([6, 16, 6 + current_width, 48], fill=fill_color)
            
        # 4. Overlays shifted slightly to stay perfectly centered
        if overlay == "heart":
            coords = [(29, 50), (14, 32), (14, 20), (21, 16), (29, 24), (37, 16), (44, 20), (44, 32)]
            
            for dx, dy in [(0,2), (0,-2), (2,0), (-2,0), (2,2), (-2,-2), (2,-2), (-2,2)]:
                draw.polygon([(x+dx, y+dy) for x, y in coords], fill="#111111")
                
            draw.polygon(coords, fill="#FFFFFF")
            
        elif overlay == "lightning":
            coords = [(34, 6), (16, 34), (30, 34), (22, 58), (46, 28), (30, 28)]
            
            for dx, dy in [(0,2), (0,-2), (2,0), (-2,0), (2,2), (-2,-2), (2,-2), (-2,2)]:
                draw.polygon([(x+dx, y+dy) for x, y in coords], fill="#111111")
                
            draw.polygon(coords, fill="#FFFFFF")
            
        return image
    
    def update_tray(self):
        """ Updates the tooltip and the dynamic icon of the tray. """
        if not self.icon:
            return

        percent = self.fsm.last_percent if self.fsm.last_percent is not None else 0

        # 1. Format Mode String
        if self.fsm.current_mode == Mode.FULL_CHARGE:
            mode_str = "Full Charge"
        elif self.fsm.current_mode == Mode.CONSERVATION:
            mode_str = "Conservation (60%)"
        elif self.fsm.current_mode == Mode.EXTENDED:
            if self.fsm.lower_threshold == self.fsm.upper_threshold:
                mode_str = f"Conservation ({self.fsm.lower_threshold}%)"
            else:
                mode_str = f"Conservation ({self.fsm.lower_threshold}%-{self.fsm.upper_threshold}%)"
        else:
            mode_str = "Unknown"

        # 2. Format State String, Determine Icon Color & Overlay
        overlay = None
        
        if not self.fsm.last_ac_status:
            state_str = "Discharging"
            
            # Discharging Colors
            if percent <= 20:
                fill_color = "#FF0000"  # Red
            elif percent <= 30:
                fill_color = "#FFD700"  # Yellow
            else:
                fill_color = "#FFFFFF"  # Dark Green
                
        else:
            sub_state = "Charging"
            
            if self.fsm.current_mode == Mode.FULL_CHARGE:
                if percent >= 100:
                    sub_state = "Full Charged"
            elif self.fsm.current_mode == Mode.CONSERVATION:
                if percent >= 60:
                    sub_state = "Conservation"
            elif self.fsm.current_mode == Mode.EXTENDED:
                if self.fsm.current_state == State.EXTENDED_CONSERVATION:
                    sub_state = "Conservation"

            # Fetch hardware charger wattage
            wattage = self.driver.get_charger_power()
            if isinstance(wattage, int) and wattage > 0:
                power_str = f"({wattage}W)"
            else:
                power_str = "(AC)"

            state_str = f"{sub_state} {power_str}"
            
            # Charging / Conservation Colors & Overlays
            if sub_state == "Conservation":
                fill_color = "#FF69B4"  # Hot Pink
                overlay = "heart"
            else:
                if sub_state == "Charging":
                    overlay = "lightning"
                    
                if wattage == 135:
                    fill_color = "#0F4FFF"  # Electric Blue (Cyan)
                else:
                    fill_color = "#32CD32"  # Light Green

        # 3. Apply updates to the Tray Interface
        status_text = (
            f"Mode: {mode_str}\n"
            f"State: {state_str}\n"
            f"Battery: {percent}%"
        )
        
        self.icon.title = status_text[:127]
        self.icon.icon = self.create_icon_image(percent, fill_color, overlay)
        self.icon.menu = self.build_menu()

    def action_set_mode(self, mode: Mode):
        """ UI handler to change the operational mode. """
        self.fsm.set_mode(mode)
        self.save_settings()
        self.on_power_event()

    def _prompt_thresholds_thread(self):
        """ 
        Runs the custom Tkinter dialog. Must be in a separate thread to avoid 
        deadlocking the pystray event loop.
        """
        root = tk.Tk()
        root.withdraw() # Hide the main empty Tkinter window
        
        # Force the hidden root and its children to stay on top
        root.attributes('-topmost', True) 
        
        # Opens the custom dialog and halts execution here until closed
        dialog = ThresholdDialog(
            parent=root, 
            title="Threshold Settings", 
            current_lower=self.fsm.lower_threshold, 
            current_upper=self.fsm.upper_threshold
        )
        
        # dialog.result will be None if the user clicked Cancel or closed the window
        if dialog.result is not None:
            new_lower, new_upper = dialog.result
            
            if self.fsm.set_thresholds(new_lower, new_upper):
                self.save_settings()
                self.on_power_event()
                #messagebox.showinfo("Success", "Thresholds updated successfully.", parent=root)
            else:
                error_msg = "Invalid thresholds.\n";
                if new_lower < 60:
                    error_msg += "Lower limit must be greater than or equal to 60.\n"
                if new_upper > 100:
                    error_msg += "Upper limit must be less than or equal to 100.\n"
                if new_lower >= 60 and new_upper <= 100 and new_lower > new_upper:
                    error_msg += "Lower limit must be greater than Upper limit.\n"
                messagebox.showerror("Threshold error",   error_msg, parent=root )
                
        root.destroy()

    def action_change_thresholds(self):
        """ UI handler to trigger the thresholds input dialogs. """
        threading.Thread(target=self._prompt_thresholds_thread, daemon=True).start()

    def action_toggle_force(self):
        """ UI handler for the force conservation trigger. """
        if self.fsm.current_state == State.EXTENDED_CHARGE:
            self.fsm.force_extended(force_charge=False)
        else:
            self.fsm.force_extended(force_charge=True)
        
        self.on_power_event()

    def build_menu(self):
        """ Builds the Traybar context menu dynamically. """
        return pystray.Menu(
            # Section Header using Unicode bold characters and disabled interaction
            pystray.MenuItem(
                "Full Charge (100%)",
                lambda: self.action_set_mode(Mode.FULL_CHARGE),
                checked=lambda item: self.fsm.current_mode == Mode.FULL_CHARGE,
                radio=True
            ),
            pystray.MenuItem(
                "Standard Conservation (60%)",
                lambda: self.action_set_mode(Mode.CONSERVATION),
                checked=lambda item: self.fsm.current_mode == Mode.CONSERVATION,
                radio=True
            ),
            pystray.MenuItem(
               
                lambda item: f"Extended Conservation ({self.fsm.lower_threshold}%-{self.fsm.upper_threshold}%)" if self.fsm.lower_threshold != self.fsm.upper_threshold else f"Extended Charge ({self.fsm.lower_threshold}%)",
                lambda: self.action_set_mode(Mode.EXTENDED),
                checked=lambda item: self.fsm.current_mode == Mode.EXTENDED,
                radio=True
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda item: "Force Conservation (Pause Charging)" if self.fsm.current_state == State.EXTENDED_CHARGE else "Force Charge (Resume Charging)",
                lambda: self.action_toggle_force(),
                visible=lambda item: (
                    self.fsm.current_mode == Mode.EXTENDED and 
                    # Show only if current charge are within the thresholds
                    self.fsm.lower_threshold <= self.fsm.last_percent < self.fsm.upper_threshold
                )
            ),
            pystray.Menu.SEPARATOR,
            
            pystray.MenuItem(
                "Settings...",
                lambda: self.action_change_thresholds()
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.exit_app)
        )

    def event_loop(self):
        """ 
        Background thread for the Windows message pump. 
        Keeps listening for native WM_POWERBROADCAST events.
        """
        while self.running:
            self.receiver.process_events()
            time.sleep(0.1)

    def exit_app(self, icon, item):
        self.running = False
        icon.stop()

    def run(self):
        """ Starts the event pump thread and the blocking Tray icon UI. """
        # Initial sync on boot
        self.on_power_event()
        
        # Event receiver must run in a background thread because pystray blocks the main thread
        listener_thread = threading.Thread(target=self.event_loop, daemon=True)
        listener_thread.start()
        
        # Start blocking tray UI
        self.icon.run()


if __name__ == "__main__":
    require_admin()
    app = BatteryApp()
    app.run()