# Shinonome Mini – A minimal console BMS player

A minimal console BMS player written in Python. It runs in a terminal using `curses` and plays audio via **miniaudio**.

## Features
- Supports **bms / bmson**
- Supports **SP(7keys), DP(14keys)**
- Supports **AUTO PLAY / MIRROR / RANDOM / EASY / HARD** options
- Simple configuration through `settings.toml`
- Minimal dependencies – **miniaudio** for sound playback and optional **pynput** and **numpy**
- No network connections, No output files
- "SOLID" gauge option: init 60%, but more harder gauge

## Dependencies
- Python 3.10+
- **miniaudio** – tiny cross‑platform audio library
- **pynput**(optional) – library for detecting Shift / Ctrl / Alt keys
- **numpy**(optional) – for less cpu usage 
- Standard library modules only (curses, json, re, os)

## Quick Start
```bash
# 1. Create a virtual environment
python3 -m venv venv

# 2. Activate it (Linux/macOS)
source venv/bin/activate
# On Windows use: venv\\Scripts\\activate

# 3. Install the required package
pip3 install miniaudio pynput numpy
# pkg install python-numpy # termux or so
```

## Running the game
```bash
python3 main.py path/to/your_chart.bms
```
- The player will launch a curses UI.
- Press **Esc** to quit (configurable via settings).
- If the display looks odd, set the terminal to fullscreen or smaller font-size.

## Notes & Caveats
- The UI is terminal‑only; no graphical interface.
- Only a subset of BMS commands are parsed. BMP, BGA and other visual commands are skipped.
- **SCROLL** command is not yet supported. (->future support)
- detect modifier keys (Shift / Ctrl / Alt) with `pynput`
- Long note release detection (`onrelease`) is unavailable on Wayland environments, so that functionality is omitted.

## SOLID GAUGE
- init:60%, clear:80%, but more resistant to both increasing and decreasing.
- While the HARD gauge reduces the rate of decrease as it nears 0%, the SOLID gauge reduces the rate of increase as it nears 100%.
- Increase Rate: {0%: 2/3, 50%: 1/2, 70%: 1/3, 80%: 1/4, 90%: 1/8, 95%: 1/16, 99%: 1/75} of
normal gauge.
- Decrease Rate: Same as HARD gauge when combined; otherwise, 1/3 of normal gauge(poor:-2%).

## Configuration (`settings.toml`)
- **scratch.side** – `"left"` or `"right"`
- **keys** – map each lane and scratches to your preferred keys (default: `z s x d …`).
- Hispeed change button default actions have been switched to `keyup`/`keydown` for better responsiveness, and can be customized via the `settings.toml`.
- **play_options** – toggle auto‑play, mirror, random, easy mode, etc.
- **judgement** – customize judgement line position and timing offset
- If audio crackles or stutters, try a lower sample rate and nchannels = 1 (monaural) in the `audio` section.
- Default encodings can be set to shift-jis(cp932), euc-kr(cp949), utf-8

## License
- GPLv3

## Acknowledgements
- Thanks deeply to the original [shinonome](https://github.com/kuroclef/shinonome) author.
- Although this is a completely different project, it borrows the core concept, hence the "-mini" suffix.

## history and future support
- basic bms command to play (bpm change or so) -> ver1.50
- SCROLL
- do not playback many-time with single #WAVxx definition
   - "polyphony" section @ bmson ->1.53a ok
- #BASE (36, 62)　->1.53a ok
- flac support　->1.56 ok?
- pynput use or nouse flag by setting　->1.53b ok
- display (none, tiny, mini) option, cmdline option
- default encoding settings (shift-jis, euc-kr, utf-8) ->1.58 ok
- numpy for less cpu usage ->1.57c ok

## this program doesn't support:
- movie or image (BMP, BGA)
- hidden/sudden
- score/file output
- IR or network connection
- playlists → (planned for a separate program later)
- #RANDOM / #IF → (maybe added later if time permits)
- mine notes → (maybe added later if time permits)
- ZZ mine, invisible notes, FREEZONE
- midi
- mp3 may cause delay, same as other player.
- preview
- pms, 774, gda → (if implemented, prioritize 5‑key/10‑key support, then 9‑key, 4‑key, 6‑key)
- Full long‑note support (sorry i can't...)

## TODO (to be verified later)
- Verify BPM alignment when using bmson (ensure no "-1" bpm offset).
- Check that bmson charts do not produce silent notes.
- do not use global variable
