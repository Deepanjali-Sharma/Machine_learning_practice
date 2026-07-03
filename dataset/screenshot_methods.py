#!/usr/bin/env python3
"""
Screenshot Method Tester
Tries each bypass method and reports what works on your system.
Output saved to ~/Pictures/ss_test/
"""

import os
import sys
import subprocess
import shutil

OUTPUT_DIR = os.path.expanduser("~/Pictures/ss_test")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def ok(msg):  print(f"  ✓  {msg}")
def fail(msg): print(f"  ✗  {msg}")
def info(msg): print(f"  ·  {msg}")


# ─────────────────────────────────────────────
# Environment detection
# ─────────────────────────────────────────────

def detect_environment():
    print("\n══ Environment ═══════════════════════════")
    session = os.environ.get("XDG_SESSION_TYPE", "unknown")
    display = os.environ.get("DISPLAY", None)
    wayland = os.environ.get("WAYLAND_DISPLAY", None)
    info(f"Session type    : {session}")
    info(f"DISPLAY         : {display or 'not set'}")
    info(f"WAYLAND_DISPLAY : {wayland or 'not set'}")
    return session


# ─────────────────────────────────────────────
# Method 1 — Xlib direct  (X11 only)
# ─────────────────────────────────────────────

def method_xlib():
    print("\n══ Method 1 — Xlib direct (X11 only) ════")
    try:
        from Xlib import display as xdisplay, X
        from PIL import Image

        d = xdisplay.Display()
        root = d.screen().root
        geom = root.get_geometry()
        w, h = geom.width, geom.height
        info(f"Connected — screen {w}x{h}")

        raw = root.get_image(0, 0, w, h, X.ZPixmap, 0xFFFFFFFF)
        img = Image.frombytes("RGBX", (w, h), raw.data, "raw", "BGRX").convert("RGB")

        out = f"{OUTPUT_DIR}/xlib.png"
        img.save(out)
        ok(f"Saved → {out}")

    except ImportError as e:
        fail(f"Missing dependency: {e}")
        info("Fix: pip install python-xlib pillow")
    except Exception as e:
        fail(f"{e}")


# ─────────────────────────────────────────────
# Method 2 — CLI tools
# ─────────────────────────────────────────────

def method_cli_tools():
    print("\n══ Method 2 — CLI tools ══════════════════")
    tools = {
        "scrot":             ["scrot",             f"{OUTPUT_DIR}/scrot.png"],
        "import (ImageMagick)": ["import", "-window", "root", f"{OUTPUT_DIR}/import.png"],
        "gnome-screenshot":  ["gnome-screenshot",  "-f", f"{OUTPUT_DIR}/gnome-screenshot.png"],
        "spectacle":         ["spectacle",         "-b", "-o", f"{OUTPUT_DIR}/spectacle.png"],
        "flameshot":         ["flameshot",         "full", "-p", OUTPUT_DIR],
    }
    for name, cmd in tools.items():
        if not shutil.which(cmd[0]):
            fail(f"{name}: not installed")
            continue
        try:
            result = subprocess.run(cmd, timeout=5, capture_output=True)
            if result.returncode == 0:
                ok(f"{name}: success")
            else:
                stderr = result.stderr.decode().strip()
                fail(f"{name}: exit {result.returncode} — {stderr}")
        except subprocess.TimeoutExpired:
            fail(f"{name}: timed out")
        except Exception as e:
            fail(f"{name}: {e}")


# ─────────────────────────────────────────────
# Method 3 — grim / wlr-screencopy  (wlroots Wayland)
# ─────────────────────────────────────────────

def method_grim():
    print("\n══ Method 3 — grim / wlr-screencopy ═════")
    info("Works on wlroots compositors (Sway, Hyprland) — NOT on GNOME")
    if not shutil.which("grim"):
        fail("grim not installed")
        info("Install: sudo apt install grim   OR   sudo pacman -S grim")
        return
    try:
        out = f"{OUTPUT_DIR}/grim.png"
        result = subprocess.run(["grim", out], timeout=5, capture_output=True)
        if result.returncode == 0:
            ok(f"Saved → {out}")
        else:
            fail(result.stderr.decode().strip())
    except Exception as e:
        fail(str(e))


