#!/usr/bin/env python3
"""
Xbox 360 Wireless Receiver - COMPLETE GUI CONTROLLER
LED + Rumble + All Buttons + Sticks + Triggers + Long Press + D-Pad Precision
For Operation Flashpoint
"""

import usb.core
import usb.util
import pygame
import sys
import time
import os
import threading
import queue
import math
import tkinter as tk
from tkinter import ttk
import pyautogui
import struct

# Set SDL environment variables BEFORE importing pygame
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

try:
    import keyboard
    from pynput.mouse import Controller as MouseController
    from pynput.mouse import Button as MouseButton
except ImportError:
    print("Installing required libraries...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "keyboard", "pynput", "pygame"])
    import keyboard
    from pynput.mouse import Controller as MouseController
    from pynput.mouse import Button as MouseButton

# ============================================
# CONFIGURATION
# ============================================

DEFAULT_SETTINGS = {
    'mouse_sensitivity': 0.056,
    'axis_deadzone': 0.08,
    'trigger_deadzone': 0.19,
    'button_debounce': 0.03,
    'invert_y': True,
    'smoothing': 0.0,
    'boost': 1.0,
    'dpad_step': 2,
    'dpad_precision': True,
    'dpad_click_mode': False,
    'mouse_margin': 5,
    'long_press_ms': 500,
    'rumble_on_fire': True,
    'rumble_intensity': 180,
    'rumble_on_zoom': True,
    'fire_rumble_mode': 'continuous',  # 'burst' or 'continuous'
    'zoom_rumble_mode': 'burst',  # 'burst' or 'continuous'
}

# ============================================
# XBOX 360 USB CONSTANTS
# ============================================

VID = 0x045e
PID = 0x0291
OUT_ENDPOINT = 0x01
IN_ENDPOINT = 0x81

# LED patterns
LED_PLAYER1 = 0x42
LED_PLAYER2 = 0x43
LED_PLAYER3 = 0x44
LED_PLAYER4 = 0x45
LED_ALL_ON = 0x46
LED_ROTATING = 0x47

# ============================================
# XBOX 360 BUTTON MAPPINGS
# ============================================

XBOX_BUTTON_MAP_6 = {
    0x01: 'DPAD_UP',
    0x02: 'DPAD_DOWN',
    0x04: 'DPAD_LEFT',
    0x08: 'DPAD_RIGHT',
    0x10: 'START',
    0x20: 'BACK',
    0x40: 'L3',
    0x80: 'R3',
}

XBOX_BUTTON_MAP_7 = {
    0x01: 'LB',
    0x02: 'RB',
    0x04: 'GUIDE',
    0x10: 'A',
    0x20: 'B',
    0x40: 'X',
    0x80: 'Y',
}

# Map to Operation Flashpoint keys
BUTTON_MAP = {
    'A': 'v',           # Action
    'B': 'r',           # Reload
    'X': 'e',           # Use
    'Y': 'space',       # Jump
    'LB': 'shift',      # Aim Down Sights
    'RB': 'k',          # Grenade
    'L3': 'up',         # Map Zoom In
    'R3': 'g',          # Gear
    'START': 'esc',     # Menu
    'BACK': 'tab',      # Map (short press)
    'GUIDE': '',        # Guide button - no mapping
}

# ============================================
# QUEUE FOR GUI UPDATES
# ============================================
gui_queue = queue.Queue(maxsize=10)

# ============================================
# XBOX 360 CONTROLLER CLASS
# ============================================
class Xbox360Controller:
    def __init__(self):
        # USB device
        self.dev = None
        self.initialized = False
        self.usb_lock = threading.Lock()  # <-- ADD THIS LINE
        
        # Add these lines for async mouse
        self.mouse_queue = queue.Queue(maxsize=100)
        self.mouse_thread_running = False
        self.mouse_worker_thread = None

        # Get screen size
        self.screen_width, self.screen_height = pyautogui.size()
        
        # Mouse control
        self.mouse = MouseController()
        self.keys_pressed = {}
        self.mouse_left_pressed = False
        self.mouse_right_pressed = False
        
        # Button states
        self.button_states = {}
        self.button_timers = {}
        self.last_buttons = []
        self.durations = {}
        
        # Trigger states
        self.lt_value = 0
        self.rt_value = 0
        self.lt_pressed = False
        self.rt_pressed = False
        
        # D-Pad states
        self.dpad_mouse_state = {'UP': False, 'DOWN': False, 'LEFT': False, 'RIGHT': False}
        self.dpad_click_count = {'UP': 0, 'DOWN': 0, 'LEFT': 0, 'RIGHT': 0}
        self.dpad_last_click_time = {'UP': 0, 'DOWN': 0, 'LEFT': 0, 'RIGHT': 0}
        self.dpad_click_cooldown = 0.15
        
        # Stick calibration
        self.lx_center = 0
        self.ly_center = 0
        self.calibrated = False
        
        # Rumble state
        self.rumble_thread = None
        self.rumble_running = False
        self.continuous_rumble_running = False
        
        # Settings
        self.settings = DEFAULT_SETTINGS.copy()
        
        # Running flag
        self.running = True
        self.thread = None
        
        print("🎮 Xbox 360 Controller initialized")

    # ============================================
    # USB METHODS - LED + RUMBLE
    # ============================================
    
    def find_usb_device(self):
        """Find the Xbox 360 wireless receiver - ONLY CALL ONCE!"""
        if self.dev is not None:
            return True
            
        self.dev = usb.core.find(idVendor=VID, idProduct=PID)
        if self.dev is None:
            print("❌ Receiver not found")
            return False
        print(f"✅ Receiver found: Bus {self.dev.bus} Address {self.dev.address}")
        return True
    
    def init_usb(self):
        """Initialize USB receiver"""
        print("\n[1] Initializing receiver...")
        
        # Always try to detach kernel driver and claim interface
        try:
            self.dev.detach_kernel_driver(0)
            print("  Detached kernel driver")
        except:
            pass
        
        try:
            self.dev.set_configuration()
            print("  Configuration set")
        except:
            pass
        
        try:
            usb.util.claim_interface(self.dev, 0)
            print("  Interface claimed")
        except:
            pass
        
        # REMOVE THIS LINE - it resets and loses config:
        # self.dev.reset()
        
        time.sleep(0.1)
        return True
    
    def send_command(self, cmd, retries=3):
        """Send command to OUT endpoint 0x01 with retries"""
        if self.dev is None:
            return False
        
        with self.usb_lock:  # Use lock to prevent concurrent writes
            for attempt in range(retries):
                try:
                    self.dev.write(OUT_ENDPOINT, cmd, timeout=1000)
                    return True
                except usb.core.USBError as e:
                    if attempt < retries - 1:
                        time.sleep(0.05)
                        continue
                    print(f"  ❌ Command failed after {retries} attempts: {e}")
                    return False
                except Exception as e:
                    print(f"  ❌ Command failed: {e}")
                    return False
        return False
    
    def set_led(self, pattern):
        """Set LED pattern with verification"""
        print(f"  Setting LED: {hex(pattern)}")
        
        # Try alternate command format (some receivers need this)
        cmd = [0x00, 0x00, 0x08, pattern, 0x00, 0x00, 0x00, 0x00, 
            0x00, 0x00, 0x00, 0x00]
        
        # Send twice to ensure it takes
        success1 = self.send_command(cmd)
        time.sleep(0.05)
        success2 = self.send_command(cmd)
        
        return success1 or success2
    
    def set_rumble(self, left, right):
        """Set rumble (0-255 each) with fallback format"""
        if self.dev is None:
            return False
        if left > 255: left = 255
        if right > 255: right = 255
        if left < 0: left = 0
        if right < 0: right = 0
        
        with self.usb_lock:
            # Try primary command format
            cmd1 = [0x00, 0x01, 0x0f, 0xc0, 0x00, left, right, 0x00,
                    0x00, 0x00, 0x00, 0x00]
            
            # Try alternate format if primary fails
            cmd2 = [0x00, 0x08, 0x00, 0x00, 0x00, left, right, 0x00,
                    0x00, 0x00, 0x00, 0x00]
            
            try:
                # Try primary
                self.dev.write(OUT_ENDPOINT, cmd1, timeout=100)
                return True
            except:
                try:
                    # Try alternate
                    self.dev.write(OUT_ENDPOINT, cmd2, timeout=100)
                    return True
                except:
                    return False
    
    # ============================================
    # RUMBLE FUNCTIONS - WITH MODE SELECTION
    # ============================================
    
    def rumble_trigger(self, trigger_type='zoom'):
        """Rumble a trigger with selected mode"""
        if trigger_type == 'zoom':
            if not self.settings.get('rumble_on_zoom', True):
                return
            mode = self.settings.get('zoom_rumble_mode', 'continuous')
            intensity = int(self.settings.get('rumble_intensity', 180) * 0.5)
            motor = 'left'  # Left motor for zoom feel
        else:  # fire
            if not self.settings.get('rumble_on_fire', True):
                return
            mode = self.settings.get('fire_rumble_mode', 'burst')
            intensity = self.settings.get('rumble_intensity', 180)
            motor = 'right'  # Right motor for fire feel
        
        # Stop any existing rumble
        self.stop_all_rumble()
        
        if mode == 'burst':
            # Burst mode - quick rumble
            self.rumble_running = True
            self.rumble_thread = threading.Thread(
                target=self._burst_rumble, 
                args=(intensity, motor), 
                daemon=True
            )
            self.rumble_thread.start()
        else:  # continuous
            # Continuous mode - rumble while held
            self.continuous_rumble_running = True
            self.rumble_thread = threading.Thread(
                target=self._continuous_rumble, 
                args=(intensity, motor), 
                daemon=True
            )
            self.rumble_thread.start()
    
    def stop_continuous_rumble(self):
        """Stop continuous rumble"""
        self.continuous_rumble_running = False
        self.set_rumble(0, 0)
    
    def stop_all_rumble(self):
        """Stop all rumble"""
        self.rumble_running = False
        self.continuous_rumble_running = False
        if self.rumble_thread and self.rumble_thread.is_alive():
            self.rumble_thread.join(timeout=0.1)
        self.set_rumble(0, 0)
    
    def _burst_rumble(self, intensity, motor):
        """Burst rumble effect: quick burst then fade"""
        left = intensity if motor == 'left' else 0
        right = intensity if motor == 'right' else 0
        
        # Quick burst
        self.set_rumble(left, right)
        time.sleep(0.05)
        
        # Fade out
        steps = 5
        for i in range(steps, 0, -1):
            if not self.rumble_running:
                break
            level = int(intensity * (i / steps))
            l = level if motor == 'left' else 0
            r = level if motor == 'right' else 0
            self.set_rumble(l, r)
            time.sleep(0.02)
        
        self.set_rumble(0, 0)
        self.rumble_running = False
    
    def _continuous_rumble(self, intensity, motor):
        """Continuous rumble loop"""
        while self.continuous_rumble_running:
            left = intensity if motor == 'left' else 0
            right = intensity if motor == 'right' else 0
            self.set_rumble(left, right)
            time.sleep(0.03)
            if self.continuous_rumble_running:
                self.set_rumble(0, 0)
                time.sleep(0.02)
        
        self.set_rumble(0, 0)
    
    def send_sync(self):
        """Send sync command to pair controller"""
        print("  Sending SYNC command...")
        cmd = [0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
               0x00, 0x00, 0x00, 0x00]
        return self.send_command(cmd)
    
    def read_data(self):
        """Read controller data from IN endpoint 0x81"""
        if self.dev is None:
            return None
        try:
            data = self.dev.read(IN_ENDPOINT, 32, timeout=100)
            return data
        except usb.core.USBTimeoutError:
            return None
        except Exception as e:
            return None

    # ============================================
    # USB DATA PARSING
    # ============================================
    
    def parse_buttons(self, b6, b7):
        """Parse buttons from bytes 6 and 7"""
        buttons = {}
        
        for mask, name in XBOX_BUTTON_MAP_6.items():
            buttons[name] = bool(b6 & mask)
        
        for mask, name in XBOX_BUTTON_MAP_7.items():
            buttons[name] = bool(b7 & mask)
        
        return buttons
    
    def update_timers(self, current_buttons):
        """Update button timers for long press detection"""
        current_time = time.time() * 1000
        all_buttons = list(XBOX_BUTTON_MAP_6.values()) + list(XBOX_BUTTON_MAP_7.values())
        
        for button in all_buttons:
            if button in current_buttons:
                if button not in self.button_timers:
                    self.button_timers[button] = current_time
            else:
                if button in self.button_timers:
                    del self.button_timers[button]
    
    def get_button_durations(self, current_buttons):
        """Get duration in ms for each pressed button"""
        current_time = time.time() * 1000
        durations = {}
        for button in current_buttons:
            if button in self.button_timers:
                durations[button] = int(current_time - self.button_timers[button])
        return durations

    # ============================================
    # CALIBRATION
    # ============================================
    
    def calibrate_sticks(self):
        """Calibrate stick centers by sampling idle position"""
        print("   Calibrating sticks... DON'T TOUCH THE STICKS!")
        
        lx_samples = []
        ly_samples = []
        
        # Take 30 samples over 1 second
        for _ in range(30):
            data = self.read_data()
            if data and len(data) >= 14 and data[1] == 0x01:
                lx = struct.unpack('<h', bytes(data[10:12]))[0]
                ly = struct.unpack('<h', bytes(data[12:14]))[0]
                lx_samples.append(lx)
                ly_samples.append(ly)
            time.sleep(0.02)
        
        if lx_samples and ly_samples:
            self.lx_center = int(sum(lx_samples) / len(lx_samples))
            self.ly_center = int(sum(ly_samples) / len(ly_samples))
            self.calibrated = True
            print(f"   Center: LX={self.lx_center}, LY={self.ly_center}")
            return True
        else:
            self.lx_center = 0
            self.ly_center = 0
            self.calibrated = True
            print("   Using default centers (0, 0)")
            return False

    # ============================================
    # MOUSE CENTERING
    # ============================================
    
    def center_mouse(self):
        """Center the mouse on screen"""
        center_x = self.screen_width // 2
        center_y = self.screen_height // 2
        self.mouse.position = (center_x, center_y)
        
        # Flash rumble to indicate centering
        def rumble_feedback():
            self.set_rumble(80, 80)
            time.sleep(0.1)
            self.set_rumble(0, 0)
        
        threading.Thread(target=rumble_feedback, daemon=True).start()
        
        # Send status to GUI
        try:
            gui_queue.put_nowait({
                'center_mouse': True,
                'center_x': center_x,
                'center_y': center_y
            })
        except queue.Full:
            pass
        
        print(f"🎯 Mouse centered at ({center_x}, {center_y})")

    # ============================================
    # INPUT HANDLING
    # ============================================
    def _mouse_worker(self):
        """Background thread for processing mouse movements"""
        while self.mouse_thread_running:
            try:
                # Process all queued movements at once
                dx_total = 0
                dy_total = 0
                count = 0
                
                while not self.mouse_queue.empty() and count < 10:
                    try:
                        dx, dy = self.mouse_queue.get_nowait()
                        dx_total += dx
                        dy_total += dy
                        count += 1
                    except queue.Empty:
                        break
                
                if count > 0:
                    # Apply combined movement
                    self.safe_mouse_move(dx_total, dy_total)
                
                # Small sleep to prevent CPU spam
                time.sleep(0.001)
            except Exception as e:
                pass

    def set_key_state(self, key, pressed):
        """Set keyboard or mouse state"""
        if key is None or key == '':
            return
        
        if key == 'MOUSE_LEFT':
            if pressed and not self.mouse_left_pressed:
                self.mouse.press(MouseButton.left)
                self.mouse_left_pressed = True
            elif not pressed and self.mouse_left_pressed:
                self.mouse.release(MouseButton.left)
                self.mouse_left_pressed = False
            return
        
        elif key == 'MOUSE_RIGHT':
            if pressed and not self.mouse_right_pressed:
                self.mouse.press(MouseButton.right)
                self.mouse_right_pressed = True
            elif not pressed and self.mouse_right_pressed:
                self.mouse.release(MouseButton.right)
                self.mouse_right_pressed = False
            return
        
        try:
            if pressed:
                if not self.keys_pressed.get(key, False):
                    keyboard.press(key)
                    self.keys_pressed[key] = True
            else:
                if self.keys_pressed.get(key, False):
                    keyboard.release(key)
                    self.keys_pressed[key] = False
        except Exception as e:
            pass
    
    def safe_mouse_move(self, dx, dy):
        """Move mouse but keep it within screen bounds"""
        current_x, current_y = self.mouse.position
        new_x = current_x + dx
        new_y = current_y + dy
        
        margin = self.settings.get('mouse_margin', 5)
        new_x = max(margin, min(new_x, self.screen_width - margin))
        new_y = max(margin, min(new_y, self.screen_height - margin))
        
        if new_x != current_x or new_y != current_y:
            self.mouse.position = (new_x, new_y)
            return True
        return False
    
    def handle_dpad_click(self, direction, pressed):
        """Handle D-pad as click-to-move for precision aiming"""
        if not self.settings.get('dpad_precision', True):
            return
        
        self.dpad_mouse_state[direction] = pressed
        
        if not pressed:
            return
        
        click_mode = self.settings.get('dpad_click_mode', False)
        
        if click_mode:
            current_time = time.time()
            
            if current_time - self.dpad_last_click_time.get(direction, 0) < self.dpad_click_cooldown:
                return
            
            step = self.settings.get('dpad_step', 5)
            
            if direction == 'UP':
                try:
                    self.mouse_queue.put_nowait((0, -step))
                except queue.Full:
                    pass
                self.dpad_click_count['UP'] += 1
            elif direction == 'DOWN':
                try:
                    self.mouse_queue.put_nowait((0, step))
                except queue.Full:
                    pass
                self.dpad_click_count['DOWN'] += 1
            elif direction == 'LEFT':
                try:
                    self.mouse_queue.put_nowait((-step, 0))
                except queue.Full:
                    pass
                self.dpad_click_count['LEFT'] += 1
            elif direction == 'RIGHT':
                try:
                    self.mouse_queue.put_nowait((step, 0))
                except queue.Full:
                    pass
                self.dpad_click_count['RIGHT'] += 1
            
            self.dpad_last_click_time[direction] = current_time
            
            def release_dpad():
                self.dpad_mouse_state[direction] = False
            threading.Timer(0.05, release_dpad).start()

    def handle_dpad_continuous(self):
        """Handle continuous D-pad movement (for hold mode)"""
        click_mode = self.settings.get('dpad_click_mode', False)
        if click_mode:
            return
        
        if not self.settings.get('dpad_precision', True):
            return
        
        step = self.settings.get('dpad_step', 5)
        
        if self.dpad_mouse_state['UP']:
            try:
                self.mouse_queue.put_nowait((0, -step))
            except queue.Full:
                pass
        if self.dpad_mouse_state['DOWN']:
            try:
                self.mouse_queue.put_nowait((0, step))
            except queue.Full:
                pass
        if self.dpad_mouse_state['LEFT']:
            try:
                self.mouse_queue.put_nowait((-step, 0))
            except queue.Full:
                pass
        if self.dpad_mouse_state['RIGHT']:
            try:
                self.mouse_queue.put_nowait((step, 0))
            except queue.Full:
                pass
    # ============================================
    # MAIN CONTROLLER LOOP
    # ============================================
    
    def controller_loop(self):
        """Main controller loop - runs in separate thread"""
        if not self.find_usb_device():
            print("❌ No Xbox 360 receiver found!")
            return
        
        if not self.init_usb():
            print("❌ USB init failed!")
            return
        
        time.sleep(0.2)
        
        # Set LED to Player 1
        print("\n[2] Setting LED...")
        self.set_led(LED_PLAYER1)
        time.sleep(0.5)
        
        # Test rumble
        print("\n[2.5] Rumble test...")
        print("  Vibrating for 1 second...")
        self.set_rumble(255, 255)
        time.sleep(1)
        self.set_rumble(0, 0)
        
        # Send sync
        print("\n[3] Sending SYNC command...")
        self.send_sync()
        
        print("\n  Press SYNC on RECEIVER, then SYNC on CONTROLLER if not connected")
        print("  Or just press the Xbox Guide button")
        time.sleep(2)
        
        # ADD THIS: Re-initialize after sync for reliable rumble
        print("\n[3.5] Re-initializing for rumble...")
        try:
            usb.util.claim_interface(self.dev, 0)
            self.set_led(LED_PLAYER1)  # Re-set LED
            time.sleep(0.1)
            # Test rumble again to confirm
            self.set_rumble(100, 100)
            time.sleep(0.2)
            self.set_rumble(0, 0)
            print("  ✅ Rumble confirmed working")
        except Exception as e:
            print(f"  ⚠️ Re-init issue: {e}")
        
        # Calibrate sticks
        self.calibrate_sticks()
        
        print("\n🎮 Xbox 360 Controller active with D-Pad precision aiming")
        print("   D-Pad → Click to move mouse incrementally")
        print("   Right Stick → Normal mouse look")
        print("   Left Stick → WASD movement")
        print("   LT → Zoom (with rumble!) | RT → Shoot (with rumble!)")
        print("   BACK (short) → Map | BACK (hold) → Center mouse 🎯")
        
        last_status_update = time.time()
        last_continuous_dpad = time.time()
        
        # Track trigger states to prevent spamming
        last_lt_pressed = False
        last_rt_pressed = False
        
        # Track key states for left stick
        last_w = False
        last_s = False
        last_a = False
        last_d = False
        
        # Track BACK button for mouse centering
        back_pressed = False
        back_press_time = 0
        back_held = False
        
        # Track RT press for rumble
        rt_was_pressed = False
        lt_was_pressed = False
        
        # Initialize lx, ly, rx, ry to 0
        lx = 0
        ly = 0
        rx = 0
        ry = 0
        
        while self.running:
            # Read USB data
            data = self.read_data()
            
            if data and len(data) >= 18 and data[1] == 0x01:
                # BUTTONS - bytes 6 and 7
                b6 = data[6]
                b7 = data[7]
                buttons = self.parse_buttons(b6, b7)
                current_buttons = [name for name, pressed in buttons.items() if pressed and name != 'GUIDE']
                
                # Update timers
                self.update_timers(current_buttons)
                self.durations = self.get_button_durations(current_buttons)
                self.button_states = buttons
                
                # Handle D-pad
                dpad_buttons = ['DPAD_UP', 'DPAD_DOWN', 'DPAD_LEFT', 'DPAD_RIGHT']
                for btn in dpad_buttons:
                    if btn in buttons:
                        direction = btn.split('_')[1]
                        self.handle_dpad_click(direction, buttons[btn])
                
                # Handle normal buttons (including BACK with special handling)
                for btn_name, pressed in buttons.items():
                    if btn_name in dpad_buttons or btn_name == 'GUIDE':
                        continue
                    
                    if btn_name == 'BACK':
                        # BACK button - short press = tab (map), long press = center mouse
                        if pressed and not back_pressed:
                            back_pressed = True
                            back_press_time = time.time()
                            back_held = False
                        elif not pressed and back_pressed:
                            # Released - check if it was a short press
                            press_duration = time.time() - back_press_time
                            if press_duration < 0.5 and not back_held:
                                # Short press - send TAB key (map) using BUTTON_MAP
                                map_key = BUTTON_MAP.get('BACK', 'tab')
                                self.set_key_state(map_key, True)
                                threading.Timer(0.05, lambda: self.set_key_state(map_key, False)).start()
                            back_pressed = False
                            back_held = False
                        
                        # Check for long press (500ms)
                        if back_pressed and not back_held:
                            if time.time() - back_press_time > 0.5:
                                back_held = True
                                self.center_mouse()
                    elif btn_name in BUTTON_MAP:
                        self.set_key_state(BUTTON_MAP[btn_name], pressed)
                
                # ============================================
                # TRIGGERS - LT = byte 8, RT = byte 9
                # ============================================
                lt = data[8]  # 0-255
                rt = data[9]  # 0-255
                
                # Store values for GUI
                self.lt_value = lt
                self.rt_value = rt
                
                # Trigger deadzone
                trigger_deadzone = self.settings['trigger_deadzone'] * 255
                lt_pressed = lt > trigger_deadzone
                rt_pressed = rt > trigger_deadzone
                
                # ============================================
                # RUMBLE WITH MODE SELECTION
                # ============================================
                
                # RUMBLE ON ZOOM (LT)
                if lt_pressed and not lt_was_pressed:
                    # Start LT rumble
                    mode = self.settings.get('zoom_rumble_mode', 'continuous')
                    if mode == 'continuous':
                        self.rumble_trigger('zoom')
                    else:  # burst
                        self.rumble_trigger('zoom')
                elif not lt_pressed and lt_was_pressed:
                    # Stop LT continuous rumble if it was running
                    if self.settings.get('zoom_rumble_mode', 'continuous') == 'continuous':
                        self.stop_continuous_rumble()
                lt_was_pressed = lt_pressed
                
                # RUMBLE ON FIRE (RT)
                if rt_pressed and not rt_was_pressed:
                    # Start RT rumble
                    mode = self.settings.get('fire_rumble_mode', 'burst')
                    if mode == 'continuous':
                        self.rumble_trigger('fire')
                    else:  # burst
                        self.rumble_trigger('fire')
                elif not rt_pressed and rt_was_pressed:
                    # Stop RT continuous rumble if it was running
                    if self.settings.get('fire_rumble_mode', 'burst') == 'continuous':
                        self.stop_continuous_rumble()
                rt_was_pressed = rt_pressed
                
                # Only send events when state changes (prevents spamming)
                if lt_pressed != last_lt_pressed:
                    last_lt_pressed = lt_pressed
                    self.lt_pressed = lt_pressed
                    self.set_key_state('q', lt_pressed)  # LT = Zoom
                
                if rt_pressed != last_rt_pressed:
                    last_rt_pressed = rt_pressed
                    self.rt_pressed = rt_pressed
                    self.set_key_state('MOUSE_LEFT', rt_pressed)  # RT = Shoot
                
                # ============================================
                # LEFT STICK - WITH CALIBRATION
                # ============================================
                if len(data) >= 14:
                    lx = struct.unpack('<h', bytes(data[10:12]))[0] - self.lx_center
                    ly = struct.unpack('<h', bytes(data[12:14]))[0] - self.ly_center
                    
                    deadzone = self.settings['axis_deadzone'] * 32768
                    invert_y = self.settings['invert_y']
                    
                    # Calculate magnitude for better deadzone
                    magnitude = math.sqrt(lx*lx + ly*ly)
                    
                    # Only process if magnitude > deadzone
                    if magnitude > deadzone:
                        # Normalize for circular deadzone
                        if magnitude > 0:
                            norm_lx = lx / magnitude
                            norm_ly = ly / magnitude
                            scaled_magnitude = (magnitude - deadzone) / (32768 - deadzone)
                            
                            # Apply scaling to maintain circular shape
                            lx = int(norm_lx * scaled_magnitude * 32768)
                            ly = int(norm_ly * scaled_magnitude * 32768)
                        else:
                            lx = 0
                            ly = 0
                    else:
                        lx = 0
                        ly = 0
                    
                    # LEFT STICK Y AXIS:
                    # Xbox 360: UP = negative value, DOWN = positive value
                    # For WASD: UP = 'w' (forward), DOWN = 's' (backward)
                    w_pressed = False
                    s_pressed = False
                    a_pressed = False
                    d_pressed = False
                    
                    if not invert_y:
                        # Normal: Up = w, Down = s
                        w_pressed = ly < -deadzone
                        s_pressed = ly > deadzone
                    else:
                        # Inverted: Up = s, Down = w
                        w_pressed = ly > deadzone
                        s_pressed = ly < -deadzone
                    
                    a_pressed = lx < -deadzone
                    d_pressed = lx > deadzone
                    
                    # Only send key events when state changes (prevents spamming)
                    if w_pressed != last_w:
                        last_w = w_pressed
                        self.set_key_state('w', w_pressed)
                    if s_pressed != last_s:
                        last_s = s_pressed
                        self.set_key_state('s', s_pressed)
                    if a_pressed != last_a:
                        last_a = a_pressed
                        self.set_key_state('a', a_pressed)
                    if d_pressed != last_d:
                        last_d = d_pressed
                        self.set_key_state('d', d_pressed)
                
                # ============================================
                # RIGHT STICK - FIXED Y AXIS (UP = UP, DOWN = DOWN)
                # ============================================
                if len(data) >= 18:
                    rx = struct.unpack('<h', bytes(data[14:16]))[0]
                    ry = struct.unpack('<h', bytes(data[16:18]))[0]
                    
                    deadzone = self.settings['axis_deadzone'] * 32768
                    sensitivity = self.settings['mouse_sensitivity']
                    invert_y = self.settings['invert_y']
                    boost = self.settings['boost']
                    
                    magnitude = math.sqrt(rx*rx + ry*ry)
                    if magnitude > deadzone:
                        # Normalize for circular deadzone
                        norm_rx = rx / magnitude
                        norm_ry = ry / magnitude
                        
                        scaled_magnitude = (magnitude - deadzone) / (32768 - deadzone)
                        
                        move_x = int(norm_rx * scaled_magnitude * sensitivity * boost * 200)
                        move_y = int(norm_ry * scaled_magnitude * sensitivity * boost * 200)
                        
                        # RIGHT STICK Y AXIS FIXED:
                        if invert_y:
                            move_y = -move_y
                        
                if abs(move_x) > 0.5 or abs(move_y) > 0.5:
                    # Queue the movement for async processing
                    try:
                        self.mouse_queue.put_nowait((move_x, move_y))
                    except queue.Full:
                        pass  # Skip if queue is full to prevent lag
                                
                # Send status to GUI
                current_time = time.time()
                if current_time - last_status_update > 0.05:
                    try:
                        gui_queue.put_nowait({
                            'lt': self.lt_value,
                            'rt': self.rt_value,
                            'lt_pressed': self.lt_pressed,
                            'rt_pressed': self.rt_pressed,
                            'lx': lx,
                            'ly': ly,
                            'rx': rx,
                            'ry': ry,
                            'dpad': self.dpad_mouse_state.copy(),
                            'dpad_clicks': self.dpad_click_count.copy(),
                            'buttons': self.button_states.copy(),
                            'durations': self.durations.copy(),
                            'back_held': back_held,
                            'rumble_on_fire': self.settings.get('rumble_on_fire', True),
                            'rumble_on_zoom': self.settings.get('rumble_on_zoom', True),
                            'fire_rumble_mode': self.settings.get('fire_rumble_mode', 'burst'),
                            'zoom_rumble_mode': self.settings.get('zoom_rumble_mode', 'continuous')
                        })
                    except queue.Full:
                        pass
                    last_status_update = current_time
            
            # Handle continuous D-pad
            click_mode = self.settings.get('dpad_click_mode', False)
            if not click_mode:
                current_time = time.time()
                if current_time - last_continuous_dpad > 0.02:
                    self.handle_dpad_continuous()
                    last_continuous_dpad = current_time
            
            time.sleep(0.005)  # 200Hz loop
    
    def start(self):
        """Start the controller in a separate thread"""
        self.running = True
        self.mouse_thread_running = True
        
        # Start mouse worker thread
        self.mouse_worker_thread = threading.Thread(target=self._mouse_worker, daemon=True)
        self.mouse_worker_thread.start()
        
        # Start controller thread
        self.thread = threading.Thread(target=self.controller_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop the controller and clean up"""
        self.running = False
        self.mouse_thread_running = False
        
        # Clear mouse queue
        while not self.mouse_queue.empty():
            try:
                self.mouse_queue.get_nowait()
            except:
                break
        
        # Stop rumble
        self.stop_all_rumble()
        
        # Release all keys
        for key in list(self.keys_pressed.keys()):
            if self.keys_pressed.get(key, False):
                try:
                    keyboard.release(key)
                except:
                    pass
        self.keys_pressed.clear()
        
        # Release mouse buttons
        if self.mouse_left_pressed:
            try:
                self.mouse.release(MouseButton.left)
                self.mouse_left_pressed = False
            except:
                pass
        if self.mouse_right_pressed:
            try:
                self.mouse.release(MouseButton.right)
                self.mouse_right_pressed = False
            except:
                pass
        
        # Turn off rumble
        try:
            self.set_rumble(0, 0)
        except:
            pass
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        
        if self.mouse_worker_thread and self.mouse_worker_thread.is_alive():
            self.mouse_worker_thread.join(timeout=0.5)
        
        # Release mouse buttons
        if self.mouse_left_pressed:
            try:
                self.mouse.release(MouseButton.left)
                self.mouse_left_pressed = False
            except:
                pass
        if self.mouse_right_pressed:
            try:
                self.mouse.release(MouseButton.right)
                self.mouse_right_pressed = False
            except:
                pass
        
        # Turn off rumble
        try:
            self.set_rumble(0, 0)
        except:
            pass
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
    
    def update_settings(self, **kwargs):
        """Update controller settings"""
        for key, value in kwargs.items():
            if key in self.settings:
                self.settings[key] = value

# ============================================
# GUI TUNER
# ============================================
class Xbox360TunerGUI:
    def __init__(self, controller):
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("🎮 Xbox 360 Tuner - D-Pad Click Aiming")
        self.root.geometry("480x1000")
        self.root.attributes('-topmost', True)
        
        self.controller_connected = False
        self.status_text = "🔴 Disconnected"
        
        self.create_widgets()
        self.update_values()
        
    def create_widgets(self):
        # Title
        title = tk.Label(self.root, text="XBOX 360 WIRELESS TUNER", 
                         font=("Arial", 14, "bold"))
        title.pack(pady=5)
        
        subtitle = tk.Label(self.root, text="D-Pad → Click for Precision Mouse Movement", 
                           font=("Arial", 10), fg="blue")
        subtitle.pack(pady=2)
        
        # Control buttons at top
        control_frame = ttk.Frame(self.root)
        control_frame.pack(pady=5)
        
        self.start_btn = ttk.Button(control_frame, text="▶ Start Controller", command=self.start_controller)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = ttk.Button(control_frame, text="⏹ Stop Controller", command=self.stop_controller, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_frame, text="🔄 Connect", command=self.check_controller).pack(side=tk.LEFT, padx=5)
        
        self.status_label = tk.Label(self.root, text=self.status_text, font=("Arial", 10))
        self.status_label.pack(pady=2)
        
        # Scrollable frame
        canvas_frame = ttk.Frame(self.root)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        def configure_scroll_region(event):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        def configure_canvas_width(event):
            self.canvas.itemconfig(self.canvas_window, width=event.width)
        
        self.scrollable_frame.bind("<Configure>", configure_scroll_region)
        self.canvas.bind("<Configure>", configure_canvas_width)
        
        def on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        main_frame = self.scrollable_frame
        main_frame.configure(padding="10")
        
        # Settings sliders
        row = 0
        self.add_slider(main_frame, row, "Mouse Sensitivity", "mouse_sensitivity", 0.02, 0.5, "%.3f")
        row += 2
        self.add_slider(main_frame, row, "Axis Deadzone", "axis_deadzone", 0.05, 0.5, "%.2f")
        row += 2
        self.add_slider(main_frame, row, "Trigger Deadzone", "trigger_deadzone", 0.1, 0.5, "%.2f")
        row += 2
        self.add_slider(main_frame, row, "D-Pad Step Size (pixels)", "dpad_step", 1, 30, "%dpx")
        row += 2
        self.add_slider(main_frame, row, "Boost", "boost", 0.5, 3.0, "%.1fx")
        row += 2
        self.add_slider(main_frame, row, "Long Press (ms)", "long_press_ms", 100, 1000, "%dms")
        row += 2
        
        # Rumble Settings
        ttk.Label(main_frame, text="Rumble Settings", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=(10,0))
        row += 1
        
        # Rumble enable checkboxes
        rumble_frame = ttk.Frame(main_frame)
        rumble_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0,5))
        
        self.rumble_fire_var = tk.BooleanVar(value=self.controller.settings.get('rumble_on_fire', True))
        rumble_fire_check = ttk.Checkbutton(rumble_frame, text="Rumble on Fire (RT)", 
                                             variable=self.rumble_fire_var, command=self.on_rumble_fire_change)
        rumble_fire_check.pack(anchor=tk.W)
        
        self.rumble_zoom_var = tk.BooleanVar(value=self.controller.settings.get('rumble_on_zoom', True))
        rumble_zoom_check = ttk.Checkbutton(rumble_frame, text="Rumble on Zoom (LT)", 
                                             variable=self.rumble_zoom_var, command=self.on_rumble_zoom_change)
        rumble_zoom_check.pack(anchor=tk.W)
        row += 1
        
        # Rumble intensity slider
        ttk.Label(main_frame, text="Rumble Intensity", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W, pady=(5,0))
        self.rumble_intensity_var = tk.DoubleVar(value=self.controller.settings.get('rumble_intensity', 180))
        rumble_slider = ttk.Scale(main_frame, from_=20, to=255, orient=tk.HORIZONTAL,
                                   variable=self.rumble_intensity_var, command=self.on_rumble_intensity_change)
        rumble_slider.grid(row=row+1, column=0, sticky=tk.EW, pady=(0,5))
        self.rumble_intensity_label = ttk.Label(main_frame, text=str(int(self.controller.settings.get('rumble_intensity', 180))))
        self.rumble_intensity_label.grid(row=row+1, column=1, padx=(10,0))
        row += 2
        
        # Rumble Mode Selection
        ttk.Label(main_frame, text="Rumble Mode", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=(10,0))
        row += 1
        
        # Fire Rumble Mode
        ttk.Label(main_frame, text="Fire (RT):", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W)
        self.fire_mode_var = tk.StringVar(value=self.controller.settings.get('fire_rumble_mode', 'burst'))
        fire_mode_frame = ttk.Frame(main_frame)
        fire_mode_frame.grid(row=row, column=1, sticky=tk.W)
        ttk.Radiobutton(fire_mode_frame, text="Burst", variable=self.fire_mode_var, 
                        value='burst', command=self.on_fire_mode_change).pack(side=tk.LEFT)
        ttk.Radiobutton(fire_mode_frame, text="Continuous", variable=self.fire_mode_var, 
                        value='continuous', command=self.on_fire_mode_change).pack(side=tk.LEFT)
        row += 1
        
        # Zoom Rumble Mode
        ttk.Label(main_frame, text="Zoom (LT):", font=("Arial", 10)).grid(row=row, column=0, sticky=tk.W)
        self.zoom_mode_var = tk.StringVar(value=self.controller.settings.get('zoom_rumble_mode', 'continuous'))
        zoom_mode_frame = ttk.Frame(main_frame)
        zoom_mode_frame.grid(row=row, column=1, sticky=tk.W)
        ttk.Radiobutton(zoom_mode_frame, text="Burst", variable=self.zoom_mode_var, 
                        value='burst', command=self.on_zoom_mode_change).pack(side=tk.LEFT)
        ttk.Radiobutton(zoom_mode_frame, text="Continuous", variable=self.zoom_mode_var, 
                        value='continuous', command=self.on_zoom_mode_change).pack(side=tk.LEFT)
        row += 1
        
        # D-Pad Mode
        ttk.Label(main_frame, text="D-Pad Mode", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=(10,0))
        row += 1
        self.dpad_click_mode_var = tk.BooleanVar(value=self.controller.settings.get('dpad_click_mode', False))
        click_mode_frame = ttk.Frame(main_frame)
        click_mode_frame.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0,5))
        
        hold_radio = ttk.Radiobutton(click_mode_frame, text="Hold Mode (continuous while held)", 
                                      variable=self.dpad_click_mode_var, value=False,
                                      command=self.on_dpad_click_mode_change)
        hold_radio.pack(anchor=tk.W)
        
        click_radio = ttk.Radiobutton(click_mode_frame, text="Click Mode (1 click = 1 step)", 
                                       variable=self.dpad_click_mode_var, value=True,
                                       command=self.on_dpad_click_mode_change)
        click_radio.pack(anchor=tk.W)
        row += 1
        
        # Checkboxes
        ttk.Label(main_frame, text="Options", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=(10,0))
        row += 1
        
        self.dpad_precision_var = tk.BooleanVar(value=self.controller.settings.get('dpad_precision', True))
        dpad_check = ttk.Checkbutton(main_frame, text="Enable D-Pad Aiming", 
                                      variable=self.dpad_precision_var, command=self.on_dpad_precision_change)
        dpad_check.grid(row=row, column=0, sticky=tk.W, pady=(0,5))
        row += 1
        
        self.invert_var = tk.BooleanVar(value=self.controller.settings['invert_y'])
        invert_check = ttk.Checkbutton(main_frame, text="Invert Y (Sticks)", 
                                        variable=self.invert_var, command=self.on_invert_change)
        invert_check.grid(row=row, column=0, sticky=tk.W, pady=(0,5))
        row += 1
        
        # Mouse centering info
        center_frame = ttk.Frame(main_frame)
        center_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=(5,0))
        ttk.Label(center_frame, text="🎯 BACK: Short=Map | Hold=Center Mouse", 
                  font=("Arial", 10, "bold"), foreground="green").pack()
        row += 1
        
        # Live Values
        self.value_frame = ttk.LabelFrame(main_frame, text="Live Values", padding="5")
        self.value_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=(10,0))
        
        self.lt_label = ttk.Label(self.value_frame, text="LT: 0 [IDLE]")
        self.lt_label.grid(row=0, column=0, sticky=tk.W)
        
        self.rt_label = ttk.Label(self.value_frame, text="RT: 0 [IDLE]")
        self.rt_label.grid(row=1, column=0, sticky=tk.W)
        
        self.stick_label = ttk.Label(self.value_frame, text="LS: (0, 0)  RS: (0, 0)")
        self.stick_label.grid(row=2, column=0, sticky=tk.W)
        
        self.dpad_label = ttk.Label(self.value_frame, text="D-Pad: None")
        self.dpad_label.grid(row=3, column=0, sticky=tk.W)
        
        self.dpad_clicks_label = ttk.Label(self.value_frame, text="Clicks: ↑0 ↓0 ←0 →0")
        self.dpad_clicks_label.grid(row=4, column=0, sticky=tk.W)
        
        self.button_label = ttk.Label(self.value_frame, text="Buttons: None")
        self.button_label.grid(row=5, column=0, sticky=tk.W)
        
        self.center_status = ttk.Label(self.value_frame, text="🎯 Mouse: Not Centered", foreground="gray")
        self.center_status.grid(row=6, column=0, sticky=tk.W)
        
        self.rumble_status = ttk.Label(self.value_frame, text="💥 Rumble: Off", foreground="gray")
        self.rumble_status.grid(row=7, column=0, sticky=tk.W)
        
        self.mode_status = ttk.Label(self.value_frame, text="Mode: Fire(Burst) Zoom(Cont)", foreground="gray")
        self.mode_status.grid(row=8, column=0, sticky=tk.W)
        row += 1
        
        # Presets
        ttk.Label(main_frame, text="Presets", font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=(10,0))
        row += 1
        preset_frame = ttk.Frame(main_frame)
        preset_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=(0,5))
        
        ttk.Button(preset_frame, text="Sniper", command=self.preset_sniper).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Balanced", command=self.preset_balanced).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Action", command=self.preset_action).pack(side=tk.LEFT, padx=2)
        ttk.Button(preset_frame, text="Precision", command=self.preset_precision).pack(side=tk.LEFT, padx=2)
        
        main_frame.columnconfigure(0, weight=1)
        
        # Check controller status
        self.root.after(500, self.check_controller)
    
    def add_slider(self, parent, row, label, key, from_, to, format_str):
        """Add a slider with label"""
        ttk.Label(parent, text=label, font=("Arial", 10, "bold")).grid(row=row, column=0, sticky=tk.W, pady=(10,0))
        
        var = tk.DoubleVar(value=self.controller.settings[key])
        slider = ttk.Scale(parent, from_=from_, to=to, orient=tk.HORIZONTAL,
                          variable=var, command=lambda v: self.on_slider_change(key, var, format_str))
        slider.grid(row=row+1, column=0, sticky=tk.EW, pady=(0,5))
        
        label_widget = ttk.Label(parent, text=format_str % self.controller.settings[key])
        label_widget.grid(row=row+1, column=1, padx=(10,0))
        
        # Store references
        setattr(self, f"{key}_var", var)
        setattr(self, f"{key}_label", label_widget)
        
        return var, label_widget
    
    def on_slider_change(self, key, var, format_str):
        """Handle slider change"""
        value = var.get()
        if key == 'dpad_step':
            value = int(value)
        self.controller.update_settings(**{key: value})
        label = getattr(self, f"{key}_label")
        if key == 'dpad_step':
            label.config(text=f"{int(value)}px")
        else:
            label.config(text=format_str % value)
    
    def on_rumble_intensity_change(self, val):
        """Handle rumble intensity change"""
        value = int(self.rumble_intensity_var.get())
        self.controller.update_settings(rumble_intensity=value)
        self.rumble_intensity_label.config(text=str(value))
    
    def on_rumble_fire_change(self):
        """Handle rumble on fire change"""
        enabled = self.rumble_fire_var.get()
        self.controller.update_settings(rumble_on_fire=enabled)
    
    def on_rumble_zoom_change(self):
        """Handle rumble on zoom change"""
        enabled = self.rumble_zoom_var.get()
        self.controller.update_settings(rumble_on_zoom=enabled)
    
    def on_fire_mode_change(self):
        """Handle fire rumble mode change"""
        mode = self.fire_mode_var.get()
        self.controller.update_settings(fire_rumble_mode=mode)
        self.update_mode_status()
    
    def on_zoom_mode_change(self):
        """Handle zoom rumble mode change"""
        mode = self.zoom_mode_var.get()
        self.controller.update_settings(zoom_rumble_mode=mode)
        self.update_mode_status()
    
    def update_mode_status(self):
        """Update the mode status label"""
        fire_mode = self.fire_mode_var.get()
        zoom_mode = self.zoom_mode_var.get()
        self.mode_status.config(text=f"Mode: Fire({fire_mode}) Zoom({zoom_mode})")
    
    def on_dpad_click_mode_change(self):
        self.controller.update_settings(dpad_click_mode=self.dpad_click_mode_var.get())
    
    def on_dpad_precision_change(self):
        self.controller.update_settings(dpad_precision=self.dpad_precision_var.get())
    
    def on_invert_change(self):
        self.controller.update_settings(invert_y=self.invert_var.get())
    
    def check_controller(self):
        """Check if controller is connected - DON'T open device, just check"""
        dev = usb.core.find(idVendor=VID, idProduct=PID)
        if dev is not None:
            self.controller_connected = True
            self.status_text = f"✅ Controller Ready"
            self.status_label.config(text=self.status_text, fg="green")
        else:
            self.controller_connected = False
            self.status_text = "🔴 No controller found - Click Connect"
            self.status_label.config(text=self.status_text, fg="red")
        
        if not self.controller_connected:
            self.root.after(2000, self.check_controller)
    
    def start_controller(self):
        """Start the controller - this opens the USB device"""
        self.controller.start()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_text = "🟢 Controller Running"
        self.status_label.config(text=self.status_text, fg="green")
    
    def stop_controller(self):
        self.controller.stop()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_text = "⏸ Controller Stopped"
        self.status_label.config(text=self.status_text, fg="orange")
    
    def update_values(self):
        """Update live values from queue"""
        try:
            while not gui_queue.empty():
                data = gui_queue.get_nowait()
                
                # Check for mouse centering event
                if data.get('center_mouse', False):
                    self.center_status.config(
                        text=f"🎯 Mouse Centered at ({data.get('center_x', 0)}, {data.get('center_y', 0)})",
                        foreground="green"
                    )
                    def reset_center_status():
                        self.center_status.config(text="🎯 Mouse: Centered!", foreground="green")
                    threading.Timer(2.0, reset_center_status).start()
                
                lt_val = data.get('lt', 0)
                rt_val = data.get('rt', 0)
                lt_pressed = data.get('lt_pressed', False)
                rt_pressed = data.get('rt_pressed', False)
                
                lt_status = "🔴 PRESSED" if lt_pressed else "⚪ IDLE"
                rt_status = "🔴 PRESSED" if rt_pressed else "⚪ IDLE"
                
                self.lt_label.config(text=f"LT: {lt_val:3d} [{lt_status}]")
                self.rt_label.config(text=f"RT: {rt_val:3d} [{rt_status}]")
                
                lx = data.get('lx', 0)
                ly = data.get('ly', 0)
                rx = data.get('rx', 0)
                ry = data.get('ry', 0)
                self.stick_label.config(text=f"LS: ({lx:+5d}, {ly:+5d})  RS: ({rx:+5d}, {ry:+5d})")
                
                dpad = data.get('dpad', {})
                dpad_active = [d for d, pressed in dpad.items() if pressed]
                if dpad_active:
                    self.dpad_label.config(text=f"D-Pad: {', '.join(dpad_active)}")
                else:
                    self.dpad_label.config(text="D-Pad: None")
                
                clicks = data.get('dpad_clicks', {'UP': 0, 'DOWN': 0, 'LEFT': 0, 'RIGHT': 0})
                self.dpad_clicks_label.config(
                    text=f"Clicks: ↑{clicks.get('UP', 0)} ↓{clicks.get('DOWN', 0)} ←{clicks.get('LEFT', 0)} →{clicks.get('RIGHT', 0)}"
                )
                
                buttons = data.get('buttons', {})
                durations = data.get('durations', {})
                pressed_buttons = []
                for name, pressed in buttons.items():
                    if pressed and not name.startswith('DPAD_'):
                        if name in durations:
                            dur = durations[name]
                            indicator = "🔴" if dur > self.controller.settings.get('long_press_ms', 500) else ""
                            pressed_buttons.append(f"{name}({dur}ms{indicator})")
                        else:
                            pressed_buttons.append(name)
                
                if pressed_buttons:
                    self.button_label.config(text=f"Buttons: {', '.join(pressed_buttons)}")
                else:
                    self.button_label.config(text="Buttons: None")
                
                if data.get('back_held', False):
                    self.center_status.config(text="🎯 Holding BACK... centering soon!", foreground="orange")
                
                # Update rumble status
                if data.get('rumble_on_fire', True) or data.get('rumble_on_zoom', True):
                    self.rumble_status.config(text="💥 Rumble: Enabled", foreground="green")
                else:
                    self.rumble_status.config(text="💥 Rumble: Disabled", foreground="gray")
                
                # Update mode status
                fire_mode = data.get('fire_rumble_mode', 'burst')
                zoom_mode = data.get('zoom_rumble_mode', 'continuous')
                self.mode_status.config(text=f"Mode: Fire({fire_mode}) Zoom({zoom_mode})")
        except:
            pass
        
        self.root.after(50, self.update_values)
    
    def apply_preset(self, sensitivity, deadzone, trigger_deadzone, boost, dpad_step=5, click_mode=True):
        """Apply a preset"""
        self.controller.update_settings(
            mouse_sensitivity=sensitivity,
            axis_deadzone=deadzone,
            trigger_deadzone=trigger_deadzone,
            boost=boost,
            dpad_step=dpad_step,
            dpad_click_mode=click_mode
        )
        
        self.mouse_sensitivity_var.set(sensitivity)
        self.axis_deadzone_var.set(deadzone)
        self.trigger_deadzone_var.set(trigger_deadzone)
        self.boost_var.set(boost)
        self.dpad_step_var.set(dpad_step)
        self.dpad_click_mode_var.set(click_mode)
    
    def preset_sniper(self):
        self.apply_preset(0.06, 0.35, 0.40, 1.0, 2, True)
    
    def preset_balanced(self):
        self.apply_preset(0.18, 0.30, 0.35, 1.5, 5, True)
    
    def preset_action(self):
        self.apply_preset(0.25, 0.25, 0.30, 2.0, 8, False)
    
    def preset_precision(self):
        self.apply_preset(0.04, 0.40, 0.45, 1.0, 1, True)
    
    def run(self):
        """Start the GUI main loop"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle window close"""
        self.stop_controller()
        self.root.destroy()

# ============================================
# MAIN
# ============================================
if __name__ == "__main__":
    print("🎮 Xbox 360 Wireless Controller - Complete GUI")
    print("=" * 60)
    print("  LED + Rumble + All Buttons + Sticks + Triggers")
    print("  D-Pad → Click for Precision Mouse Movement")
    print("  Right Stick → Normal mouse look")
    print("  Left Stick → WASD movement")
    print("  LT → Zoom (with rumble!) | RT → Shoot (with rumble!)")
    print("  BACK (short) → Map | BACK (hold) → Center mouse 🎯")
    print("=" * 60)
    print("Starting GUI...")
    print("💡 Use mouse wheel to scroll up/down")
    
    controller = Xbox360Controller()
    gui = Xbox360TunerGUI(controller)
    gui.run()