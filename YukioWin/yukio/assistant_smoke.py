"""Exercise compact settings in the actual Windows release executable."""
import json
import os
from pathlib import Path
import time
import traceback
from datetime import datetime


def schedule(app, output):
    if not os.environ.get("YUKIO_REMINDER_FILE"):
        raise RuntimeError("Assistant smoke testing requires isolated YUKIO_REMINDER_FILE")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    ui = app.assistant
    checks = []
    startup_test = None
    package_provenance = None
    def check(condition, name):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    def finish(error=None, quit_from_settings=False):
        if startup_test is not None:
            try: startup_test.set_enabled(False)
            except Exception: error = (error or "") + " Startup test cleanup failed"
        (output / "report.json").write_text(json.dumps({"ok":error is None,"checks":checks,"error":error,"packageProvenance":package_provenance},ensure_ascii=False,indent=2),encoding="utf-8")
        if quit_from_settings:
            ui.pet_settings.quit_button.invoke()
        else:
            app.quit()
    def guard(fn):
        def wrapped():
            try: fn()
            except Exception:
                finish(traceback.format_exc())
        return wrapped
    def screenshot(name):
        from PIL import ImageGrab
        ui.root.update()
        import ctypes
        ctypes.windll.dwmapi.DwmFlush()
        target = ui.delivery if name == "delivery.png" else ui.pet_settings.window if name == "settings.png" else ui.root
        x, y = target.winfo_rootx(), target.winfo_rooty()
        shot = ImageGrab.grab(bbox=(x, y, x + target.winfo_width(), y + target.winfo_height()))
        if name == "home.png":
            # A visible native window can still have an unpainted white surface.
            # Require the colored sidebar and its text to have reached the screen.
            pixel = shot.getpixel((8, 8))[:3]
            check(max(abs(a-b) for a,b in zip(pixel,(240,246,241))) < 12,"home sidebar painted")
            check(len(shot.crop((0,0,200,400)).getcolors(1000000)) > 30,"home text painted")
        shot.save(output / name)
    def setup():
        nonlocal startup_test, package_provenance
        import hashlib
        import sys
        provenance_path = Path(sys._MEIPASS) / "build-provenance.json"
        package_provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        for relative, expected in package_provenance["assetSha256"].items():
            actual = hashlib.sha256((Path(app.bundled_assets) / relative).read_bytes()).hexdigest()
            if actual != expected:
                raise AssertionError("Packaged asset mismatch: " + relative)
        checks.append("all bundled assets match packaging provenance")
        check(not ui.root.winfo_viewable(), "standalone assistant stays hidden on launch")
        from .startup import LaunchAtLogin, RegistryBackend
        startup_test = LaunchAtLogin(RegistryBackend("YukioSmoke-" + str(os.getpid())))
        check(startup_test.status == "disabled", "startup initially off")
        app.launch_at_login = startup_test
        ui.root.withdraw()
        app.win32.user32.SendMessageW(app.pet.hwnd, app.win32.WM_RBUTTONUP, 0, 0)
        ui.root.update()
        settings = ui.pet_settings
        check(settings.window.winfo_viewable(), "native pet right-click opens settings")
        check(not ui.root.winfo_viewable(), "right-click keeps main window closed")
        check(bool(settings.window.attributes("-topmost")), "settings stay above other apps")
        app.stop_demo()  # First launch starts a demo; this fixture targets the live router.
        from .events import Kind, PetEvent
        from .app import now_ms
        t = now_ms() - app.router.config.respond_hold_ms - 100
        app.router.ingest(PetEvent(t, 'test', 'lower-sign-smoke', Kind.task_start), t)
        app.router.ingest(PetEvent(t, 'test', 'lower-sign-smoke', Kind.final_answer), t)
        app.router.ingest(PetEvent(t, 'test', 'lower-sign-smoke', Kind.task_end), t)
        app.router.settle(now_ms())
        check(app.router.completed_session == 'lower-sign-smoke', 'completion sign raised before button')
        check(settings.lower_sign_button.winfo_height() >= 64, 'lower sign button has large click target')
        settings.lower_sign_button.invoke()
        check(app.router.completed_session is None, 'settings button lowers completion sign')
        check(not ui.root.winfo_viewable(), 'lowering sign keeps assistant closed')
        settings.lower_sign_button.invoke()
        check(app.router.completed_session is None, 'lower sign is safe when already lowered')
        settings.startup_button.invoke()
        check(startup_test.status == "enabled", "startup checkbox registers current exe")
        check(startup_test.backend.read() == startup_test.command, "startup command points to packaged exe")
        settings.startup_button.invoke()
        check(startup_test.status == "disabled", "startup checkbox removes registration")
        screenshot("settings.png")
        check(not hasattr(settings, "open_button"), "settings have no standalone App entry")
        app.show_assistant()
        check(not ui.root.winfo_viewable(), "legacy assistant action stays disabled")
        app._on_control_message(app.control.show_menu_message, 0, 0)
        ui.root.update()
        check(settings.window.winfo_viewable(), "reopening app shows compact settings")
        check(not ui.root.winfo_viewable(), "reopening app keeps standalone page hidden")
        check(bool(settings.outside_click.hook), "outside click hook installed in packaged exe")
        click_at(settings.lower_sign_button.winfo_rootx() + 20,
                 settings.lower_sign_button.winfo_rooty() + 20)
        ui.root.after(250, guard(inside_clicked))
    def click_at(x, y):
        import ctypes
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
        ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
    def inside_clicked():
        settings = ui.pet_settings
        check(settings.window.winfo_viewable(), "clicking inside settings keeps it open")
        # A separate native top-level window is an unambiguous outside target.
        import tkinter as tk
        ui.smoke_outside = tk.Toplevel(ui.root)
        ui.smoke_outside.geometry('100x80+0+0')
        ui.smoke_outside.attributes('-topmost', True)
        ui.root.update_idletasks()
        click_at(ui.smoke_outside.winfo_rootx() + 20, ui.smoke_outside.winfo_rooty() + 20)
        ui.root.after(250, guard(outside_clicked))
    def outside_clicked():
        settings = ui.pet_settings
        check(not settings.window.winfo_viewable(), "clicking outside hides settings")
        check(settings.outside_click.hook is None, "outside click hook released after hiding")
        ui.smoke_outside.destroy()
        app.win32.user32.SendMessageW(app.pet.hwnd, app.win32.WM_RBUTTONUP, 0, 0)
        ui.root.update()
        check(settings.window.winfo_viewable(), "right-click reopens settings after outside dismissal")
        check(bool(settings.outside_click.hook), "outside click hook reinstalled on reopen")
        button = settings.quit_button
        check(button.winfo_viewable(), "quit button visible in right-click settings")
        check(button.winfo_rooty() + button.winfo_height() <= settings.window.winfo_rooty() + settings.window.winfo_height(), "quit button fits inside settings")
        verify_skin_drag()
    def verify_skin_drag():
        from .settings import Settings
        from .app import now_ms
        settings = ui.pet_settings
        original_position = (app.pet.x, app.pet.y)
        original_state = app.shown_state
        for index, skin in ((1, "qianxia"), (0, "yukio"), (1, "qianxia")):
            settings.skin_picker.current(index)
            settings.skin_picker.event_generate("<<ComboboxSelected>>")
            ui.root.update()
            check(app.skin == skin, "settings selects " + skin)
            check(Settings(app.settings.path).get("skin") == skin, "selection persists: " + skin)
            check((app.pet.x, app.pet.y) == original_position, "skin switch preserves position: " + skin)
            check(app.shown_state == original_state, "skin switch preserves activity: " + skin)
        screenshot("settings.png")
        settings.window.withdraw()
        app.set_hide_when_idle(False)
        app.pet.move(400, 250)
        app._painted = None
        app._render(now_ms())
        # Drive the actual native window procedure and capture its rendered held pose.
        w = app.win32
        w.user32.SetCursorPos(490, 310)
        w.user32.SendMessageW(app.pet.hwnd, w.WM_LBUTTONDOWN, 1, 0)
        w.user32.SetCursorPos(520, 335)
        w.user32.SendMessageW(app.pet.hwnd, w.WM_MOUSEMOVE, 1, 0)
        check(app.swing is not None and app.hang_geo is not None, "native drag starts Qianxia held pose")
        check(app.held_spec.frame_height == 248, "Qianxia standing pose selected")
        ui.root.after(250, guard(held_visible))
    def held_visible():
        import ctypes
        from PIL import ImageGrab
        w = app.win32
        ctypes.windll.dwmapi.DwmFlush()
        x, y = app.pet.x, app.pet.y
        width, height = app.hang_geo.panel_size
        ImageGrab.grab(bbox=(x, y, x + width, y + height)).save(output / "qianxia-held.png")
        w.user32.SendMessageW(app.pet.hwnd, w.WM_LBUTTONUP, 0, 0)
        check(app._released_at is not None, "native release starts settling")
        ui.root.after(3000, guard(settled))
    def settled():
        check(app.swing is None and app.hang_geo is None, "release restores activity after settling")
        check((app.pet.x, app.pet.y) == (430, 275), "drag restores exact release position")
        check((app.settings.get("originX"), app.settings.get("originY")) == (430, 275), "release position persists")
        app.win32.user32.SendMessageW(app.pet.hwnd, app.win32.WM_RBUTTONUP, 0, 0)
        ui.root.update()
        checks.append("exit requested through settings quit button")
        finish(quit_from_settings=True)
    ui.root.after(500,guard(setup))
    ui.root.after(45000,lambda:finish("Assistant smoke timed out"))
