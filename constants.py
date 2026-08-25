# レーンのインデックスマッピング (14K / 7K 左スクラッチ用)
CHANNEL_TO_LANE_LEFT = {
    "16": 0,   # scratch (1P)
    "17": 0,   # foot pedal (1P)
    "11": 1,
    "12": 2,
    "13": 3,
    "14": 4,
    "15": 5,
    "18": 6,
    "19": 7,
    "21": 8,
    "22": 9,
    "23": 10,
    "24": 11,
    "25": 12,
    "28": 13,
    "29": 14,
    "26": 15,  # right scratch (2P)
    "27": 15,  # right foot pedal (2P)
    # Mine note channels (1P)
    "D6": 0,   # mine scratch (1P)
    "D7": 0,   # mine foot pedal (1P)
    "D1": 1,
    "D2": 2,
    "D3": 3,
    "D4": 4,
    "D5": 5,
    "D8": 6,
    "D9": 7,
    # Mine note channels (2P)
    "E1": 8,
    "E2": 9,
    "E3": 10,
    "E4": 11,
    "E5": 12,
    "E8": 13,
    "E9": 14,
    "E6": 15,  # mine right scratch (2P)
    "E7": 15,  # mine right foot pedal (2P)
    "56": 0,   # longnote scratch (1P)
    "57": 0,   # longnote foot pedal (1P)
    "51": 1,
    "52": 2,
    "53": 3,
    "54": 4,
    "55": 5,
    "58": 6,
    "59": 7,
    "61": 8,
    "62": 9,
    "63": 10,
    "64": 11,
    "65": 12,
    "68": 13,
    "69": 14,
    "66": 15,  # longnote right scratch (2P)
    "67": 15,  # longnote right foot pedal (2P)
}

# レーンのインデックスマッピング (7K 右スクラッチ用)
CHANNEL_TO_LANE_RIGHT = {
    "11": 0,
    "12": 1,
    "13": 2,
    "14": 3,
    "15": 4,
    "18": 5,
    "19": 6,
    "16": 7,   # scratch (1P) → 右端
    "17": 7,   # foot pedal (1P) → 右端
    "21": 8,
    "22": 9,
    "23": 10,
    "24": 11,
    "25": 12,
    "28": 13,
    "29": 14,
    "26": 15,
    "27": 15,
    # Mine note channels (1P, right scratch layout)
    "D1": 0,
    "D2": 1,
    "D3": 2,
    "D4": 3,
    "D5": 4,
    "D8": 5,
    "D9": 6,
    "D6": 7,
    "D7": 7,
    "E1": 8,
    "E2": 9,
    "E3": 10,
    "E4": 11,
    "E5": 12,
    "E8": 13,
    "E9": 14,
    "E6": 15,
    "E7": 15,
    "51": 0,
    "52": 1,
    "53": 2,
    "54": 3,
    "55": 4,
    "58": 5,
    "59": 6,
    "56": 7,
    "57": 7,
    "61": 8,
    "62": 9,
    "63": 10,
    "64": 11,
    "65": 12,
    "68": 13,
    "69": 14,
    "66": 15,
    "67": 15,
}

# 5K レーンマッピング (左スクラッチ)
CHANNEL_TO_LANE_5K_LEFT = {
    "16": 0, "17": 0,
    "11": 1, "12": 2, "13": 3, "14": 4, "15": 5,
    "D6": 0, "D7": 0,
    "D1": 1, "D2": 2, "D3": 3, "D4": 4, "D5": 5,
    "56": 0, "57": 0,
    "51": 1, "52": 2, "53": 3, "54": 4, "55": 5,
}

# 5K レーンマッピング (右スクラッチ)
CHANNEL_TO_LANE_5K_RIGHT = {
    "11": 0, "12": 1, "13": 2, "14": 3, "15": 4,
    "16": 5, "17": 5,
    "D1": 0, "D2": 1, "D3": 2, "D4": 3, "D5": 4,
    "D6": 5, "D7": 5,
    "51": 0, "52": 1, "53": 2, "54": 3, "55": 4,
    "56": 5, "57": 5,
}

