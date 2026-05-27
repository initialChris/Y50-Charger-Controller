import sys
import ctypes

def require_admin():
    """ 
    Checks if the script has Administrator privileges.
    If not, it relaunches the script prompting the UAC dialog and exits the current instance.
    """
    if ctypes.windll.shell32.IsUserAnAdmin():
        return True
    
    # Relaunch the script with 'runas' to trigger UAC
    script = sys.argv[0]
    params = " ".join(sys.argv[1:])
    
    # ShellExecuteW: hwnd, lpOperation, lpFile, lpParameters, lpDirectory, nShowCmd
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script}" {params}', None, 1
    )
    
    # If ShellExecuteW fails (e.g. user denies UAC), it returns a value <= 32
    if result <= 32:
        print("Error: Administrator privileges denied by the user.")
        sys.exit(1)
        
    # Exit the original non-elevated process
    sys.exit(0)