"""Exercise the real bundled Tk UI and reminder delivery on a Windows runner."""
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
    def check(condition, name):
        if not condition:
            raise AssertionError(name)
        checks.append(name)
    def finish(error=None):
        (output / "report.json").write_text(json.dumps({"ok":error is None,"checks":checks,"error":error},ensure_ascii=False,indent=2),encoding="utf-8")
        app.quit()
    def guard(fn):
        def wrapped():
            try: fn()
            except Exception:
                finish(traceback.format_exc())
        return wrapped
    def screenshot(name):
        from PIL import ImageGrab
        ui.root.update_idletasks()
        ImageGrab.grab().save(output / name)
    def setup():
        check(ui.root.winfo_viewable(),"assistant opens")
        ui.new_button.invoke()
        ui.edit_title.set("Windows reminder smoke")
        ui.edit_due.set(datetime.fromtimestamp(time.time()+600).strftime("%Y-%m-%d %H:%M"))
        ui.save_button.invoke()
        check(len(app.reminders.list("scheduled"))==1,"create through editor")
        item=app.reminders.list("scheduled")[0]
        ui.edit(item)
        ui.edit_title.set("Edited reminder")
        ui.save_button.invoke()
        check(app.reminders.items[0]["title"]=="Edited reminder","edit through editor")
        ui.navigate("personal")
        ui.entries["assistantName"].set("Yukio Test")
        ui.entries["assistantUserName"].set("Tester")
        app.settings.set("assistantReminderSound",False)
        from .settings import Settings
        restored=Settings(app.settings.path)
        check(restored.get("assistantName")=="Yukio Test" and restored.get("assistantUserName")=="Tester","personalization survives reload")
        ui.navigate("settings")
        app.set_hidden(True)
        check(app.pet_hidden,"hide pet")
        app.set_hidden(False)
        check(not app.pet_hidden,"show pet")
        ui.navigate("extensions")
        screenshot("extensions.png")
        ui.navigate("reminders")
        screenshot("reminders.png")
        item=app.reminders.items[0]
        check(app.reminders.save(item["title"],time.time()+2,item["id"]),"schedule near-term delivery")
        ui.root.withdraw()
        ui.root.after(4500,guard(delivered))
    def delivered():
        check(not ui.root.winfo_viewable(),"main window stays closed")
        check(len(app.reminders.list("ringing"))==1,"timer rings with main window closed")
        check(ui.delivery is not None and ui.delivery.winfo_viewable(),"delivery panel is visible")
        screenshot("delivery.png")
        rid=app.reminders.items[0]["id"]
        ui.act("snooze",rid)
        check(app.reminders.items[0]["status"]=="scheduled" and app.reminders.due_at(app.reminders.items[0])>time.time()+290,"snooze five minutes")
        check(ui.delivery is None,"snooze hides delivery")
        check(app.reminders.save("Confirm me",time.time()+1,rid),"reschedule")
        ui.root.after(2500,guard(complete))
    def complete():
        check(len(app.reminders.list("ringing"))==1,"reminder fires again")
        rid=app.reminders.items[0]["id"]
        ui.act("complete",rid)
        check(len(app.reminders.list("completed"))==1 and ui.delivery is None,"complete dismisses delivery")
        from .reminders import ReminderStore
        check(len(ReminderStore(app.reminders.path).list("completed"))==1,"completion persists")
        ui.act("remove",rid)
        check(not ReminderStore(app.reminders.path).items,"deletion persists")
        app.show_assistant()
        ui.navigate("home")
        check(ui.root.winfo_viewable(),"reopen after close")
        screenshot("home.png")
        finish()
    ui.root.after(500,guard(setup))
    ui.root.after(45000,lambda:finish("Assistant smoke timed out"))
