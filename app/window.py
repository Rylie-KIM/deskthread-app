"""DeskThread in its own Mac window, with no browser: `python -B -m app.window`.

The window is a plain macOS window holding the system's own web view (WebKit), driven from
Python through pyobjc. It shows the same page the backend serves on 127.0.0.1. The web view
uses a non-persistent data store, so it keeps no history, cache or cookies on disk.

Closing the window ends the session: sources are revoked, memory is cleared, the model is
unloaded and both programs stop.
"""

import json
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

from AppKit import (  # noqa: E402
    NSApplication,
    NSApplicationActivationPolicyRegular,
    NSBackingStoreBuffered,
    NSImage,
    NSMakeRect,
    NSMenu,
    NSMenuItem,
    NSObject,
    NSOpenPanel,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskResizable,
    NSWindowStyleMaskTitled,
)
from Foundation import NSURL, NSBundle, NSURLRequest  # noqa: E402
from PyObjCTools import MachSignals  # noqa: E402
from WebKit import WKWebsiteDataStore, WKWebView, WKWebViewConfiguration  # noqa: E402

from app.__main__ import REPO, Launch, prepare  # noqa: E402

ICON = REPO / "DeskThread.app" / "Contents" / "Resources" / "DeskThread.icns"
NAME = "DeskThread"


def end_session(launch: Launch) -> None:
    """What closing the window does. Safe to call more than once."""
    session = launch.runtime.session
    if session is not None:
        session.broker.revoke_all()
        session.assistant.forget()
    launch.stop_model()
    launch.web.should_exit = True


