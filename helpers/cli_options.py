import sys
import argparse

VALID_MODES = {'4K', '5K', '6K', '7K', '9K', '10K', '14K'}

def _normalize_mode(raw: str) -> str:
    """--mode / --mode-hint の値を内部形式（'7K'等）に正規化する。

    Examples:
        'beat-7k'  -> '7K'
        '7k'       -> '7K'
        'beat-14k' -> '14K'
    """
    s = raw.strip().lower()
    # bmson 互換形式: beat-Xk
    if s.startswith('beat-'):
        s = s[len('beat-'):]
    # '4k' -> '4K' 形式
    if s.endswith('k'):
        return s[:-1].upper() + 'K'
    return s.upper()

def _add_on_off_argument(parser, flag, dest, help_text):
    parser.add_argument(*flag,
                        dest=dest,
                        nargs='?',
                        const='on', #on/offの指定がないが-a/--auto等はあるとき：on
                        default=argparse.SUPPRESS,
                        choices=['on','off'],
                        help=help_text)

def _add_disp_argument(disp, flag, dest, help_text):
    disp.add_argument(flag, dest=dest, action='store_true', help=help_text)

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns
    -------
    argparse.Namespace
        Parsed arguments.  Key attributes:

        bmsfile (str|None)      : path to the BMS/bmson file
        autoplay (bool)         : --auto / -a
        mirror (bool)           : --mirror / -m
        random (bool)           : --random / -r
        easy (bool)             : --easy / -e
        hard (bool)             : --hard / -h
        solid (bool)            : --solid
        autoscratch (bool)      : --autoscratch / -s
        display_mode (str)      : 'mini' | 'tiny' | 'mw' | 'soundonly'  (default 'mini')
        nomenu (bool)           : --nomenu
        force_mode (str|None)   : normalized game mode string, e.g. '7K'
    """
    parser = argparse.ArgumentParser(
        description='Shinonome-Mini -- Minimal Console BMS Player',
        add_help=False,  # -h を --hard に割り当てるためデフォルトの -h/--help を無効化
    )
    parser.add_argument('--help', action='help', default=argparse.SUPPRESS,
                        help='Show this help message and exit')

    # Positional: BMS file (optional so that the player can still show usage)
    parser.add_argument(
        'bmsfile',
        nargs='?',
        default=None,
        metavar='FILE',
        help='Path to a BMS/bmson file',
    )

    # --- Play option flags ---
    _add_on_off_argument(parser, ('-a', '--auto'), 'autoplay', 'Force AUTO PLAY on/off')
    _add_on_off_argument(parser, ('-m', '--mirror'), 'mirror', 'Force MIRROR on/off')
    _add_on_off_argument(parser, ('-r', '--random'), 'random', 'Force RANDOM on/off')
    _add_on_off_argument(parser, ('-e', '--easy'), 'easy', 'Force EASY gauge on/off')
    _add_on_off_argument(parser, ('-h', '--hard'), 'hard', 'Force HARD gauge on/off')
    _add_on_off_argument(parser, ('--solid',), 'solid', 'Force SOLID gauge on/off')
    _add_on_off_argument(parser, ('-s', '--autoscratch'), 'autoscratch', 'Force AUTO SCRATCH on/off')
    _add_on_off_argument(parser, ('--show-result',), 'show_result', 'Force show result screen on/off')
    _add_on_off_argument(parser, ('--stats',), 'stats', 'Output performance stats to stdout upon song completion')

    # --- Display mode (mutually exclusive) ---
    disp = parser.add_mutually_exclusive_group()
    _add_disp_argument(disp, '--soundonly', 'soundonly', 'Audio-only mode (no UI, forces autoplay)')
    _add_disp_argument(disp, '--none', 'none', 'No UI mode (same as --soundonly)')
    _add_disp_argument(disp, '--tiny', 'tiny', 'Tiny display mode (1-char width, minimal UI)')
    _add_disp_argument(disp, '--mw',   'mw',   'MixWaver display mode (horizontal play UI)')
    _add_disp_argument(disp, '--scan', 'scan', 'MixWaver display mode (horizontal play UI, same as --mw)')
    _add_disp_argument(disp, '--mini', 'mini', 'Normal display mode (default)')

    # --- Menu control ---
    parser.add_argument('--nomenu', dest='nomenu', action='store_true', help='Skip menu and start playing immediately')

    # --- Game mode override ---
    # Both --mode-hint=beat-7k (bmson-compatible) and --mode=7k (shorthand) are supported.
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        '--mode-hint',
        dest='mode_hint',
        metavar='HINT',
        default=None,
        help='Game mode hint (bmson-compatible, e.g. beat-7k)',
    )
    mode_group.add_argument(
        '--mode',
        dest='mode',
        metavar='MODE',
        default=None,
        help='Game mode override (e.g. 7k, 14k)',
    )

    args = parser.parse_args()

    #存在するときだけboolに直す。存在しない時は何もしない（紛らわしいので定義もしないようにする）
    #if hasattr(...):...をandで縮約
    hasattr(args, "autoplay") and setattr(args, 'autoplay', args.autoplay == 'on')
    hasattr(args, "random")   and setattr(args, 'random',   args.random == 'on')
    hasattr(args, "mirror")   and setattr(args, 'mirror',   args.mirror == 'on')
    hasattr(args, "easy")     and setattr(args, 'easy',     args.easy == 'on')
    hasattr(args, "hard")     and setattr(args, 'hard',     args.hard == 'on')
    hasattr(args, "solid")    and setattr(args, 'solid',    args.solid == 'on')
    hasattr(args, "autoscratch") and setattr(args, 'autoscratch', args.autoscratch == 'on')
    hasattr(args, "show_result") and setattr(args, 'show_result', args.show_result == 'on')
    hasattr(args, "stats")    and setattr(args, 'stats',    args.stats == 'on')

    # Derive display_mode string
    if args.soundonly or args.none:
        args.display_mode = 'soundonly'
        args.cli_display_mode_set = True
    elif args.tiny:
        args.display_mode = 'tiny'
        args.cli_display_mode_set = True
    elif args.mw or args.scan:
        args.display_mode = 'mw'
        args.cli_display_mode_set = True
    elif args.mini:
        args.display_mode = 'mini'
        args.cli_display_mode_set = True
    else:
        args.display_mode = None
        args.cli_display_mode_set = False


    # Derive force_mode
    raw_mode = args.mode_hint or args.mode
    if raw_mode:
        normalized = _normalize_mode(raw_mode)
        if normalized in VALID_MODES:
            args.force_mode = normalized
        else:
            print(f"Warning: Unknown mode '{raw_mode}', ignoring --mode / --mode-hint", file=sys.stderr)
            args.force_mode = None
    else:
        args.force_mode = None

    # soundonly / none implies autoplay
    if args.display_mode in ('soundonly', 'none'):
        args.autoplay = True

    return args
