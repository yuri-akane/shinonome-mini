# control.py - modular handling of BPM and measure-length changes for Shinonome-Mini
"""Utility functions for processing control‑type events during playback.

The parser already tags control events with the keys:
* ``bpm`` – a numeric BPM value (float)
* ``measure_mult`` – a multiplier that changes the visual scroll speed and
  the length of future measures.

These functions are deliberately tiny so they can be edited or extended
independently of the main ``Player`` class.  The ``Player`` class now imports
them and calls the appropriate function when it encounters a control event.
"""

from typing import Any


def apply_bpm_change(player: Any, event: dict) -> None:
    """Update the player's BPM and speed‑factor.

    ``event`` is expected to contain a ``bpm`` key with the new BPM value.
    The player's ``initial_bpm`` (the BPM of the first measure) is stored on
    the instance after the chart is loaded, so we can compute a relative speed
    factor that is later used by ``Player.get_speed_factor`` for UI scaling.
    """
    new_bpm = event["bpm"]
    player.current_bpm = new_bpm
    # Update the visual speed factor relative to the song's initial BPM.
    if getattr(player, "initial_bpm", None):
        player.speed_factor = new_bpm / player.initial_bpm


def apply_measure_multiplier(player: Any, event: dict) -> None:
    """Apply a measure‑length multiplier.

    ``event`` carries ``measure_mult`` – the factor by which the length of the
    current measure (and all subsequent measures) should be stretched or
    compressed.  The player stores this value in ``current_measure_multiplier``
    which is consulted by ``Player.get_speed_factor``.
    """
    player.current_measure_multiplier = event["measure_mult"]


def process_control_event(player: Any, event: dict, auto_play: bool) -> bool:
    """Dispatch a control event.

    Returns ``True`` if the event was handled (i.e. it was a BPM or measure
    change or STOP command).  ``auto_play`` is passed through so the function signature mirrors
    the original inline logic – callers can ignore it if they wish.
    """
    if "bpm" in event:
        apply_bpm_change(player, event)
        return True
    if event.get("channel") == "02" and "measure_mult" in event:
        apply_measure_multiplier(player, event)
        return True
    if "stop" in event or event.get("channel") == "09":
        return True
    return False
