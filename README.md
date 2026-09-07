# Shinonome Mini – A minimal console BMS player

A minimal console BMS player written in Python. It runs in a terminal using `curses` and plays audio via **miniaudio**.

## Features
- Supports **bms / bmson**
- Supports **SP(5,7keys), DP(10,14keys), and 9,4,6keys**
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
- Standard library modules only (curses, json, re, os, and select (or msvcrt))
   - on Windows, pip install `windows-curses`.

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
# pip install windows-curses # windows
```

## Running the game
```bash
python3 cnnm.py path/to/your_chart.bms
```
- The player will launch a curses UI.
- Press **Esc** to quit (configurable via settings).
- If the display looks odd, set the terminal to fullscreen or smaller font-size or use --tiny option.

## playlists
```bash
python3 bmsfd.py
```
- fd-like playlist(music select).
   - independent from other modules. (future support:) can call other bms viewers and players.
- key_up/k: move up, key_down/j: move down, enter: select dir or play bms, backspace: back to parent dir, esc: exit
- "l": list all bms of subdir recursively. (may cause long time wait...）toggle for default view.
- Configure settings.toml and set your bms folders to "allowed_roots".

## menu window (example)
- press key to toggle option, and Enter key to start.
```
Shinonome-Mini -- Minimal Console BMS Player
  Song: ^☆^ さくらなみこのかぜ ^☆^ / Artist: #ねここ14歳(obj:futher)
  Audio ready.

  === PLAY OPTIONS ===
    [A] AUTO PLAY    : ON
    [S] AUTO SCRATCH : OFF
    [M] MIRROR       : OFF
    [R] RANDOM       : OFF
    [E] EASY         : OFF
    [H] HARD GAUGE   : OFF
    [O] SHOW MEASURES: ON
    [keyup/down] HS (Hispeed) : 1.2
    [L] SCRATCH SIDE : LEFT
    [$] SOLID GAUGE  : OFF

  Press key [A/S/M/R/E/H/O/L/$] to toggle option.

  Press [Enter] to START PLAY
  Press [esc] to Quit
```

## game window example (--mini)
- white as [], black as ::, scratch as XX, long note as | , mine as M!(reverse)
   - 9keys: () ^^ && >> OO << && ^^ ()
   - if you want to customize notes, edit constants.py.
```
  Shinonome-Mini -- Minimal Console BMS Player
  Song: ^☆^ さくらなみこのかぜ ^☆^ / Artist: #ねここ14歳(obj:futher)
  BPM: 931.0 | Time: 123.80s | HS: 100.0

    |    |[]  |    |[]  |    |[]  |    |[]  | HARD SOLID: [============----|----]  60.0%
    |    |    |    |    |    |    |    |    |
    |    |    |::  |    |::  |    |::  |    | EX SCORE:     0 /  3240
    |    |[]  |    |[]  |    |[]  |    |[]  | COMBO   :     0  (MAX:     0)
    |    |    |    |    |    |    |    |    |
    |    |    |::  |    |::  |    |::  |    | P:   0 G:   0 g:   0 B:   0 M:   0
    |    |[]  |    |[]  |    |[]  |    |[]  |
    |    |    |    |    |    |    |    |    |
    |    |    |::  |    |::  |    |::  |    |
    |    |[]  |    |[]  |    |[]  |    |[]  |
    |    |    |    |    |    |    |    |    |
    |    |    |::  |    |::  |    |::  |    |
    |    |[]  |    |[]  |    |[]  |    |[]  |
    |    |    |    |    |::  |    |::  |    |
    |    |[]  |    |[]  |    |[]  |    |[]  |
    |    |    |    |    |    |    |    |    |
  * +----+----+FL--+----+----+----+FL--+----+
  /  [S]  [1]  [2]  [3]  [4]  [5]  [6]  [7]
    [       AUTOPLAY MODE ACTIVE       ]

    Press esc to quit playing
```
## result window example (--mini)
```
  +------------------------------------------------+
  |                                                |
  |            S T A G E   F A I L E D             |
  |                                                |
  |          ~  Failed (Gauge: 22.0%)  ~           |
  |                                                |
  |   ---  Results  ---                            |
  |    PERFECT :     0                             |
  |    GREAT   :     0                             |
  |    GOOD    :     0                             |
  |    BAD     :     0                             |
  |    MISS    :     0                             |
  |                                                |
  |    EX SCORE :     0 /  1286                    |
  |    MAX COMBO:     0                            |
  |    MIN GAUGE:  22.0% / MAX GAUGE:  22.0%       |
  |              Press [esc] to Quit               |
  +------------------------------------------------+ 
```

## game window example (--tiny)
- extreme tiny window. notes only and gauge, 8x8 chars at 7keys.
- white as "*", black as ",", scratch as "X", long note as "|" , mine as "!"(reverse)
   - 9keys: o ^ & > o < & ^ o
   - if you want to customize notes, edit constants.py.

```example：Heavenly Door (CHALLENGE : AIR Special)
        |
        |
  * * * |
     ,  |
        |
 X*     *
  !!!!!!!
 ==------
```

## result window example (--tiny)
```
  +------------------+
  |      FAILED      |
  |   GAUGE 22.0%    |
  | P:   0  G:   0   |
  | g:   0  B:   0   |
  | M:   0           |
  | EX:    0/1286    |
  | MAX:   0         |
  |    [esc] Quit    |
  +------------------+
