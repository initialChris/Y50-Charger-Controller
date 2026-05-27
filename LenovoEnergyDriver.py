import ctypes
from ctypes import wintypes

DEVICE_NAME = r"\\.\EnergyDrv"
IOCTL_VPC = 2198872312
OP_ENABLE_CONSERVATION = 0x03
OP_DISABLE_CONSERVATION = 0x05
OP_QUERY = 0xFF

class LenovoEnergyDriver:
    
    def __init__(self):
        self.device_name = DEVICE_NAME

    def _open_handle(self):
        """ Opens a handle to the driver. Must be closed by the caller. """
        if not ctypes.windll.shell32.IsUserAnAdmin():
            return None
        
        handle = ctypes.windll.kernel32.CreateFileW(
            self.device_name, 0xC0000000, 0, None, 3, 0, None
        )
        if handle == -1 or handle == 0xFFFFFFFF:
            return None
        return handle

    def get_driver_status(self):
        """ 
        Retrieves the raw 4-byte status buffer from the Lenovo Energy Driver.
        Returns a ctypes byte array of size 4, or None if the call fails.
        """
        handle = self._open_handle()
        if not handle:
            return None

        in_buffer = ctypes.c_ubyte(OP_QUERY)
        out_buffer = (ctypes.c_ubyte * 4)()
        bytes_returned = wintypes.DWORD(0)

        success = ctypes.windll.kernel32.DeviceIoControl(
            handle, IOCTL_VPC, ctypes.byref(in_buffer), 1,
            ctypes.byref(out_buffer), 4, ctypes.byref(bytes_returned), None
        )
        
        ctypes.windll.kernel32.CloseHandle(handle)

        if not success:
            return None
            
        return out_buffer

    def get_charger_power(self):
        """ Decodes the charger power wattage from the hardware buffer. """
        buffer = self.get_driver_status()
        if not buffer:
            return "ERROR"
            
        b2 = buffer[2]
        if b2 == 0x02:
            return 135
        elif b2 == 0x03:
            return 100
        else:
            return 0

    def get_conservation_status(self):
        """ Returns True if conservation mode is active, False otherwise. """
        buffer = self.get_driver_status()
        if not buffer:
            return False
            
        # Bit 5 (0x20) of the first byte indicates if conservation mode is active
        return bool(buffer[0] & 0x20)

    def set_conservation(self, enable):
        """ Sends the specific hardware opcode to enable or disable conservation mode. """
        handle = self._open_handle()
        if not handle:
            return False

        opcode = OP_ENABLE_CONSERVATION if enable else OP_DISABLE_CONSERVATION
        
        success = ctypes.windll.kernel32.DeviceIoControl(
            handle, IOCTL_VPC, ctypes.byref(ctypes.c_ubyte(opcode)), 1,
            ctypes.byref((ctypes.c_ubyte * 4)()), 4, ctypes.byref(wintypes.DWORD(0)), None
        )
        
        ctypes.windll.kernel32.CloseHandle(handle)
        
        return success != 0


