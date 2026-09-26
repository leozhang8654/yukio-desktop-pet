"""Rigid, conjugate eye movement under fixed eyelids and eye corners.

Only iris colour detail is translated. Its backing is reconstructed from the
source sclera, so no remap can pull eyelashes, skin or hair into the eye white.
All coordinates are in the approved 2x artwork, not desktop points.
"""
from dataclasses import dataclass

import cv2
import numpy as np


def largest_component(mask):
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype('uint8'))
    if count < 2:
        raise ValueError('No iris found in the approved eye box')
    return labels == 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])


@dataclass
class EyeLayer:
    box: tuple
    aperture: np.ndarray
    foreground: np.ndarray
    iris: np.ndarray
    sclera: np.ndarray

    @classmethod
    def make(cls, prem, eye):
        x0, y0, x1, y1 = eye.box
        rgb = prem[y0:y1, x0:x1, :3]
        red, green, blue = rgb.transpose(2, 0, 1)
        # The saturated blue component belongs to the iris, including its dark
        # outline. Fill the convex hull to retain the pupil and white catchlight.
        blue_seed = largest_component((blue - red > .065) & (blue > .06) & (green - red > .005))
        hull = cv2.convexHull(np.column_stack(np.nonzero(blue_seed)[::-1]).astype('int32'))
        iris = np.zeros(blue_seed.shape, 'uint8')
        cv2.fillConvexPoly(iris, hull, 1)

        # Follow the actual opening, not the blink helper's extrapolated almond.
        # Warm skin and dark eyelashes are excluded; only the component touching
        # this iris is kept, excluding separate strands of white hair.
        candidate = ((blue - red > .03) & (blue > .06)) | ((blue - red > -.025) & (rgb.min(2) > .52))
        _, labels = cv2.connectedComponents(candidate.astype('uint8'))
        label = np.bincount(labels[blue_seed]).argmax()
        aperture = (labels == label).astype('uint8')
        contours, _ = cv2.findContours(aperture, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(aperture, contours, -1, 1, cv2.FILLED)

        # A one-pixel fringe retains the antialiased blue iris edge, but never
        # includes a corner/lash outside the fixed opening.
        iris = cv2.dilate(iris, np.ones((3, 3), 'uint8')) * aperture
        donors = (aperture > 0) & (iris == 0) & (rgb.min(2) > .52) & (np.ptp(rgb, axis=2) < .22)
        if donors.sum() < 3:
            raise ValueError(f'Insufficient sclera samples in {eye.box}')
        # Source-sampled row shading continues behind the iris. No inpainting
        # donors come from lashes or the surrounding skin.
        rows = np.flatnonzero(donors.any(axis=1))
        colours = np.array([np.median(rgb[y][donors[y]], axis=0) for y in rows])
        row_colours = np.stack([np.interp(np.arange(rgb.shape[0]), rows, colours[:, c])
                                for c in range(3)], axis=1).astype('float32')
        sclera = np.broadcast_to(row_colours[:, None, :], rgb.shape).copy()
        # Smooth donor shading vertically; individual antialiased edge samples
        # must not turn into horizontal stripes on the revealed eye white.
        sclera = cv2.GaussianBlur(sclera, (1, 9), 2)
        foreground = np.concatenate([rgb * iris[..., None], iris[..., None]], axis=2).astype('float32')
        return cls(eye.box, aperture.astype(bool), foreground, iris.astype(bool), sclera)

    def translated(self, dx, dy):
        h, w = self.aperture.shape
        # Interpolation samples this isolated layer only; a rigid translation
        # preserves iris size and shape, unlike a spatially varying face warp.
        matrix = np.array([[1, 0, dx], [0, 1, dy]], 'float32')
        return cv2.warpAffine(self.foreground, matrix, (w, h), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0)


class GazeRig:
    def __init__(self, prem, eyes, poses):
        self.source = prem
        self.eyes = [EyeLayer.make(prem, eye) for eye in eyes]
        # Use a single gain for BOTH eyes. Independent clamping would let one
        # iris stop while the other kept moving, producing a converging gaze.
        extents = np.array([p['gaze'] for p in poses], dtype='float32')
        maximum = np.max(np.abs(extents), axis=0)
        spans = []
        for eye in self.eyes:
            y, x = np.nonzero(eye.aperture)
            spans.append((np.ptp(x) + 1, np.ptp(y) + 1))
        limit = np.min(spans, axis=0) * np.array([.10, .08])
        self.gain = np.minimum(1, limit / np.maximum(maximum, 1e-6))

    def offset(self, dx, dy):
        return np.array([dx, dy]) * self.gain

    def render(self, dx, dy):
        if abs(dx) + abs(dy) < .001:
            return self.source
        dx, dy = self.offset(dx, dy)
        result = self.source.copy()
        for eye in self.eyes:
            x0, y0, x1, y1 = eye.box
            rgb = result[y0:y1, x0:x1, :3]
            shifted = eye.translated(dx, dy)
            background = np.where(eye.iris[..., None], eye.sclera, rgb)
            composed = shifted[..., :3] + background * (1 - shifted[..., 3:4])
            rgb[eye.aperture] = composed[eye.aperture]
        result[..., :3] = np.clip(result[..., :3], 0, result[..., 3:4])
        return result
