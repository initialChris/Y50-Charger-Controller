from enum import IntEnum

class Mode(IntEnum):
    """ Enumeration for User Modes. """
    FULL_CHARGE = 1
    CONSERVATION = 2
    EXTENDED = 3

class State(IntEnum):
    """ Enumeration for Internal FSM States. """
    RESET = 0
    FULL_CHARGE = 1
    CONSERVATION = 2
    EXTENDED_CONSERVATION = 3
    EXTENDED_CHARGE = 4
    NO_BATTERY = 5

class HardwareAction(IntEnum):
    """ Enumeration for the required hardware outputs. """
    NONE = 0
    ENABLE_CONSERVATION = 1
    DISABLE_CONSERVATION = 2


class BatteryFSM:
    def __init__(self):
        self.current_mode = Mode.EXTENDED
        self.current_state = State.RESET
        
        # Load default thresholds from config
        self.lower_threshold = 70
        self.upper_threshold = 80
        
        # State tracking to avoid redundant transitions
        self.last_percent = -1
        self.last_ac_status = None
        self.force = False

    def set_mode(self, new_mode: Mode):
        """ 
        Updates the target user mode if changed and resets the FSM.
        """
        if self.current_mode != new_mode:
            self.current_mode = new_mode
            self.current_state = State.RESET

    def set_thresholds(self, lower: int, upper: int) -> bool:
        """
        Validates and applies new thresholds for Extended mode.
        Rules:
        - lower must be >= 60 (hardware default limit)
        - lower must be less than or equal to upper
        - upper must be <= 100
        
        Returns True if thresholds were successfully applied, False if invalid.
        """
        if lower < 60 or upper > 100 or lower > upper:
            return False
            
        # Apply changes only if they are actually different
        if self.lower_threshold != lower or self.upper_threshold != upper:
            self.lower_threshold = lower
            self.upper_threshold = upper
            
            # If we are currently operating in Extended mode,
            # force a re-evaluation on the next tick
            # if self.current_mode == Mode.EXTENDED:
            #    self.force = True
                
        return True

    def force_extended(self, force_charge: bool) -> bool:
        """
        Forces the FSM into either the charging or conservation sub-state 
        while in Extended mode.
        If the battery is outside the valid thresholds, the FSM will naturally 
        correct itself on the next evaluation.
        
        Returns True if the force was successfully applied.
        """
        if self.current_mode == Mode.EXTENDED:
            if force_charge:
                self.current_state = State.EXTENDED_CHARGE
            else:
                self.current_state = State.EXTENDED_CONSERVATION
            #self.force = True
            return True
        return False

    def evaluate_state(self, percent: int, is_plugged: bool, hw_cons_active: bool) -> HardwareAction:
        """ 
        Pure FSM engine. Takes current telemetry and hardware state as inputs,
        updates the internal state, and returns the required hardware action.
        """
        if percent is None:
            self.current_state = State.NO_BATTERY
            return HardwareAction.NONE

        # Avoid processing if nothing has changed and force flag is off
        #if not self.force and self.current_state != State.RESET:
        #    if percent == self.last_percent and is_plugged == self.last_ac_status:
        #        return HardwareAction.NONE
        
        self.force = False
        self.last_percent = percent
        self.last_ac_status = is_plugged
        
        action = HardwareAction.NONE

        # --- STATE: RESET ---
        if self.current_state == State.RESET:
            if self.current_mode == Mode.FULL_CHARGE:
                self.current_state = State.FULL_CHARGE
                
            elif self.current_mode == Mode.CONSERVATION:
                self.current_state = State.CONSERVATION
                
            elif self.current_mode == Mode.EXTENDED:
                if percent < self.lower_threshold:
                    self.current_state = State.EXTENDED_CHARGE
                elif percent >= self.upper_threshold:
                    self.current_state = State.EXTENDED_CONSERVATION
                else:
                    # Deadband resolution based on actual hardware state
                    if hw_cons_active:
                        self.current_state = State.EXTENDED_CONSERVATION
                    else:
                        self.current_state = State.EXTENDED_CHARGE

        # --- STATE ENFORCEMENT & TRANSITIONS ---
        if self.current_state == State.FULL_CHARGE:
            if hw_cons_active:
                action = HardwareAction.DISABLE_CONSERVATION
                
        elif self.current_state == State.CONSERVATION:
            if not hw_cons_active:
                action = HardwareAction.ENABLE_CONSERVATION
                
        elif self.current_mode == Mode.EXTENDED:
            if self.current_state == State.EXTENDED_CHARGE:
                if percent >= self.upper_threshold:
                    self.current_state = State.EXTENDED_CONSERVATION
                    action = HardwareAction.ENABLE_CONSERVATION
                else:
                    # Ensure hardware matches the state
                    if hw_cons_active:
                        action = HardwareAction.DISABLE_CONSERVATION
                        
            elif self.current_state == State.EXTENDED_CONSERVATION:
                if percent <= self.lower_threshold:
                    self.current_state = State.EXTENDED_CHARGE
                    action = HardwareAction.DISABLE_CONSERVATION
                else:
                    if not hw_cons_active:
                        action = HardwareAction.ENABLE_CONSERVATION

        return action