def serve(launch: Launch) -> threading.Thread:
    """Run the backend beside the window and wait until it answers."""
    thread = threading.Thread(target=launch.web.run, name="backend", daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    while not launch.web.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    return thread


class AppDelegate(NSObject):
    launch: Launch | None = None

    def applicationShouldTerminateAfterLastWindowClosed_(self, _app: Any) -> bool:
        return True

    def applicationWillTerminate_(self, _note: Any) -> None:
        if self.launch is not None:
            end_session(self.launch)


def _menu() -> Any:
    """A minimal menu bar: Quit, and Edit so copy and paste work in the question box."""
    bar = NSMenu.alloc().init()
    app_item, edit_item = NSMenuItem.alloc().init(), NSMenuItem.alloc().init()
    bar.addItem_(app_item)
    bar.addItem_(edit_item)
    app_menu = NSMenu.alloc().initWithTitle_(NAME)
    app_menu.addItemWithTitle_action_keyEquivalent_(f"Hide {NAME}", "hide:", "h")
    app_menu.addItemWithTitle_action_keyEquivalent_(
        f"End session and quit {NAME}", "terminate:", "q"
    )
    app_item.setSubmenu_(app_menu)
    edit_menu = NSMenu.alloc().initWithTitle_("Edit")
    for title, action, key in (
        ("Undo", "undo:", "z"),
        ("Cut", "cut:", "x"),
        ("Copy", "copy:", "c"),
        ("Paste", "paste:", "v"),
        ("Select All", "selectAll:", "a"),
    ):
        edit_menu.addItemWithTitle_action_keyEquivalent_(title, action, key)
    edit_item.setSubmenu_(edit_menu)
    return bar


class Bridge(NSObject):
    """Receives the three requests the page can make of the window: "choose-folder" (show the
    Mac's own folder panel), and after a session has ended "restart" (a new session in this
    window) and "quit". Nothing else is accepted."""

    on_restart: Any = None
    on_choose: Any = None

    def userContentController_didReceiveScriptMessage_(
        self, _controller: Any, message: Any
    ) -> None:
        request = str(message.body())
        if request == "quit":
            NSApplication.sharedApplication().terminate_(None)
        elif request == "restart" and self.on_restart is not None:
            self.on_restart()
        elif request == "choose-folder" and self.on_choose is not None:
            self.on_choose()


class Window:
    """The app, its one window and the web view inside it."""

    def __init__(self, launch: Launch, backend: threading.Thread) -> None:
        self.launch, self.backend = launch, backend
        self.delegate = AppDelegate.alloc().init()
        self.delegate.launch = launch
        self.bridge = Bridge.alloc().init()
        self.bridge.on_restart = self.restart
        self.bridge.on_choose = self.choose_folder
        self.view: Any = None

    def choose_folder(self) -> None:
        """Show the Mac's folder panel and tell the page which folder was picked. Picking a
        folder here is the user's own act; the page then asks the backend to use it."""
        panel = NSOpenPanel.openPanel()
        panel.setCanChooseDirectories_(True)
        panel.setCanChooseFiles_(False)
        panel.setAllowsMultipleSelection_(False)
        panel.setPrompt_("Choose")
        panel.setMessage_("Choose the folder DeskThread may read")
        picked = panel.URLs()[0].path() if panel.runModal() == 1 and panel.URLs() else ""
        script = f"window.deskthreadFolder && window.deskthreadFolder({json.dumps(str(picked))})"
        self.view.evaluateJavaScript_completionHandler_(script, None)

    def restart(self) -> None:
        """Start a new session in the same window: new programs, new secret address."""
        end_session(self.launch)  # the old session is already over; this makes sure
        self.backend.join(timeout=10)
        launch = prepare()
        if launch is None:
            return
        self.launch, self.backend = launch, serve(launch)
        self.delegate.launch = launch
        self.view.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(launch.address)))

    def run(self) -> None:
        """Create the app, the window and the web view, and run until the window closes."""
        bundle = NSBundle.mainBundle()
        info = bundle.localizedInfoDictionary() or bundle.infoDictionary()
        if info is not None:
            info["CFBundleName"] = NAME  # the name in the menu bar, instead of "Python"
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        app.setDelegate_(self.delegate)
        app.setMainMenu_(_menu())
        if ICON.is_file():
            app.setApplicationIconImage_(NSImage.alloc().initWithContentsOfFile_(str(ICON)))

        config = WKWebViewConfiguration.alloc().init()
        # Nothing the page does is kept on disk: no history, no cache, no cookies.
        config.setWebsiteDataStore_(WKWebsiteDataStore.nonPersistentDataStore())
        config.userContentController().addScriptMessageHandler_name_(self.bridge, "deskthread")
        style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskMiniaturizable
            | NSWindowStyleMaskResizable
        )
        window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, 1280, 860), style, NSBackingStoreBuffered, False
        )
        window.setTitle_(NAME)
        window.setReleasedWhenClosed_(False)
        window.setMinSize_((760, 560))
        self.view = WKWebView.alloc().initWithFrame_configuration_(
            window.contentView().bounds(), config
        )
        self.view.setAutoresizingMask_(18)  # width and height follow the window
        window.setContentView_(self.view)
        address = NSURL.URLWithString_(self.launch.address)
        self.view.loadRequest_(NSURLRequest.requestWithURL_(address))
        # Ctrl+C or a plain `kill` also ends the session cleanly instead of leaving programs behind.
        for number in (signal.SIGINT, signal.SIGTERM):
            MachSignals.signal(number, lambda _signal: app.terminate_(None))
        window.center()
        window.makeKeyAndOrderFront_(None)
        app.activateIgnoringOtherApps_(True)
        app.run()


def main() -> int:
    launch = prepare()
    if launch is None:
        print("The local model server did not start. Is Ollama installed (brew install ollama)?")
        return 2
    if not (Path(REPO) / "ui" / "out" / "index.html").is_file():
        launch.stop_model()
        print("The page is not built yet (ui/out is missing): run `make ui` once.")
        return 2
    window = Window(launch, serve(launch))
    try:
        window.run()
    finally:
        end_session(window.launch)
        window.backend.join(timeout=10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
