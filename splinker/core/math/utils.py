def rgb_to_hsv_255(r: int, g: int, b: int):
    # Input: r,g,b ∈ [0,255] (ints)
    # Output: (h, s, v) with h∈[0,359], s∈[0,255], v∈[0,255] (ints)
    if not (isinstance(r, int) and isinstance(g, int) and isinstance(b, int)):
        raise TypeError("r, g, b must be integers.")
    if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
        raise ValueError("r, g, b must be in [0,255].")

    rf = r / 255.0
    gf = g / 255.0
    bf = b / 255.0

    cmax = max(rf, gf, bf)
    cmin = min(rf, gf, bf)
    delta = cmax - cmin

    # Hue
    if delta == 0:
        h_deg = 0.0
    elif cmax == rf:
        h_deg = 60.0 * (((gf - bf) / delta) % 6.0)
    elif cmax == gf:
        h_deg = 60.0 * (((bf - rf) / delta) + 2.0)
    else:  # cmax == bf
        h_deg = 60.0 * (((rf - gf) / delta) + 4.0)

    # Saturation
    if cmax == 0:
        s_f = 0.0
    else:
        s_f = delta / cmax

    v_f = cmax

    # Scale to integer ranges
    h = int(round(h_deg)) % 360
    s = int(round(s_f * 255.0))
    v = int(round(v_f * 255.0))

    # Clamp in case of rounding edge cases
    h = max(0, min(359, h))
    s = max(0, min(255, s))
    v = max(0, min(255, v))
    return h, s, v
