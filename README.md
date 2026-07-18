# Xbox 360 Wireless Controller - Complete GUI Controller

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

<div align="center">
  <img src="https://github.com/igiteam/xbox360_input_gui_py/blob/main/xbox360%20Genuine%20controller.png?raw=true" alt="Xbox 360 Wireless Controller" width="300"/>
  <img src="https://github.com/igiteam/xbox360_input_gui_py/blob/main/Xbox360%20Genuine%20Microsoft%20Wireless%20Controller%20Receiver%20White%20Windows%20PC.png?raw=true" alt="Microsoft Wireless Receiver" width="300"/>
</div>

A comprehensive Python application that turns your Xbox 360 wireless controller into a fully customizable PC game controller with LED control, rumble feedback, and precision aiming. Optimized specifically for Operation Flashpoint but works with any PC game.

✅ Tested on: Xbox 360 Controller + Xbox 360 PC Wireless Gaming Receiver + macOS Big Sur

## 🎮 Features

### Complete Controller Support
- **All Buttons**: A, B, X, Y, LB, RB, Start, Back, L3, R3, Guide
- **Analog Sticks**: Left stick for WASD movement, Right stick for mouse look
- **Analog Triggers**: LT for zoom, RT for shoot
- **D-Pad**: Precision aiming with click or hold modes
- **LED Control**: Player indicator LEDs
- **Rumble Feedback**: Burst or continuous modes for fire and zoom

### Precision Aiming
- **D-Pad Click Mode**: Each click moves mouse by adjustable step size
- **D-Pad Hold Mode**: Continuous mouse movement while held
- **Adjustable Step Size**: 1-30 pixels per click
- **Zero Input Lag**: Async mouse processing for smooth aiming

### Advanced Features
- **Async Mouse Processing**: No input lag, smooth mouse movement
- **USB Retry Logic**: Robust USB communication with automatic retries
- **Rumble Modes**:
  - Burst: Quick rumble feedback
  - Continuous: Sustained rumble while held
- **Configurable Deadzones**: Axis and trigger deadzone adjustment
- **Mouse Sensitivity**: Fully adjustable sensitivity
- **Boost**: Sensitivity multiplier for fast turns
- **Invert Y**: Invert stick Y-axis
- **Mouse Centering**: Long-press Back button to center mouse

### Live GUI Tuner
- **Real-time Feedback**: See all controller values update live
- **Adjustable Settings**: All settings configurable via sliders
- **Presets**: Quick switching between Sniper, Balanced, Action, Precision
- **Scrollable Interface**: Mouse wheel support for navigation
- **Top-most Window**: Always visible while gaming

## 📋 Requirements

### Hardware
- Xbox 360 Wireless Receiver (Microsoft or compatible)
- Xbox 360 Wireless Controller
- USB port

### Software
- Python 3.8 or higher
- macOS/Linux/Windows (with libusb)

### Python Dependencies (auto-installed)
- `pyusb` - USB communication
- `pygame` - SDL dummy environment
- `keyboard` - Keyboard simulation
- `pynput` - Mouse control
- `pyautogui` - Screen management

## 🚀 Installation

### 1. Clone the Repository
git clone https://github.com/yourusername/xbox360-controller-gui.git
cd xbox360-controller-gui

2. Install System Dependencies

macOS:
brew install libusb

Linux (Ubuntu/Debian):
sudo apt-get install libusb-1.0-0-dev

Windows:
    Install libusb-win32
    Or use Zadig to install WinUSB driver

3. Create Virtual Environment (Recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

4. Run the Application
python3 xbox360_controller_input_gui_ofp.py

The script will automatically install all Python dependencies.
🎯 How to Use

Initial Setup
1. Connect Receiver: Plug in the Xbox 360 wireless receiver
2. Start Application: Run the script
3. Click "Connect": Verify receiver is detected
4. Click "Start Controller": Initialize the controller
5. Sync Controller: Press the sync button on receiver, then on controller
6. Calibrate: Don't touch sticks during calibration

### Button Mapping (Operation Flashpoint)

Controller    Keyboard    Function
A             V           Action/Interact
B             R           Reload
X             E           Use/Enter vehicle
Y             Space       Jump
LB            Shift       Aim Down Sights
RB            K           Throw Grenade
L3            Up Arrow    Map Zoom In
R3            G           Gear/Inventory
Start         Esc         Menu
Back (short)  Tab         Map
Back (hold)   -           Center Mouse

Joystick Controls
- Left Stick: WASD movement
- Right Stick: Mouse look
- LT (Left Trigger): Zoom (Q key)
- RT (Right Trigger): Shoot (Mouse Left Click)

D-Pad Modes
1. Hold Mode (Default): Continuous mouse movement while held
2. Click Mode: Each click moves mouse by step size

### Customization

Sensitivity Presets
- Sniper: Low sensitivity, high precision (0.06 sens)
- Balanced: Medium sensitivity (0.18 sens)
- Action: High sensitivity (0.25 sens)
- Precision: Very low sensitivity (0.04 sens)

Advanced Settings
- Mouse Sensitivity: 0.02 - 0.5
- Axis Deadzone: 0.05 - 0.5
- Trigger Deadzone: 0.1 - 0.5
- D-Pad Step: 1 - 30 pixels
- Boost: 0.5x - 3.0x
- Long Press: 100 - 1000ms


### 🔧 Troubleshooting

Controller Not Detected
1. Check USB connection
2. Click "Connect" button
3. Try different USB port
4. On Linux/macOS, check USB permissions

LED Not Working
- The application will retry LED commands 3 times
- LED should light up as Player 1 (top-left quadrant)
- If not, try restarting the application

Rumble Not Working
- Ensure "Rumble on Fire" and "Rumble on Zoom" are enabled
- Try switching between Burst and Continuous modes
- Check intensity slider (20-255)

USB Permission Issues (Linux)

# Add user to plugdev group
sudo usermod -a -G plugdev $USER

# Create udev rule
echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="045e", ATTR{idProduct}=="0291", MODE="0666"' | sudo tee /etc/udev/rules.d/50-xbox360.rules
sudo udevadm control --reload-rules
sudo udevadm trigger

Input Lag
- Async mouse processing is enabled by default
- Check your system's mouse settings
- Reduce polling rate in game settings


🎮 Game-Specific Configuration

Operation Flashpoint
The application is optimized for Operation Flashpoint with the following mappings:
- WASD for movement
- Mouse for aiming
- Q for zoom
- Mouse left click for shooting
- Tab for map
- Escape for menu

### Other Games
You can customize the button mappings in the BUTTON_MAP dictionary:

BUTTON_MAP = {
    'A': 'v',      # Change to your preferred key
    'B': 'r',      # Change to your preferred key
    # ...
}

\`\`\`
📁 Project Structure

xbox360-controller-gui/
├── xbox360_controller_input_gui_ofp.py  # Main application
├── README.md                             # This file
└── LICENSE                               # MIT License
\`\`\`

### 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

Development Setup
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

Reporting Issues
- Use the GitHub issue tracker
- Include your OS, Python version, and error logs
- Describe steps to reproduce


### 📄 License

MIT License - See LICENSE file for details.


### 🙏 Acknowledgments

- pyusb - USB communication
- pynput - Mouse control
- keyboard - Keyboard simulation
- Xbox 360 controller community for USB protocol documentation


### ⚠️ Disclaimer

This software is provided "as is" without warranty. Use at your own risk. The author is not responsible for any damage or loss of data.


Enjoy gaming with your Xbox 360 controller! 🎮