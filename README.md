# Shinonome Mini – A minimal console BMS player

A minimal console BMS player written in Python. It runs in a terminal using `curses` and plays audio via **miniaudio**.

## Features
- Supports **SP,DP**
- Supports **AUTO PLAY / MIRROR / RANDOM / EASY**
- Simple configuration through `settings.toml`
- Minimal dependencies – only **miniaudio** for sound playback

## Dependencies
- Python 3.10+
- **miniaudio** – tiny cross‑platform audio library (installed via pip)
- Standard library modules only (curses, json, re, os)

## Quick Start
```bash
# 1. Create a virtual environment
python3 -m venv venv

# 2. Activate it (Linux/macOS)
source venv/bin/activate
# On Windows use: venv\Scripts\activate

# 3. Install the required package
pip3 install miniaudio
```

## Running the game
```bash
python3 main.py <path-to-your-bms-file>
```
The player will launch a curses UI. Use the keys defined in `settings.toml` (default: `z s x d …`).

## Configuration (`settings.toml`)
- **scratch.side** – `"left"` or `"right"`
- **keys** – map each lane and scratches to your preferred keys
- **play_options** – toggle auto‑play, mirror, random, easy mode, etc.
- **judgement** – customize judgement line position and timing offset

## Notes & Caveats
- The UI is terminal‑only; no graphical interface.
- Only a subset of BMS commands are currently parsed. BMP (`01`) is kept for BGM, while background layers (BGA) and other visual commands are skipped.
- STOP and BPM‑change commands are marked for future implementation.
- Works best on Shift‑JIS encoded BMS files.

## License
- GPLv3

## Acknowledgements
- Thanks to the original Shinonome author.
