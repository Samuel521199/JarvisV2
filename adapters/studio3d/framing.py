# SPDX-License-Identifier: GPL-2.0-or-later
"""Perspective fit for measured geometry in camera-aligned coordinates."""
import math
def distance(points,sensor_width_mm,lens_mm,aspect,margin=1.14):
    if not points or min(sensor_width_mm,lens_mm,aspect)<=0:raise ValueError('Invalid camera fit')
    tan_x=sensor_width_mm/(2*lens_mm);tan_y=tan_x/aspect
    result=max(z+margin*max(abs(x)/tan_x,abs(y)/tan_y) for x,y,z in points)
    if not math.isfinite(result) or result<=0:raise ValueError('Invalid camera bounds')
    return result
