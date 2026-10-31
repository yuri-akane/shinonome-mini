# player/judgement.py - 判定窓計算モジュール


def get_judgement_windows(rank: int, easy_mode: bool) -> tuple[float, float, float, float]:
    """#RANK命令とEASYオプションに基づき、判定窓（秒）を返す。

    デフォルトの判定窓 (BMS #RANK 3 = NORMAL 相当)
    RANK: 0: VERY HARD, 1: HARD, 2: NORMAL, 3: EASY, 4: VERY EASY
    と言いつつ、歴史的なBMS仕様では RANK 2 が NORMAL, 3 が EASY
    """
    perf = 0.03
    great = 0.07
    good = 0.11
    bad = 0.15

    if rank == 0:     # VERY HARD
        perf, great, good, bad = 0.008, 0.024, 0.05, 0.10
    elif rank == 1:   # HARD
        perf, great, good, bad = 0.015, 0.045, 0.08, 0.12
    elif rank == 2:   # NORMAL
        perf, great, good, bad = 0.03, 0.06, 0.10, 0.15
    elif rank == 3:   # EASY
        perf, great, good, bad = 0.05, 0.10, 0.15, 0.20
    elif rank == 4:   # VERY EASY
        perf, great, good, bad = 0.10, 0.20, 0.30, 0.40

    # EASYオプションが有効な場合は、さらに判定窓を1.5倍緩くする
    if easy_mode:
        perf  *= 1.5
        great *= 1.5
        good  *= 1.5
        bad   *= 1.4  # 1.5 #badハマりがゲーム性を損なうのでせめてもの抵抗

    return perf, great, good, bad
