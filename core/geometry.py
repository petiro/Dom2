def cubic_bezier(p0, p1, p2, p3, t):
    """
    Calcola un punto (x, y) su una curva di Bezier cubica al tempo t (0.0 - 1.0).
    Formula: B(t) = (1-t)^3*P0 + 3(1-t)^2*t*P1 + 3(1-t)t^2*P2 + t^3*P3
    """
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
