# key_listener.py
"""Utility module to capture keyboard events using pynput.

This version avoids module‑level globals by encapsulating the listener state
inside a :class:`KeyListener` class.  Users can create an instance, start it,
stop it, and poll for key events:

```python
from key_listener import KeyListener

listener = KeyListener()
listener.start()
# ... in your update loop ...
for ev_type, key in listener.get_events():
    ...
listener.stop()
```

Only this module uses ``pynput``; the rest of the codebase remains untouched.
"""

from __future__ import annotations

import threading
import queue
from typing import List, Tuple

from pynput import keyboard


class KeyListener:
    """Encapsulated keyboard listener.

    The class manages its own thread, event queue, and stop signal, so no
    module‑level mutable state is required.  Each instance operates
    independently, which also makes testing easier.
    """

    def __init__(self) -> None:
        self._event_queue: "queue.Queue[Tuple[str, str]]" = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ---------------------------------------------------------------------
    # Internal callbacks used by ``pynput``
    # ---------------------------------------------------------------------
    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Callback for key‑press events; store ``("press", key)``.
        """
        try:
            key_str = key.name if isinstance(key, keyboard.Key) else key.char
        except AttributeError:
            key_str = str(key)
        self._event_queue.put(("press", key_str))

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        """Callback for key‑release events; store ``("release", key)``.
        """
        try:
            key_str = key.name if isinstance(key, keyboard.Key) else key.char
        except AttributeError:
            key_str = str(key)
        self._event_queue.put(("release", key_str))

    # ---------------------------------------------------------------------
    # Public control methods
    # ---------------------------------------------------------------------
    def _run_listener(self) -> None:
        """Thread target that runs the ``pynput`` listener.

        The listener lives inside a ``with`` block so it is automatically
        cleaned up when ``self._stop_event`` is set.
        """
        with keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        ) as _listener:
            self._stop_event.wait()  # Block until ``stop`` signals.
            # Exiting the ``with`` block stops the listener.

    def start(self) -> None:
        """Start the background listener thread.

        Re‑starting an already‑running listener is a no‑op.
        """
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_listener, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the listener to stop and wait for the thread to finish.
        """
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def get_events(self) -> List[Tuple[str, str]]:
        """Retrieve and clear all queued key events.

        Returns:
            List of ``(event_type, key)`` tuples where ``event_type`` is
            ``"press"`` or ``"release"``.
        """
        events: List[Tuple[str, str]] = []
        while not self._event_queue.empty():
            try:
                events.append(self._event_queue.get_nowait())
            except queue.Empty:
                break
        return events


# A convenience singleton instance for simple scripts.
# Users who prefer a function‑based API can import ``default_listener``.
default_listener = KeyListener()

def start_key_listener() -> None:
    """Start the module‑level default listener.

    This mirrors the original API while keeping globals confined to a single
    object.
    """
    default_listener.start()

def stop_key_listener() -> None:
    """Stop the module‑level default listener."""
    default_listener.stop()

def get_key_events() -> List[Tuple[str, str]]:
    """Get events from the module‑level default listener."""
    return default_listener.get_events()