# 10K レーンマッピング (1P 左皿 / 2P 右皿)
CHANNEL_TO_LANE_10K = {
    "16": 0, "17": 0,
    "11": 1, "12": 2, "13": 3, "14": 4, "15": 5,
    "21": 6, "22": 7, "23": 8, "24": 9, "25": 10,
    "26": 11, "27": 11,
    "D6": 0, "D7": 0,
    "D1": 1, "D2": 2, "D3": 3, "D4": 4, "D5": 5,
    "E1": 6, "E2": 7, "E3": 8, "E4": 9, "E5": 10,
    "E6": 11, "E7": 11,
    "56": 0, "57": 0,
    "51": 1, "52": 2, "53": 3, "54": 4, "55": 5,
    "61": 6, "62": 7, "63": 8, "64": 9, "65": 10,
    "66": 11, "67": 11,
}

# 9K レーンマッピング (PMS 9鍵)
CHANNEL_TO_LANE_9K = {
    "11": 0, "12": 1, "13": 2, "14": 3, "15": 4,
    "22": 5, "23": 6, "24": 7, "25": 8,
    "D1": 0, "D2": 1, "D3": 2, "D4": 3, "D5": 4,
    "E2": 5, "E3": 6, "E4": 7, "E5": 8,
    "51": 0, "52": 1, "53": 2, "54": 3, "55": 4,
    "62": 5, "63": 6, "64": 7, "65": 8,
}

# 4K レーンマッピング
CHANNEL_TO_LANE_4K = {
    "11": 0, "12": 1, "14": 2, "15": 3,
    "D1": 0, "D2": 1, "D4": 2, "D5": 3,
    "51": 0, "52": 1, "54": 2, "55": 3,
}

# 6K レーンマッピング
CHANNEL_TO_LANE_6K = {
    "11": 0, "12": 1, "13": 2, "15": 3, "18": 4, "19": 5,
    "D1": 0, "D2": 1, "D3": 2, "D5": 3, "D8": 4, "D9": 5,
    "51": 0, "52": 1, "53": 2, "55": 3, "58": 4, "59": 5,
}

# レーンごとのノーツ表現
LANE_CHARS_LEFT = {
    0: "XX", 
    1: "[]", 2: "::", 3: "[]", 4: "::", 5: "[]", 6: "::", 7: "[]",
    8: "[]", 9: "::", 10: "[]", 11: "::", 12: "[]", 13: "::", 14: "[]",
    15: "XX",
}
LANE_CHARS_RIGHT = {
    0: "[]", 1: "::", 2: "[]", 3: "::", 4: "[]", 5: "::", 6: "[]",
    7: "XX",
    8: "[]", 9: "::", 10: "[]", 11: "::", 12: "[]", 13: "::", 14: "[]",
    15: "XX",
}

LANE_CHARS_5K_LEFT = {
    0: "XX", 1: "[]", 2: "::", 3: "[]", 4: "::", 5: "[]"
}
LANE_CHARS_5K_RIGHT = {
    0: "[]", 1: "::", 2: "[]", 3: "::", 4: "[]", 5: "XX"
}
LANE_CHARS_10K = {
    0: "XX", 1: "[]", 2: "::", 3: "[]", 4: "::", 5: "[]",
    6: "[]", 7: "::", 8: "[]", 9: "::", 10: "[]", 11: "XX"
}
LANE_CHARS_9K = {
    0: "()", 1: "^^", 2: "&&", 3: ">>", 4: "XX",
    5: "<<", 6: "&&", 7: "^^", 8: "()"
}
LANE_CHARS_4K = {
    0: "[]", 1: ">>", 2: "<<", 3: "[]"
}
LANE_CHARS_6K = {
    0: "[]", 1: "::", 2: ">>", 3: "<<", 4: "::", 5: "[]"
}

