import os
import sys
import math
import random
import pygame
import pygame.scrap
from datetime import datetime

# -----------------------------------------------------------------------------
# Steampunk Palette & Configuration
# -----------------------------------------------------------------------------
BLACK = (15, 12, 10)
BRASS = (181, 137, 0)
BRASS_DARK = (101, 67, 33)
BRASS_LIGHT = (255, 215, 0)
COPPER = (184, 115, 51)
NIXIE_GLOW = (255, 140, 0)
VOICE_ACTIVE = (0, 255, 127)
CYAN_GLOW = (0, 210, 255)
AMBER_GLOW = (255, 160, 20)
TEXT_COLOR = (255, 240, 190)
MUTED_BRASS = (140, 110, 70)

WIDTH, HEIGHT = 808, 784
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

NIXIE_DIR = os.path.join(BASE_DIR, "nixie_images", "drawable-hdpi")
if not os.path.exists(NIXIE_DIR):
    NIXIE_DIR = os.path.expanduser("~/.local/share/steampunk_assets/nixie_tubes")
if not os.path.exists(NIXIE_DIR):
    NIXIE_DIR = "/home/pcarff/Downloads/nixie_images/drawable-hdpi"

SIGNALS_DIRS = ["/dev/shm/signals", "/tmp/signals"]


# -----------------------------------------------------------------------------
# Signal Bus State & Typed Input Writer
# -----------------------------------------------------------------------------
def get_voice_state() -> str:
    """Read real-time voice state from backtalk signal bus."""
    for s_dir in SIGNALS_DIRS:
        state_file = os.path.join(s_dir, ".voice_state")
        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    return f.read().strip().lower()
            except Exception:
                pass
    return "idle"


def send_typed_message(text: str):
    """Deliver typed message to backtalk through signal bus queue file."""
    for s_dir in SIGNALS_DIRS:
        try:
            os.makedirs(s_dir, exist_ok=True)
            sig_file = os.path.join(s_dir, ".typed_input")
            with open(sig_file, "w", encoding="utf-8") as f:
                f.write(text.strip() + "\n")
            # Immediate responsive visual feedback
            state_file = os.path.join(s_dir, ".voice_state")
            with open(state_file, "w") as sf:
                sf.write("thinking")
            return True
        except Exception:
            pass
    return False


# -----------------------------------------------------------------------------
# System Clipboard Access (Tkinter / Pygame Scrap / CLI)
# -----------------------------------------------------------------------------
_tk_root = None


def get_clipboard_text() -> str:
    """Retrieve plain text from system clipboard using the best available backend."""
    global _tk_root
    # 1. Tkinter (fastest & most reliable on Linux X11, ~0.3ms)
    try:
        if _tk_root is None:
            import tkinter as tk
            _tk_root = tk.Tk()
            _tk_root.withdraw()
        text = _tk_root.clipboard_get()
        if text:
            return text
    except Exception:
        _tk_root = None

    # 2. Pygame scrap
    try:
        if pygame.scrap.get_init():
            for mime in ("text/plain;charset=utf-8", "UTF8_STRING", "TEXT"):
                raw = pygame.scrap.get(mime)
                if raw:
                    return raw.decode("utf-8", errors="replace").rstrip("\x00")
    except Exception:
        pass

    # 3. CLI fallbacks (xclip / xsel / wl-paste)
    import subprocess
    import shutil
    for cmd in (
        ["xclip", "-selection", "clipboard", "-o"],
        ["xsel", "-b", "-o"],
        ["wl-paste", "--no-newline"],
    ):
        if shutil.which(cmd[0]):
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=0.3)
                if res.returncode == 0 and res.stdout:
                    return res.stdout
            except Exception:
                pass
    return ""


def set_clipboard_text(text: str):
    """Set system clipboard text."""
    global _tk_root
    try:
        if _tk_root is None:
            import tkinter as tk
            _tk_root = tk.Tk()
            _tk_root.withdraw()
        _tk_root.clipboard_clear()
        _tk_root.clipboard_append(text)
        _tk_root.update()
    except Exception:
        _tk_root = None


