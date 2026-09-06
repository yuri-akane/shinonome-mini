from typing import Any

def detect_mode_from_bms(info: dict[str, Any], used_channels: set[str]) -> str:
    """
    Determine the game mode for a BMS file based on header information and channel usage.
    
    Parameters
    ----------
    info : dict
        Parsed header information from a BMS file.  It may contain a 'forced_mode'
        key that overrides automatic detection, and an optional 'ext_is_pms' flag.
    used_channels : set[str]
        Set of channel identifiers (e.g., "11", "12", ..., "69") that appear in the chart.
    
    Returns
    -------
    str
        One of: '4K', '6K', '9K', '10K', '14K', '7K', or '5K'.
    """
    # Extract flags from info if present; otherwise compute defaults
    forced_mode = info.get("forced_mode")
    ext_is_pms = info.get("ext_is_pms", False)

    # Helper sets for channel detection
    has_scratch = bool(used_channels & {"16", "17", "26", "27", "56", "57", "66", "67", "D6", "D7", "E6", "E7"})
    has_1P_7k = bool(used_channels & {"18", "19", "58", "59", "D8", "D9"})
    has_pms_2p = bool(used_channels & {"22", "23", "24", "25", "62", "63", "64", "65", "E2", "E3", "E4", "E5"})
    has_non_pms_2p = bool(used_channels & {"21", "26", "27", "28", "29", "61", "66", "67", "68", "69", "E1", "E6", "E7", "E8", "E9"})

    if forced_mode:
        return forced_mode
    elif ext_is_pms:
        return "9K"
    elif has_pms_2p and not has_scratch and not has_non_pms_2p and not has_1P_7k:
        return "9K"
    elif has_pms_2p or has_non_pms_2p:
        has_2P_7k = bool(used_channels & {"28", "29", "68", "69", "E8", "E9"})
        return "14K" if (has_1P_7k or has_2P_7k) else "10K"
    else:
        return "7K" if has_1P_7k else "5K"


def detect_mode_from_bmson(raw_mode_hint: str, used_x: set[int], ext_is_pms: bool) -> str:
    """
    Determine the game mode for a BMSON file based on mode hint, channel usage and file extension.
    
    Parameters
    ----------
    raw_mode_hint : str
        The 'mode_hint' value extracted from the BMSON JSON (e.g., 'generic-4k', 'beat-6k').
    used_x : set[int]
        Set of integer lane indices that appear in the chart.
    ext_is_pms : bool #bmsonの時点で拡張子はpmsではありえなく無意味だがコード上処理が間違っているわけではない
        True if the file extension is .pms, which forces 9K mode for BMSON files.
    
    Returns
    -------
    str
        One of: '4K', '6K', '9K', '10K', '14K', '7K', or '5K'.
    """
    # Normalise the hint to lower case for comparison
    raw_mode_hint = raw_mode_hint.lower().strip()

    has_scratch = bool(used_x & {8, 16})
    has_1P_7k = bool(used_x & {6, 7})
    has_2P_any = bool(used_x & set(range(9, 17)))
    has_2P_7k = bool(used_x & {14, 15})

    if raw_mode_hint in ("generic-4k", "beat-4k", "4k"):
        return "4K"
    elif raw_mode_hint in ("generic-6k", "beat-6k", "6k"):
        return "6K"
    elif ext_is_pms or (raw_mode_hint == "popn-9k"):
        return "9K"
    elif (
        not has_scratch
        and not has_2P_any
        and (6 in used_x or 7 in used_x or 8 in used_x or 9 in used_x)
        and not (has_1P_7k and 8 in used_x)
    ):
        return "9K"
    elif has_2P_any:
        return "14K" if (has_1P_7k or has_2P_7k) else "10K"
    elif not has_scratch and used_x and max(used_x) <= 4:
        return "4K"
    elif not has_scratch and used_x and max(used_x) <= 6 and not has_1P_7k:
        return "6K"
    else:
        return "7K" if has_1P_7k else "5K"