# ─────────────────────────────────────────────
# Method 4 — /dev/fb0 legacy framebuffer
# ─────────────────────────────────────────────

def method_framebuffer():
    print("\n══ Method 4 — /dev/fb0 legacy framebuffer ")
    fb = "/dev/fb0"
    if not os.path.exists(fb):
        fail("/dev/fb0 not present on this system")
        return
    try:
        with open("/sys/class/graphics/fb0/virtual_size") as f:
            w, h = map(int, f.read().strip().split(","))
        with open("/sys/class/graphics/fb0/bits_per_pixel") as f:
            bpp = int(f.read().strip())
        info(f"Framebuffer: {w}x{h} @ {bpp}bpp")

        size = w * h * (bpp // 8)
        with open(fb, "rb") as f:
            data = f.read(size)

        from PIL import Image
        fmt_map = {32: ("RGBA", "BGRA"), 16: ("RGB", "BGR;16")}
        if bpp not in fmt_map:
            fail(f"Unsupported bpp: {bpp}")
            return

        mode, raw_mode = fmt_map[bpp]
        img = Image.frombytes(mode, (w, h), data, "raw", raw_mode).convert("RGB")
        out = f"{OUTPUT_DIR}/framebuffer.png"
        img.save(out)
        ok(f"Saved → {out}")

    except PermissionError:
        fail("Permission denied")
        info("Fix: sudo usermod -aG video $USER  (then re-login)")
    except Exception as e:
        fail(str(e))


# ─────────────────────────────────────────────
# Method 5 — KMS/DRM  (/dev/dri/)
# ─────────────────────────────────────────────

def method_drm():
    print("\n══ Method 5 — KMS/DRM (/dev/dri/) ═══════")
    dri = "/dev/dri"
    if not os.path.exists(dri):
        fail("/dev/dri not found")
        return

    cards = [f for f in os.listdir(dri) if f.startswith("card")]
    info(f"DRI devices: {cards or 'none found'}")

    for card in cards:
        path = f"{dri}/{card}"
        try:
            fd = os.open(path, os.O_RDWR)
            os.close(fd)
            ok(f"{card}: read/write access available")
            info("Raw framebuffer dump needs libdrm ioctls — try: pip install pydrm")
        except PermissionError:
            fail(f"{card}: permission denied — needs root or 'video' group")
        except Exception as e:
            fail(f"{card}: {e}")


# ─────────────────────────────────────────────
# Method 6 — PipeWire
# ─────────────────────────────────────────────

def method_pipewire():
    print("\n══ Method 6 — PipeWire ═══════════════════")
    if not shutil.which("pw-cli"):
        fail("pw-cli not found — PipeWire not installed")
        return

    result = subprocess.run(["pw-cli", "info", "0"], capture_output=True, timeout=3)
    if result.returncode != 0:
        fail("PipeWire daemon not running")
        return

    ok("PipeWire is running")

    # Check for active screencopy nodes in the graph
    if shutil.which("pw-dump"):
        dump = subprocess.run(["pw-dump"], capture_output=True, timeout=3)
        graph = dump.stdout.decode().lower()
        if "screencast" in graph or "screencopy" in graph:
            ok("Screencast node(s) found in PipeWire graph")
        else:
            fail("No active screencast nodes — GNOME requires the portal to initiate a stream")

    info("Direct PipeWire screen capture (no portal) options:")
    info("  - libpipewire Python bindings (not widely packaged)")
    info("  - github.com/SaturnSH2x2/pipewire-screencapture")
    info("  - or call the portal programmatically (like the original script)")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    print("╔══════════════════════════════════════════╗")
    print("║      Screenshot Method Tester            ║")
    print("╚══════════════════════════════════════════╝")

    detect_environment()
    method_xlib()
    method_cli_tools()
    method_grim()
    method_framebuffer()
    method_drm()
    method_pipewire()

    print(f"\n══ Done ══════════════════════════════════")
    print(f"  Output directory: {OUTPUT_DIR}\n")


if __name__ == "__main__":
    main()