```

## cnnm.py CLI options
```
--soundonly #no display, music only
--nomenu #game start with default settings(settings.toml)
--random, -r
--mirror, -m
--easy, -e
--hard, -h
--auto, -a
--autoscratch, -s
--solid
--mode=4k #force game mode
--mode=5k
--mode=6k
--mode=7k
--mode=9k
--mode=10k
--mode=14k
--mini #default display 
--tiny #extreme tiny display
--none # alias --soundonly
--help
```
## Notes & Caveats
- The UI is terminal‑only; no graphical interface.
- Only a subset of BMS commands are parsed. BMP, BGA and other visual commands are skipped.
- detect modifier keys (Shift / Ctrl / Alt) with `pynput`
- Long note release detection (`onrelease`) is unavailable on Wayland environments, so that functionality is omitted.

## SOLID GAUGE
- init:60%, clear:80%, but more resistant to both increasing and decreasing.
   - both 1/3 (at 70%), so it balances as normal gauge.
- While the HARD gauge reduces the rate of decrease as it nears 0%, the SOLID gauge reduces the rate of increase as it nears 100%.
- Increase Rate: {0%: 2/3, 50%: 1/2, 70%: 1/3, 80%: 1/4, 90%: 1/8, 95%: 1/16, 99%: 1/75} of
normal gauge.
   - more HARD(x0.1-x0.2) when HARD combined, and "init:60%".
- Decrease Rate: Same as HARD gauge when combined; otherwise, 1/3 of normal gauge(poor:-2%, and less(half) with EASY).

## Configuration (`settings.toml`)
- **scratch.side** – `"left"` or `"right"`
- **keys** – map each lane and scratches to your preferred keys (default: `z s x d …`).
- Hispeed change button default actions have been switched to `keyup`/`keydown` for better responsiveness, and can be customized via the `settings.toml`.
- **play_options** – toggle auto‑play, mirror, random, easy mode, etc.
- **judgement** – customize judgement line position and timing offset
- If audio crackles or stutters, try a lower sample rate and nchannels = 1 (monaural) in the `audio` section.
   - also, check numpy installed.
- Default encodings can be set to shift-jis(cp932), euc-kr(cp949), utf-8

## License
- GPLv3

## Acknowledgements
- Thanks deeply to the original [shinonome](https://github.com/kuroclef/shinonome) author.
- Although this is a completely different project, it borrows the core concept, hence the "-mini" suffix.

## future support
- to ver2.00
   - implement bmsfd.py to be able to call other viewers and players
- to ver2.50
   - mixwaver-like
   - minus BPM?

## this program doesn't support:
- movie or image (BMP, BGA)
- hidden/sudden, S-RAN/H-RAN/R-RAN, FLIP(DP), etc
- score/file output
- IR or network connection
- ZZ mine, invisible notes, FREEZONE
- minus BPM, minus SCROLL, gravity, reverse flow
   - minus SCROLL may be done, but not fully tested
- midi
- mp3 may cause delay, same as other players.
- preview
- bmm, 774, n2s, gda, sm, osu and other formats
   - double scratch or foot pedal with each 16-17ch
- Full long‑note support (LN,CN,HCN...sorry i can't...)
- musicbox (old bms)
- #WAVxx as absolute path or parent directory
- #STP, #SPEED, #EXT, #SWITCH, etc
- 18keys, 24keys, 48keys, etc
- more 1000+ measures
- half、skins
   - 5keys "half" against 7keys "separate". use "tiny" display option instead.
- show SLOW/FAST

## TODO (to be verified later)
- Verify bms support that resources (wav, bmp) are divided into subfolders
- Verify longnote support（lnobj, lnmode, ln_type...too complicated）
- Verify BPM alignment when using bmson (ensure no "-1" bpm offset).
- Check that bmson charts do not produce silent notes. (about bmson that doesnot cut WAVs.)
- do not use global variable
- split modules for refactor
- do more tests, do more bms.

## changelog
- ver1.50 basic bms command to play (bpm change, score length change, stop, longnote or so)
- 1.53a #BASE (36, 62)
- 1.53a do not playback many-time with single #WAVxx definition
   - "polyphony" section @ bmson
- 1.53b pynput use or nouse flag by setting
- 1.56 flac support
- 1.57c numpy for less cpu usage
- 1.58 default encoding settings (shift-jis, euc-kr, utf-8)
- 1.59e++ #SCROLL
- 1.60 mine notes
- 1.60 #RANDOM - #IF
- 1.61c 5keys/10keys
- 1.62 9keys(pms), fix #RANDOM
- 1.63 4keys/6keys
- 1.64 cli options
- 1.65 add playlists (bmsfd.py), fix 4keys/6keys ch
- 1.66 rename main.py->cnnm.py, fix playlists with bmson, fix 4keys/6keys mirror/random
- 1.67 bmson measure line
- 1.68 curses error handling, --tiny display option, remove deprecated typing(python 3.9+)
- 1.69 improve --soundonly handling at exit (Ctrl+C(force exit) to Enter key), and improve windows support
- 1.70 improve --tiny window(key press) and handling at result(gameover)
- 1.71 result window, result stdout, gauge increment at autoplay, other error handlings
- 1.72 debug short longnote behavior
- 1.73 ゲージが十分にあってもfailedになる場合があるのを修正（予定）
