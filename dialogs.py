# dialogs.py

import tkinter as tk
from tkinter import simpledialog, messagebox

class ThresholdDialog(simpledialog.Dialog):
    """ Custom dialog to prompt for both lower and upper thresholds at once. """
    def __init__(self, parent, title, current_lower, current_upper):
        self.current_lower = current_lower
        self.current_upper = current_upper
        self.result = None
        super().__init__(parent, title)

    def validate_input(self, action, value_if_allowed):
        """
        Validates keystrokes in the Entry widget.
        action: '1' for insert, '0' for delete, '-1' for others.
        value_if_allowed: The resulting text if the action is accepted.
        """
        if action == '1':  # Action 1 means the user is inserting text
            # Reject if it's not made of digits only (no signs like + or -)
            if not value_if_allowed.isdigit():
                return False
            # Reject if the length exceeds 3 characters
            if len(value_if_allowed) > 3:
                return False
        return True

    def body(self, master):
        """ Builds the UI elements of the dialog. """
        tk.Label(master, text="Lower Threshold (Min 60%):").grid(row=0, sticky=tk.W, pady=2)
        tk.Label(master, text="Upper Threshold (Max 100%):").grid(row=1, sticky=tk.W, pady=2)

        # Register the validation callback with the Tkinter engine
        # '%d' passes the action type, '%P' passes the resulting string
        vcmd = (master.register(self.validate_input), '%d', '%P')

        # Apply the validation command to the Entry widgets
        self.entry_lower = tk.Entry(master, width=10, validate='key', validatecommand=vcmd)
        self.entry_upper = tk.Entry(master, width=10, validate='key', validatecommand=vcmd)

        self.entry_lower.insert(0, str(self.current_lower))
        self.entry_upper.insert(0, str(self.current_upper))

        self.entry_lower.grid(row=0, column=1, padx=5)
        self.entry_upper.grid(row=1, column=1, padx=5)

        return self.entry_lower # Set initial focus

    def apply(self):
        """ Parses inputs when the user clicks 'OK'. """
        try:
            # We still need to parse, but the try/except is safer in case of empty strings
            lower = int(self.entry_lower.get())
            upper = int(self.entry_upper.get())
            self.result = (lower, upper)
        except ValueError:
            # Handle the case where the user deletes everything and leaves it empty
            self.result = False 


def prompt_for_thresholds(current_lower: int, current_upper: int):
    """
    Opens the dialog to ask for thresholds.
    Returns:
    - tuple (lower, upper) if valid integers are provided.
    - False if parsing failed (e.g. empty fields).
    - None if the user clicked Cancel.
    """
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    dialog = ThresholdDialog(root, "Extended Mode Settings", current_lower, current_upper)
    result = dialog.result
    
    root.destroy()
    return result

def show_alert(title: str, message: str, is_error: bool = False):
    """ Displays a simple message box (info or error). """
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    
    if is_error:
        messagebox.showerror(title, message)
    else:
        messagebox.showinfo(title, message)
        
    root.destroy()