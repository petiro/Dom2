def cubic_bezier(p0, p1, p2, p3, t):
    """Calcola un punto (x, y) su una curva di Bezier cubica."""
    x0, y0 = p0
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3

    u = 1 - t
    tt = t * t
    uu = u * u
    uuu = uu * u
    ttt = tt * t

    x = uuu * x0 + 3 * uu * t * x1 + 3 * u * tt * x2 + ttt * x3
    y = uuu * y0 + 3 * uu * t * y1 + 3 * u * tt * y2 + ttt * y3

    return x, y

def clamp_point(x, y, max_w, max_h):
    """FIX 3.2: Limita le coordinate al viewport per sicurezza."""
    if max_w <= 0: max_w = 1920
    if max_h <= 0: max_h = 1080
    
    cx = max(0, min(x, max_w))
    cy = max(0, min(y, max_h))
    return cx, cy