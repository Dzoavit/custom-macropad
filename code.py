import board
import digitalio
import time
import rotaryio
import usb_hid
import usb_midi
import busio
import adafruit_ssd1306

from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.consumer_control_code import ConsumerControlCode

import adafruit_midi
from adafruit_midi.control_change import ControlChange

# --- INITIALIZE HID & MIDI ---
kbd = Keyboard(usb_hid.devices)
layout = KeyboardLayoutUS(kbd)
cc = ConsumerControl(usb_hid.devices)
midi = adafruit_midi.MIDI(midi_out=usb_midi.ports[1], out_channel=0)

# --- OLED DISPLAY SETUP ---
i2c = busio.I2C(board.GP19, board.GP18)
oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c, addr=0x3C)

# --- DISPLAY TIMER TRACKING ---
last_display_time = time.monotonic()
showing_default = True

def update_display(title, detail_line1="", detail_line2=""):
    """Shows text-based interactions (Volume, Keys, Media)"""
    global last_display_time, showing_default
    oled.fill(0)
    oled.text(title[:16], 0, 0, 1)         # Top Header
    oled.text(detail_line1[:20], 0, 24, 1) # Line 1
    oled.text(detail_line2[:20], 0, 42, 1) # Line 2
    oled.show()
    
    last_display_time = time.monotonic()
    showing_default = False

def show_default_screen():
    """Loads the custom image as the idle/default screen"""
    global last_display_time, showing_default
    oled.fill(0)
    
    # Layer name at the top
    oled.text(LAYER_NAMES[current_layer][:16], 0, 0, 1)
    
    try:
        with open("/image.bin", "rb") as f:
            # Read all 768 image bytes directly into the lower 48 rows (bytes 256-1023)
            oled.buffer[256:1024] = f.read(768)
    except OSError:
        oled.text("Image missing!", 0, 24, 1)
        
    oled.show()
    last_display_time = time.monotonic()
    showing_default = True

# --- PIN CONFIGURATION (REVERSED) ---
# Reversed to fix the 12-to-1 flip issue
button_pins = [
    board.GP10, board.GP9,  board.GP6,  board.GP16,
    board.GP17, board.GP8,  board.GP12, board.GP11,
    board.GP5,  board.GP14, board.GP15, board.GP0
]

# --- LAYER CONFIGURATION ---
LAYER_NAMES = ["DEFAULT MACROS", "UNASSIGNED"]
current_layer = 0

button_labels = [
    # LAYER 0: Default Macros
    [
        "Zoom In (+)", "Zoom Out (-)", "Bold (Ctrl+B)", "Undo (Ctrl+Z)",
        "Redo (Ctrl+Y)", "Alt + Tab", "Launch Discord", "Screenshot",
        "Show Desktop", "Launch Chrome", "Launch Spotify", "Launch Valorant"
    ],
    # LAYER 1: Unassigned
    [
        "Unassigned", "Unassigned", "Unassigned", "Unassigned",
        "Unassigned", "Unassigned", "Unassigned", "Unassigned",
        "Unassigned", "Unassigned", "Unassigned", "Unassigned"
    ]
]

buttons = []
last_state = []

for pin in button_pins:
    btn = digitalio.DigitalInOut(pin)
    btn.direction = digitalio.Direction.INPUT
    btn.pull = digitalio.Pull.DOWN
    buttons.append(btn)
    last_state.append(False)

# Encoder 1: Master Volume (MIDI) & Play/Pause (HID)
enc1 = rotaryio.IncrementalEncoder(board.GP21, board.GP22, divisor=2)
enc1_btn = digitalio.DigitalInOut(board.GP2)
enc1_btn.direction = digitalio.Direction.INPUT
enc1_btn.pull = digitalio.Pull.UP  

# Encoder 2: Track Control (HID) & Layer Switcher
enc2 = rotaryio.IncrementalEncoder(board.GP28, board.GP27, divisor=2)
enc2_btn = digitalio.DigitalInOut(board.GP4)
enc2_btn.direction = digitalio.Direction.INPUT
enc2_btn.pull = digitalio.Pull.UP  

