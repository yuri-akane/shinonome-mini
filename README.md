# Shinonome Mini – A minimal console BMS player

A minimal console BMS player written in Python. It runs in a terminal using `curses` and plays audio via **miniaudio**.

## Features
- Supports **SP, DP**
- Supports **AUTO PLAY / MIRROR / RANDOM / EASY** options
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
python3 main.py <path-to-your-bms-file>
```
The player will launch a curses UI.

## Notes & Caveats
- The UI is terminal‑only; no graphical interface.
- Only a subset of BMS commands are parsed. BMP, BGA and other visual commands are skipped.
- **SCROLL** command is not yet supported. (->future support)
- detect modifier keys (Shift / Ctrl / Alt) with `pynput`
- Long note release detection (`onrelease`) is unavailable on Wayland environments, so that functionality is omitted.
- `settings.toml` allow assigning keys (default: `z s x d …`).
- Hispeed change button default actions have been switched to `keyup`/`keydown` for better responsiveness, and can be customized via the `settings.toml`.
- Works best on Shift‑JIS encoded BMS files.
- bmson format is not yet supported. (->future support)

## Configuration (`settings.toml`)
- **scratch.side** – `"left"` or `"right"`
- **keys** – map each lane and scratches to your preferred keys
- **play_options** – toggle auto‑play, mirror, random, easy mode, etc.
- **judgement** – customize judgement line position and timing offset

## License
- GPLv3

## Acknowledgements
- Thanks deeply to the original [shinonome](https://github.com/kuroclef/shinonome) author.
- 全く別物になっていますが、基本コンセプトをお借りしているので-miniとさせていただきました。

## future support(ver2.0)
- bmson
- better longnote support and allow Shift / Ctrl / Alt
   - using pynput

## future support(after ver2.0)
- SCROLL
- STOP (partially done, but buggy at some bms...)
- do not playback many-time with single #WAVxx definition
- do not use global variable
- #BASE（36,62）
- flac support

## this program doesn't support:
- movie or image (BMP, BGA)
- hidden/sudden
- score/file output
- IR or network connection
- playlists -> ※別のプログラムであとでやる
- #RANDOM - #IF ->余裕ができたらやるかも？
- mine notes ->余裕ができたらやるかも？
- invisible notes
- mp3, midi
- pms, 774, gda ->pmsくらいはやるかも…？
