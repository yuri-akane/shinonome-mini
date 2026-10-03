
def estimated_total(note_count: float) -> float:
    """ If #TOTAL is missing or non‑positive, estimate a sensible default.
        Use common BMS community formula: TOTAL = 7.605 * notes / (0.01 * notes + 6.5)
        Clamp to a minimum of 260 (many players enforce this).
        ->だが私はこだわりの式を使う：7x / (0.01x + 6) + sqrt(x) - 10
    """
    if note_count > 0:
        #estimated = int(7.605 * note_count / (0.01 * note_count + 6.5))
        estimated = 7.0 * note_count / (0.01 * note_count + 6.0) + (note_count ** 0.5) - 10
        if estimated < 260:
            estimated = 260
        return estimated
    else:
        return 0