# --- STATE TRACKING VARIABLES ---
last_pos1 = enc1.position
last_pos2 = enc2.position
last_enc1_btn_state = True 
last_enc2_btn_state = True

# Display startup screen
show_default_screen()

# --- HELPER FUNCTIONS ---
def press_keys(*keys):
    kbd.press(*keys)
    time.sleep(0.05)
    kbd.release_all()

def run_command(cmd):
    press_keys(Keycode.WINDOWS, Keycode.R)
    time.sleep(0.4) 
    layout.write(cmd) 
    time.sleep(0.1)
    press_keys(Keycode.ENTER)

def handle_button(i):
    layer_name = LAYER_NAMES[current_layer]
    action_name = button_labels[current_layer][i]
    
    update_display(layer_name, f"Key {i+1}:", action_name)
    
    # --- LAYER 0 LOGIC ---
    if current_layer == 0:
        if i == 0: press_keys(Keycode.CONTROL, Keycode.EQUALS)
        elif i == 1: press_keys(Keycode.CONTROL, Keycode.MINUS)
        elif i == 2: press_keys(Keycode.CONTROL, Keycode.B)
        elif i == 3: press_keys(Keycode.CONTROL, Keycode.Z)
        elif i == 4: press_keys(Keycode.CONTROL, Keycode.Y)
        elif i == 5: press_keys(Keycode.ALT, Keycode.TAB)
        elif i == 6: run_command('"C:\\macro\\disc.lnk"') 
        elif i == 7: press_keys(Keycode.WINDOWS, Keycode.SHIFT, Keycode.S)
        elif i == 8: press_keys(Keycode.WINDOWS, Keycode.D)
        elif i == 9: run_command("chrome")
        elif i == 10: run_command("spotify")
        elif i == 11: run_command('"C:\\macro\\VALO.lnk"')
        
    # --- LAYER 1 LOGIC (Unassigned) ---
    elif current_layer == 1:
        pass  # No key actions executed for this layer

# --- MAIN LOOP ---
while True:
    # 1. Handle Button Grid
    for i, btn in enumerate(buttons):
        if btn.value and not last_state[i]:
            handle_button(i)
        last_state[i] = btn.value

    # 2. Encoder 1: Master Volume (MIDI CC #1) & Play/Pause
    pos2 = enc2.position
    if pos2 != last_pos2:
        if pos2 > last_pos2:
            midi.send(ControlChange(1, 1))
            update_display("MIDI CONTROL", "Master Volume", "Turned UP (+)")
        else:
            midi.send(ControlChange(1, 127))
            update_display("MIDI CONTROL", "Master Volume", "Turned DOWN (-)")
        last_pos2 = pos2

    current_enc2_state = enc2_btn.value
    if not current_enc2_state and last_enc2_btn_state: 
        cc.send(ConsumerControlCode.PLAY_PAUSE)
        update_display("MEDIA CONTROL", "Action:", "Play / Pause")
    last_enc2_btn_state = current_enc2_state

    # 3. Encoder 2: Track Skipping (HID) & Layer Switch
    pos1 = enc1.position
    if pos1 != last_pos1:
        if pos1 > last_pos1:
            cc.send(ConsumerControlCode.SCAN_NEXT_TRACK)
            update_display("MEDIA CONTROL", "Track Selection", ">> Next Track")
        else:
            cc.send(ConsumerControlCode.SCAN_PREVIOUS_TRACK)
            update_display("MEDIA CONTROL", "Track Selection", "<< Prev Track")
        last_pos1 = pos1

    current_enc1_state = enc1_btn.value
    if not current_enc1_state and last_enc1_btn_state: 
        current_layer = (current_layer + 1) % len(LAYER_NAMES)
        show_default_screen()
    last_enc1_btn_state = current_enc1_state

    # 4. 2-Second Display Timeout
    if not showing_default and (time.monotonic() - last_display_time >= 2.0):
        show_default_screen()

    time.sleep(0.01)