# キー名表示用のリスト
KEY_NAMES_DP = [
    "[S1]", "[1]", "[2]", "[3]", "[4]", "[5]", "[6]", "[7]",
    "[8]", "[9]", "[10]", "[11]", "[12]", "[13]", "[14]", "[S2]"
]
KEY_NAMES_RIGHT = [
    "[1]", "[2]", "[3]", "[4]", "[5]", "[6]", "[7]", "[S]"
]
KEY_NAMES_LEFT = [
    "[S]", "[1]", "[2]", "[3]", "[4]", "[5]", "[6]", "[7]"
]

KEY_NAMES_5K_LEFT = ["[S]", "[1]", "[2]", "[3]", "[4]", "[5]"]
KEY_NAMES_5K_RIGHT = ["[1]", "[2]", "[3]", "[4]", "[5]", "[S]"]
KEY_NAMES_10K = [
    "[S1]", "[1]", "[2]", "[3]", "[4]", "[5]",
    "[6]", "[7]", "[8]", "[9]", "[10]", "[S2]"
]
KEY_NAMES_9K = [
    "[W]", "[Y]", "[G]", "[B]", "[R]", "[B]", "[G]", "[Y]", "[W]"
]
KEY_NAMES_4K = [
    "[1]", "[2]", "[3]", "[4]"
]
KEY_NAMES_6K = [
    "[1]", "[2]", "[3]", "[4]", "[5]", "[6]"
]

def get_channel_to_lane_map(mode: str, scratch_side: str = "left") -> dict:
    """キーモードとスクラッチ位置に応じた channel_to_lane マップを返す"""
    mode_upper = mode.upper()
    if mode_upper == "4K":
        return CHANNEL_TO_LANE_4K.copy()
    elif mode_upper == "6K":
        return CHANNEL_TO_LANE_6K.copy()
    elif mode_upper == "9K":
        return CHANNEL_TO_LANE_9K.copy()
    elif mode_upper == "5K":
        return CHANNEL_TO_LANE_5K_RIGHT.copy() if scratch_side == "right" else CHANNEL_TO_LANE_5K_LEFT.copy()
    elif mode_upper == "10K":
        return CHANNEL_TO_LANE_10K.copy()
    elif mode_upper == "7K":
        return CHANNEL_TO_LANE_RIGHT.copy() if scratch_side == "right" else CHANNEL_TO_LANE_LEFT.copy()
    else:  # 14K / DP
        return CHANNEL_TO_LANE_LEFT.copy()

def get_lane_chars(mode: str, scratch_side: str = "left") -> dict:
    """キーモードとスクラッチ位置に応じた lane_chars を返す"""
    mode_upper = mode.upper()
    if mode_upper == "4K":
        return LANE_CHARS_4K
    elif mode_upper == "6K":
        return LANE_CHARS_6K
    elif mode_upper == "9K":
        return LANE_CHARS_9K
    elif mode_upper == "5K":
        return LANE_CHARS_5K_RIGHT if scratch_side == "right" else LANE_CHARS_5K_LEFT
    elif mode_upper == "10K":
        return LANE_CHARS_10K
    elif mode_upper == "7K":
        return LANE_CHARS_RIGHT if scratch_side == "right" else LANE_CHARS_LEFT
    else:  # 14K
        return LANE_CHARS_LEFT

def get_key_names(mode: str, scratch_side: str = "left") -> list:
    """キーモードとスクラッチ位置に応じた key_names を返す"""
    mode_upper = mode.upper()
    if mode_upper == "4K":
        return KEY_NAMES_4K
    elif mode_upper == "6K":
        return KEY_NAMES_6K
    elif mode_upper == "9K":
        return KEY_NAMES_9K
    elif mode_upper == "5K":
        return KEY_NAMES_5K_RIGHT if scratch_side == "right" else KEY_NAMES_5K_LEFT
    elif mode_upper == "10K":
        return KEY_NAMES_10K
    elif mode_upper == "7K":
        return KEY_NAMES_RIGHT if scratch_side == "right" else KEY_NAMES_LEFT
    else:  # 14K
        return KEY_NAMES_DP
