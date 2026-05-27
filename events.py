# events.py

import win32api
import win32con
import win32gui

class PowerEventReceiver:
    """
    Creates a hidden ghost window to intercept native Windows power events
    without the need for aggressive polling.
    """
    def __init__(self, on_power_change_callback):
        self.callback = on_power_change_callback
        
        wc = win32gui.WNDCLASS()
        wc.lpszClassName = "LenovoBatteryEventBridge"
        wc.lpfnWndProc = self.wndproc
        wc.hInstance = win32api.GetModuleHandle(None)
        
        try:
            class_atom = win32gui.RegisterClass(wc)
        except win32gui.error:
            # Class already registered (e.g., script reloaded)
            class_atom = wc.lpszClassName

        self.hwnd = win32gui.CreateWindow(
            class_atom, "LenovoBatteryEventBridge", 
            0, 0, 0, 0, 0, 0, 0, 0, None
        )

    def wndproc(self, hwnd, msg, wparam, lparam):
        """ Windows message callback procedure. """
        if msg == win32con.WM_POWERBROADCAST:
            # PBT_APMPOWERSTATUSCHANGE: Indicates a change in the power status 
            # (e.g., AC adapter plugged or unplugged, battery dropping percentage).
            if wparam == 0x000A: 
                if self.callback:
                    self.callback()
                    
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    def process_events(self):
        """
        Dispatches incoming native messages.
        Must be called periodically in the application's main loop.
        """
        win32gui.PumpWaitingMessages()


if __name__ == "__main__":
    # Local test routine
    import time
    
    def dummy_callback():
        print(f"[{time.strftime('%H:%M:%S')}] EVENT TRIGGERED: Power status changed!")

    print("Listening for Windows power events...")
    print("Try plugging or unplugging your AC adapter.")
    
    receiver = PowerEventReceiver(dummy_callback)
    
    try:
        while True:
            receiver.process_events()
            time.sleep(0.1) # Small sleep to prevent 100% CPU usage
    except KeyboardInterrupt:
        print("\nExiting listener.")