# -----------------------------------------------------------------------------
# Nixie Tube Component & Realistic Industrial Backplate Bank
# -----------------------------------------------------------------------------
class NixieTube:
    def __init__(self, index=0, x=0, y=0, size=60, bank=None):
        self.index = index
        self.x = x
        self.y = y
        self.size = size
        self.value = str(random.randint(0, 9))
        self.bank = bank

    def draw(self, surface):
        if self.bank:
            d_idx = int(self.value) if self.value.isdigit() else 0
            d_surf = self.bank.digit_surfaces.get(d_idx)
            if d_surf:
                surface.blit(d_surf, (self.x, self.y))


class NixieBank:
    def __init__(self, x=70, y=88, width=660, height=120):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

        # Load Realistic Rustic Backplate
        bp_paths = [
            os.path.join(BASE_DIR, "nixie_backplate.png"),
            os.path.expanduser("~/.local/share/steampunk_assets/textures/nixie_backplate.png"),
            "/tmp/nixie_backplate_master.png",
        ]
        self.backplate = None
        for p in bp_paths:
            if os.path.exists(p):
                raw = pygame.image.load(p).convert_alpha()
                self.backplate = pygame.transform.smoothscale(raw, (self.width, self.height))
                break

        # Sizing: 44x80 socket chamber, 42x76 slender digit (ratio 0.553, eliminating squatness)
        self.inner_w = 44
        self.inner_h = 80
        self.digit_w = 42
        self.digit_h = 76

        digit_names = [
            "zeroam.jpg", "oneam.jpg", "twoam.jpg", "threeam.jpg",
            "fouram.jpg", "fiveam.jpg", "sixam.jpg", "sevenam.jpg",
            "eightam.jpg", "nineam.jpg"
        ]

        # Pre-render luminous slender digits (warm amber glow + slender digit + glass glint)
        self.digit_surfaces = {}
        for i in range(10):
            surf = pygame.Surface((self.inner_w, self.inner_h), pygame.SRCALPHA)

            # 1. Warm radial amber glow behind filament
            gcx, gcy = self.inner_w // 2, self.inner_h // 2
            for r in range(self.inner_h // 2, 0, -3):
                alpha = int(45 * (1.0 - r / (self.inner_h // 2)))
                pygame.draw.ellipse(surf, (255, 140, 0, alpha), (gcx - r, gcy - r, r * 2, r * 2))

            # 2. Slender scaled Nixie digit
            img_path = os.path.join(NIXIE_DIR, digit_names[i])
            if os.path.exists(img_path):
                raw_d = pygame.image.load(img_path).convert_alpha()
                scaled_d = pygame.transform.smoothscale(raw_d, (self.digit_w, self.digit_h))
                surf.blit(scaled_d, (1, 2))

            # 3. Specular glass glint (vertical reflection streak on left edge)
            pygame.draw.line(surf, (255, 255, 255, 45), (3, 6), (3, self.inner_h - 8), 2)
            pygame.draw.line(surf, (255, 255, 255, 80), (4, 10), (4, self.inner_h - 14), 1)

            self.digit_surfaces[i] = surf

        # Create 8 tube units aligned with the backplate's milled brass socket bays
        self.tubes = []
        for i in range(8):
            tx = self.x + 56 + i * 72
            ty = self.y + 20
            self.tubes.append(NixieTube(index=i, x=tx, y=ty, bank=self))

    def draw(self, surface):
        if self.backplate:
            surface.blit(self.backplate, (self.x, self.y))
        for tube in self.tubes:
            d_idx = int(tube.value) if tube.value.isdigit() else 0
            d_surf = self.digit_surfaces.get(d_idx)
            if d_surf:
                surface.blit(d_surf, (tube.x, tube.y))


# -----------------------------------------------------------------------------
# Operational Steampunk Clock Component (FLUX Chronometer)
# -----------------------------------------------------------------------------
class SteampunkClock:
    def __init__(self, cx, cy, size=154):
        self.cx = cx
        self.cy = cy
        self.size = size
        self.radius = size // 2
        self.scale = size / 1024.0

        paths = [
            os.path.join(BASE_DIR, "clock_dial_base_trans.png"),
            "/home/pcarff/Pictures/Flux_Generations/clock_dial_base_trans.png",
            os.path.expanduser("~/.local/share/steampunk_assets/textures/clock_dial_base_trans.png"),
        ]
        self.dial_img = None
        for p in paths:
            if os.path.exists(p):
                raw = pygame.image.load(p).convert_alpha()
                self.dial_img = pygame.transform.smoothscale(raw, (size, size))
                break

    def draw(self, surface):
        if self.dial_img:
            surface.blit(self.dial_img, (self.cx - self.radius, self.cy - self.radius))

        now = datetime.now()
        hours = now.hour % 12
        minutes = now.minute
        seconds = now.second
        usecs = now.microsecond

        sec_val = seconds + usecs / 1_000_000.0
        min_val = minutes + sec_val / 60.0
        hour_val = hours + min_val / 60.0

        hour_angle = math.radians(hour_val * 30.0 - 90.0)
        min_angle = math.radians(min_val * 6.0 - 90.0)
        sec_angle = math.radians(sec_val * 6.0 - 90.0)

        hour_len = 175.0 * self.scale
        min_len = 245.0 * self.scale
        sec_len = 270.0 * self.scale

        # Hour Hand (lancet pointer with glowing amber core)
        self._draw_lancet(surface, hour_angle, hour_len, 4.5, (255, 175, 40), (180, 135, 30))

        # Minute Hand (slender lancet pointer)
        self._draw_lancet(surface, min_angle, min_len, 3.5, (255, 185, 50), (180, 135, 30))

        # Second Hand (fine copper / vermillion needle)
        cos_s = math.cos(sec_angle)
        sin_s = math.sin(sec_angle)
        sx = self.cx + sec_len * cos_s
        sy = self.cy + sec_len * sin_s
        tx = self.cx - 26 * self.scale * cos_s
        ty = self.cy - 26 * self.scale * sin_s

        # Shadow
        pygame.draw.line(surface, (15, 10, 8), (tx + 1, ty + 2), (sx + 1, sy + 2), 2)
        # Needle
        pygame.draw.line(surface, (230, 50, 40), (self.cx, self.cy), (sx, sy), 2)
        pygame.draw.line(surface, (184, 115, 51), (tx, ty), (self.cx, self.cy), 2)
        # Counterbalance
        pygame.draw.circle(surface, (255, 215, 0), (int(tx), int(ty)), max(2, int(3 * self.scale)))

        # Polished Brass Center Hub
        hub_r = max(4, int(28.0 * self.scale))
        pygame.draw.circle(surface, (25, 16, 10), (self.cx + 1, self.cy + 2), hub_r + 1)
        pygame.draw.circle(surface, (181, 137, 0), (self.cx, self.cy), hub_r)
        pygame.draw.circle(surface, (255, 215, 0), (self.cx, self.cy), hub_r - 2)
        pygame.draw.circle(surface, (190, 140, 20), (self.cx, self.cy), hub_r - 4)
        # Specular dot
        pygame.draw.circle(surface, (255, 255, 220), (self.cx - int(hub_r * 0.35), self.cy - int(hub_r * 0.35)), max(1, int(hub_r * 0.25)))

    def _draw_lancet(self, surface, angle, length, width, core_color, border_color):
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)
        perp_cos = -sin_a
        perp_sin = cos_a

        tip_x = self.cx + length * cos_a
        tip_y = self.cy + length * sin_a
        base_l_x = self.cx + width * perp_cos
        base_l_y = self.cy + width * perp_sin
        base_r_x = self.cx - width * perp_cos
        base_r_y = self.cy - width * perp_sin
        tail_x = self.cx - (length * 0.18) * cos_a
        tail_y = self.cy - (length * 0.18) * sin_a

        poly = [(tip_x, tip_y), (base_r_x, base_r_y), (tail_x, tail_y), (base_l_x, base_l_y)]

        # Drop shadow
        shadow_poly = [(x + 2, y + 2) for x, y in poly]
        pygame.draw.polygon(surface, (12, 8, 6), shadow_poly)

        # Outer border
        pygame.draw.polygon(surface, border_color, poly)

        # Luminous inner core
        inner_poly = [
            (tip_x - 3 * cos_a, tip_y - 3 * sin_a),
            (self.cx - (width * 0.5) * perp_cos, self.cy - (width * 0.5) * perp_sin),
            (tail_x + 3 * cos_a, tail_y + 3 * sin_a),
            (self.cx + (width * 0.5) * perp_cos, self.cy + (width * 0.5) * perp_sin)
        ]
        pygame.draw.polygon(surface, core_color, inner_poly)


# -----------------------------------------------------------------------------
# Operational Analog Telemetry Meter Component
# -----------------------------------------------------------------------------
class AnalogMeter:
    def __init__(self, cx, cy, size=140, face_name="meter_face_dial_trans.png"):
        self.cx = cx
        self.cy = cy
        self.size = size
        self.radius = size // 2
        path = os.path.join(BASE_DIR, face_name)
        if not os.path.exists(path):
            path = os.path.expanduser(f"~/.local/share/steampunk_assets/textures/{face_name}")
        self.face_img = None
        if os.path.exists(path):
            raw = pygame.image.load(path).convert_alpha()
            self.face_img = pygame.transform.smoothscale(raw, (size, size))
        self.angle = 0.0
        self.target_angle = 0.0

    def update(self, is_working, is_speaking):
        if is_working:
            self.target_angle = random.uniform(-38, 38)
        elif is_speaking:
            self.target_angle = math.sin(pygame.time.get_ticks() * 0.008) * 22.0
        else:
            self.target_angle = math.sin(pygame.time.get_ticks() * 0.002) * 8.0 - 15.0
        self.angle += (self.target_angle - self.angle) * 0.15

    def draw(self, surface):
        if self.face_img:
            surface.blit(self.face_img, (self.cx - self.radius, self.cy - self.radius))
        
        rad = math.radians(self.angle - 90)
        r = int(self.size * 0.38)
        tx = self.cx + r * math.cos(rad)
        ty = self.cy + r * math.sin(rad)
        
        # Shadow
        pygame.draw.line(surface, (15, 10, 8), (self.cx + 1, self.cy + 2), (tx + 1, ty + 2), 2)
        # Vermillion Needle
        pygame.draw.line(surface, (220, 45, 30), (self.cx, self.cy), (tx, ty), 2)
        # Brass Pivot Hub
        pygame.draw.circle(surface, (181, 137, 0), (self.cx, self.cy), 6)
        pygame.draw.circle(surface, (255, 215, 0), (self.cx, self.cy), 3)


# -----------------------------------------------------------------------------
# Main Visualizer Loop
# -----------------------------------------------------------------------------

def main():
    # Enable smooth hardware bilinear scaling for high-DPI / 4K displays
    os.environ["SDL_RENDER_SCALE_QUALITY"] = "1"
    pygame.init()
    pygame.font.init()
    try:
        pygame.scrap.init()
    except Exception:
        pass

    # Determine default scale factor based on screen height (e.g. 4K 3840x2160)
    display_info = pygame.display.Info()
    env_scale = os.environ.get("MILO_SCALE")
    if env_scale:
        try:
            scale_factor = float(env_scale)
        except ValueError:
            scale_factor = 1.85 if display_info.current_h >= 2000 else 1.0
    else:
        # 4K screens (>=2000px): default 1.85x (~1495x1450)
        # 1440p screens (>=1400px): default 1.4x (~1131x1097)
        # 1080p screens: default 1.0x (808x784)
        if display_info.current_h >= 2000:
            scale_factor = 1.85
        elif display_info.current_h >= 1400:
            scale_factor = 1.4
        else:
            scale_factor = 1.0
    default_scale = scale_factor

    win_w = int(WIDTH * scale_factor)
    win_h = int(HEIGHT * scale_factor)
    screen = pygame.display.set_mode((win_w, win_h), pygame.RESIZABLE)
    canvas = pygame.Surface((WIDTH, HEIGHT))

    # Load ornate box background
    box_bg_path = os.path.join(BASE_DIR, 'box_background.png')
    if os.path.exists(box_bg_path):
        box_bg = pygame.image.load(box_bg_path).convert()
        box_bg = pygame.transform.smoothscale(box_bg, (WIDTH, HEIGHT))
    else:
        box_bg = pygame.Surface((WIDTH, HEIGHT))
        box_bg.fill(BLACK)

    pygame.display.set_caption("MILO — Steampunk Telemetry & Voice Console")
    clock = pygame.time.Clock()

    # Load Background (Dark Walnut)
    # Load Background (Dark Walnut)
    bg_path = os.path.join(NIXIE_DIR, "dkwalnut.jpg")
    if not os.path.exists(bg_path):
        bg_path = os.path.join(BASE_DIR, "nixie_images", "drawable-hdpi", "dkwalnut.jpg")
    if not os.path.exists(bg_path):
        bg_path = "/home/pcarff/Downloads/nixie_images/drawable-hdpi/dkwalnut.jpg"
    bg_texture = None
    if os.path.exists(bg_path):
        bg_texture = pygame.image.load(bg_path).convert()
        bg_texture = pygame.transform.scale(bg_texture, (WIDTH, HEIGHT))

    # Load Title Plate (MILO Flight Director Brass Plate)
    title_plate_path = os.path.join(BASE_DIR, "milo_plate.png")
    title_plate = None
    if os.path.exists(title_plate_path):
        raw_plate = pygame.image.load(title_plate_path).convert_alpha()
        target_w = 300
        ratio = target_w / raw_plate.get_width()
        target_h = int(raw_plate.get_height() * ratio)
        title_plate = pygame.transform.smoothscale(raw_plate, (target_w, target_h))

    # Load Transparent Lamp Graphics (Hex Jewel Fixture - mounted beside input tray)
    lamp_w, lamp_h = 46, 44
    lamp_on_path = os.path.join(BASE_DIR, "lamp_on_trans.png")
    if not os.path.exists(lamp_on_path):
        lamp_on_path = "/home/pcarff/Downloads/lamp_on_trans.png"
    lamp_off_path = os.path.join(BASE_DIR, "lamp_off_trans.png")
    if not os.path.exists(lamp_off_path):
        lamp_off_path = "/home/pcarff/Downloads/lamp_off_trans.png"

    lamp_on_img = None
    lamp_off_img = None
    if os.path.exists(lamp_on_path):
        raw_on = pygame.image.load(lamp_on_path).convert_alpha()
        lamp_on_img = pygame.transform.smoothscale(raw_on, (lamp_w, lamp_h))
    if os.path.exists(lamp_off_path):
        raw_off = pygame.image.load(lamp_off_path).convert_alpha()
        lamp_off_img = pygame.transform.smoothscale(raw_off, (lamp_w, lamp_h))

    # Layout Coordinates for Option B Handcrafted Cabinet:
    # 1. Operational Steampunk Clock (Fitted inside circular porthole bezel: 234px diameter)
    clock_cx = 404
    clock_cy = 432
    clock_widget = SteampunkClock(cx=clock_cx, cy=clock_cy, size=234)

    # 2. Dual Analog Telemetry Meters flanking the clock
    meter_left = AnalogMeter(cx=204, cy=432, size=140)
    meter_right = AnalogMeter(cx=604, cy=432, size=140)

    # 3. Voice Indicator Lamp (mounted beside input tray)
    lamp_x = 695
    lamp_y = 638
    lamp_center_x = lamp_x + lamp_w // 2
    lamp_center_y = lamp_y + lamp_h // 2

    # 4. Realistic Nixie Tube Bank (Upper bay centered tubes)
    nixie_bank = NixieBank(x=85, y=115, width=640, height=110)
    tubes = nixie_bank.tubes
    nixie_start_x = 404 - (7 * 68 + 44) // 2
    nixie_y = 164

    # Fonts
    font_plate = pygame.font.SysFont("serif", 16, bold=True)
    font_sub = pygame.font.SysFont("serif", 10, bold=True)
    font_title = pygame.font.SysFont("monospace", 26, bold=True)
    font_input = pygame.font.SysFont("monospace", 15)
    font_small = pygame.font.SysFont("monospace", 12)

    # Pre-render Nameplate
    t_surf_sh = font_plate.render("M.I.L.O.", True, (180, 150, 80))
    t_surf = font_plate.render("M.I.L.O.", True, (40, 26, 12))
    s_surf_sh = font_sub.render("FLIGHT DIRECTOR", True, (180, 150, 80))
    s_surf = font_sub.render("FLIGHT DIRECTOR", True, (50, 32, 16))

    # State Variables
    input_text = ""
    last_sent_text = ""
    pulse_phase = 0.0
    cursor_timer = 0
    running = True

    while running:
        cursor_timer = (cursor_timer + 1) % 60
        cursor_visible = cursor_timer < 30

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 3:  # Right-click pastes clipboard text into input box
                    clip = get_clipboard_text()
                    if clip:
                        clean = " ".join(clip.split())
                        if clean:
                            remaining = 1000 - len(input_text)
                            if remaining > 0:
                                input_text += clean[:remaining]
            elif event.type == pygame.KEYDOWN:
                ctrl_pressed = bool(event.mod & pygame.KMOD_CTRL)
                shift_pressed = bool(event.mod & pygame.KMOD_SHIFT)

                # Paste from clipboard (Ctrl+V or Shift+Insert)
                if (ctrl_pressed and event.key == pygame.K_v) or (shift_pressed and event.key == pygame.K_INSERT):
                    clip = get_clipboard_text()
                    if clip:
                        clean = " ".join(clip.split())
                        if clean:
                            remaining = 1000 - len(input_text)
                            if remaining > 0:
                                input_text += clean[:remaining]
                # Copy current input text to clipboard (Ctrl+C)
                elif ctrl_pressed and event.key == pygame.K_c:
                    if input_text:
                        set_clipboard_text(input_text)
                # Clear entire input line (Ctrl+U)
                elif ctrl_pressed and event.key == pygame.K_u:
                    input_text = ""
                # Delete previous word (Ctrl+Backspace or Ctrl+W)
                elif ctrl_pressed and event.key in (pygame.K_BACKSPACE, pygame.K_w):
                    parts = input_text.rstrip().rsplit(" ", 1)
                    input_text = parts[0] if len(parts) > 1 else ""
                elif event.key == pygame.K_ESCAPE:
                    running = False
                elif ctrl_pressed and event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    scale_factor = round(min(3.0, scale_factor + 0.1), 2)
                    new_w = int(WIDTH * scale_factor)
                    new_h = int(HEIGHT * scale_factor)
                    screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE)
                elif ctrl_pressed and event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE, pygame.K_KP_MINUS):
                    scale_factor = round(max(0.6, scale_factor - 0.1), 2)
                    new_w = int(WIDTH * scale_factor)
                    new_h = int(HEIGHT * scale_factor)
                    screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE)
                elif ctrl_pressed and event.key in (pygame.K_0, pygame.K_KP_0):
                    scale_factor = default_scale
                    new_w = int(WIDTH * scale_factor)
                    new_h = int(HEIGHT * scale_factor)
                    screen = pygame.display.set_mode((new_w, new_h), pygame.RESIZABLE)
                elif event.key == pygame.K_RETURN:
                    msg = input_text.strip()
                    if msg:
                        send_typed_message(msg)
                        last_sent_text = msg
                        input_text = ""
                elif event.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                else:
                    if not ctrl_pressed and len(input_text) < 1000 and event.unicode and event.unicode.isprintable():
                        input_text += event.unicode

        # Query real-time voice state from backtalk signal bus
        voice_state = get_voice_state()
        is_user_talking = (voice_state == "listening")
        is_working = (voice_state == "thinking")
        is_thinking = (voice_state == "thinking")
        is_speaking = (voice_state == "speaking")

        # ---------------------------------------------------------------------
        # Nixie Tube Behavior:
        # - When MILO is working (thinking): numbers flicker rapidly
        # - In all other states (idle, listening, or MILO speaking): numbers stay FROZEN
        # ---------------------------------------------------------------------
        if is_working:
            for tube in tubes:
                if random.random() < 0.28:  # Rapid telemetry calculation flicker
                    tube.value = str(random.randint(0, 9))
        # When waiting for user or when MILO is speaking: DO NOTHING -> NUMBERS STAY FROZEN

        pulse_phase += 0.08
        glow_pulse = (math.sin(pulse_phase) + 1.0) * 0.5

        # --- Draw Background Cabinet onto Virtual Canvas ---
        canvas.blit(box_bg, (0, 0))

        # --- Draw Engraved Nameplate Text ---
        canvas.blit(t_surf_sh, (404 - t_surf.get_width() // 2 + 1, 75 + 1))
        canvas.blit(t_surf, (404 - t_surf.get_width() // 2, 75))
        canvas.blit(s_surf_sh, (404 - s_surf.get_width() // 2 + 1, 95 + 1))
        canvas.blit(s_surf, (404 - s_surf.get_width() // 2, 95))

        # --- Draw Realistic Nixie Tubes (Centered in Upper Bay at Y=164) ---
        for i, tube in enumerate(tubes):
            tx = nixie_start_x + i * 68
            ty = nixie_y
            d_idx = int(tube.value) if tube.value.isdigit() else 0
            d_surf = nixie_bank.digit_surfaces.get(d_idx)
            if d_surf:
                canvas.blit(d_surf, (tx, ty))

        # --- Update & Draw Dual Analog Telemetry Meters ---
        meter_left.update(is_working, is_speaking)
        meter_right.update(is_working, is_speaking)
        meter_left.draw(canvas)
        meter_right.draw(canvas)

        # --- Draw Centered Steampunk Clock (Porthole Bezel: 234px) ---
        clock_widget.draw(canvas)

        # ---------------------------------------------------------------------
        # Steampunk Text Input Box (Recessed Lower Tray)
        # ---------------------------------------------------------------------
        input_box_rect = pygame.Rect(130, 638, 548, 44)

        # Outer Brass Frame
        pygame.draw.rect(canvas, (15, 12, 10), input_box_rect, border_radius=6)
        border_color = BRASS_LIGHT if (pygame.time.get_ticks() % 1200 < 600 and len(input_text) > 0) else BRASS
        pygame.draw.rect(canvas, border_color, input_box_rect, width=2, border_radius=6)

        # Corner Rivets for Input Frame
        for ix, iy in [
            (input_box_rect.left + 5, input_box_rect.top + 5),
            (input_box_rect.right - 5, input_box_rect.top + 5),
            (input_box_rect.left + 5, input_box_rect.bottom - 5),
            (input_box_rect.right - 5, input_box_rect.bottom - 5),
        ]:
            pygame.draw.circle(canvas, BRASS_DARK, (ix, iy), 2)

        # Prompt symbol
        prompt_surf = font_input.render("▶", True, BRASS_LIGHT)
        canvas.blit(prompt_surf, (input_box_rect.left + 12, input_box_rect.top + 12))

        # Render Input Text or Placeholder
        text_x = input_box_rect.left + 32
        text_y = input_box_rect.top + 13
        if input_text:
            rendered_input = font_input.render(input_text, True, TEXT_COLOR)
            # Clip if too long for box
            max_w = input_box_rect.width - 45
            if rendered_input.get_width() > max_w:
                sub_surf = rendered_input.subsurface((rendered_input.get_width() - max_w, 0, max_w, rendered_input.get_height()))
                canvas.blit(sub_surf, (text_x, text_y))
                cursor_x = text_x + max_w + 2
            else:
                canvas.blit(rendered_input, (text_x, text_y))
                cursor_x = text_x + rendered_input.get_width() + 2

            if cursor_visible:
                pygame.draw.line(canvas, BRASS_LIGHT, (cursor_x, text_y + 1), (cursor_x, text_y + 17), 2)
        else:
            placeholder = font_input.render("Type a message to MILO and press Enter...", True, MUTED_BRASS)
            canvas.blit(placeholder, (text_x, text_y))
            if cursor_visible:
                pygame.draw.line(canvas, BRASS_LIGHT, (text_x, text_y + 1), (text_x, text_y + 17), 2)

        # --- Draw Voice Indicator Lamp (Beside Lower Tray) ---
        if is_user_talking:
            glow_radius = int(26 + glow_pulse * 6)
            glow_surf = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            alpha = int(55 + glow_pulse * 40)
            glow_color = (255, 170, 30, alpha)
            pygame.draw.circle(glow_surf, glow_color, (glow_radius, glow_radius), glow_radius)
            canvas.blit(glow_surf, (lamp_center_x - glow_radius, lamp_center_y - glow_radius))

        if is_user_talking and lamp_on_img:
            canvas.blit(lamp_on_img, (lamp_x, lamp_y))
        elif lamp_off_img:
            canvas.blit(lamp_off_img, (lamp_x, lamp_y))

        # --- Footer Line (Recent Message or Shortcut Hints) ---
        footer_y = 748
        if last_sent_text:
            display_msg = last_sent_text if len(last_sent_text) <= 38 else last_sent_text[:35] + "..."
            last_surf = font_small.render(f"Sent: \"{display_msg}\" | [Ctrl+V] Paste | [Right-Alt] Push-To-Talk | [Esc] Exit", True, (160, 130, 85))
            canvas.blit(last_surf, ((WIDTH - last_surf.get_width()) // 2, footer_y))
        else:
            hint = font_small.render("[Enter] Send Message | [Ctrl+V] Paste | [Right-Alt] Push-To-Talk | [Ctrl +/-] Zoom | [Esc] Exit", True, (140, 115, 80))
            canvas.blit(hint, ((WIDTH - hint.get_width()) // 2, footer_y))

        # --- Smoothscale Virtual Canvas to Fill Window Completely ---
        cur_w, cur_h = screen.get_size()
        if cur_w == WIDTH and cur_h == HEIGHT:
            screen.blit(canvas, (0, 0))
        else:
            aspect_diff = abs((cur_w / cur_h) - (WIDTH / HEIGHT))
            if aspect_diff < 0.05:
                # Aspect ratio is close to native -> stretch to 100% fill window with zero black bars
                scaled = pygame.transform.smoothscale(canvas, (cur_w, cur_h))
                screen.blit(scaled, (0, 0))
            else:
                # Window was dragged to non-standard aspect ratio -> letterbox cleanly
                fit_scale = min(cur_w / WIDTH, cur_h / HEIGHT)
                sw = int(WIDTH * fit_scale)
                sh = int(HEIGHT * fit_scale)
                scaled = pygame.transform.smoothscale(canvas, (sw, sh))
                screen.fill(BLACK)
                screen.blit(scaled, ((cur_w - sw) // 2, (cur_h - sh) // 2))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
