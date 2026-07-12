# Shinonome Mini – A minimal console BMS player

A minimal console BMS player written in Python. It runs in a terminal using `curses` and plays audio via **miniaudio**.

## Features
- Supports **bms / bmson**
- Supports **SP(7keys), DP(14keys)**
- Supports **AUTO PLAY / MIRROR / RANDOM / EASY / HARD** options
- Simple configuration through `settings.toml`
- Minimal dependencies – **miniaudio** for sound playback and **pynput** for modifier key detection
- No network connections, No output files

## Dependencies
- Python 3.10+
- **miniaudio** – tiny cross‑platform audio library (installed via pip)
- **pynput** – library for detecting Shift / Ctrl / Alt keys (installed via pip)
- Standard library modules only (curses, json, re, os)

## Quick Start
```bash
# 1. Create a virtual environment
python3 -m venv venv

# 2. Activate it (Linux/macOS)
source venv/bin/activate
# On Windows use: venv\\Scripts\\activate

# 3. Install the required package
pip3 install miniaudio pynput
```

## Running the game
```bash
python3 main.py path/to/your_chart.bms
```
- The player will launch a curses UI.
- Press **Esc** to quit (configurable via settings).
- If the display looks odd, set the terminal to fullscreen.

## Notes & Caveats
- The UI is terminal‑only; no graphical interface.
- Only a subset of BMS commands are parsed. BMP, BGA and other visual commands are skipped.
- **SCROLL** command is not yet supported. (->future support)
- detect modifier keys (Shift / Ctrl / Alt) with `pynput`
- Long note release detection (`onrelease`) is unavailable on Wayland environments, so that functionality is omitted.
- `settings.toml` allows assigning keys (default: `z s x d …`).
- Hispeed change button default actions have been switched to `keyup`/`keydown` for better responsiveness, and can be customized via the `settings.toml`.
- Works best on Shift‑JIS encoded BMS files.

## Configuration (`settings.toml`)
- **scratch.side** – `"left"` or `"right"`
- **keys** – map each lane and scratches to your preferred keys
- **play_options** – toggle auto‑play, mirror, random, easy mode, etc.
- **judgement** – customize judgement line position and timing offset

## License
- GPLv3

## Acknowledgements
- Thanks deeply to the original [shinonome](https://github.com/kuroclef/shinonome) author.
- Although this is a completely different project, it borrows the core concept, hence the "-mini" suffix.

## future support(after ver1.50)
- SCROLL
- do not playback many-time with single #WAVxx definition
   - "polyphony" section @ bmson
- #BASE (36, 62)
- flac support

## this program doesn't support:
- movie or image (BMP, BGA)
- hidden/sudden
- score/file output
- IR or network connection
- playlists → (planned for a separate program later)
- #RANDOM / #IF → (maybe added later if time permits)
- mine notes → (maybe added later if time permits)
- invisible notes
- mp3, midi
- preview
- pms, 774, gda → (if implemented, prioritize 5‑key/10‑key support, then 9‑key, 4‑key, 6‑key)
- Full long‑note support (sorry i can't...)

## TODO (to be verified later)
- Verify BPM alignment when using bmson (ensure no "-1" bpm offset).
- Check that bmson charts do not produce silent notes.
- do not use global variable
