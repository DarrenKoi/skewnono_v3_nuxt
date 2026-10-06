"""Thin an AFM profile to what a browser can draw.

A profile travels as one JSON object per sample, and the page draws one chart
element per sample. A 2048 x 256 scan is 524,288 of them: tens of MB of JSON and
a heat map that hangs the tab while it paints. The chart is a few hundred pixels
across, so past that it could not show the extra samples anyway.

This runs in the route, after the provider, so home and office thin the same way.
"""
import math

__all__ = ["PROFILE_POINT_BUDGET", "thin_profile"]

# 512 x 64 (32,768), the grid the page was built on, passes untouched, and so does
# the longest 1D line (16,384 x 1). Raise it only after watching the page paint.
PROFILE_POINT_BUDGET = 65_536


def thin_profile(points: list[dict], budget: int = PROFILE_POINT_BUDGET) -> list[dict]:
    """At most `budget` samples of `points`, every one of them an original sample.

    Samples are picked, never averaged: Z stays the file's own value, and a
    missing sample stays missing instead of being smeared into its neighbours.
    A full lattice keeps every `step`-th row and column, so it is still a full,
    evenly spaced lattice and the page still draws it as cells. Anything else
    (a 1D line, a ragged scan) keeps every k-th sample in file order.
    """
    count = len(points)
    if count <= budget:
        return points

    xs = sorted({p["x"] for p in points})
    ys = sorted({p["y"] for p in points})
    if len(xs) > 1 and len(ys) > 1 and len(xs) * len(ys) == count:
        step = math.ceil(math.sqrt(count / budget))
        keep_x, keep_y = set(xs[::step]), set(ys[::step])
        return [p for p in points if p["x"] in keep_x and p["y"] in keep_y]

    return points[:: math.ceil(count / budget)]
