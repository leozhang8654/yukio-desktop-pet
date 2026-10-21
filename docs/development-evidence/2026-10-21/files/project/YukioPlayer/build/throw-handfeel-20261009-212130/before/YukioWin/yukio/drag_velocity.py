"""Event-time pointer velocity. Coordinates must already use one logical basis."""
import math


class DragVelocityTracker:
    def __init__(self, window=0.100, stopped=0.120):
        self.window, self.stopped = window, stopped
        self.samples = []
        self.last_move = None

    def add(self, t, x, y):
        if not all(math.isfinite(v) for v in (t, x, y)):
            return
        if self.samples and t <= self.samples[-1][0]:
            return
        if not self.samples or math.hypot(x-self.samples[-1][1], y-self.samples[-1][2]) > 0.01:
            self.last_move = t
        self.samples.append((t, x, y))
        self.samples = [s for s in self.samples if t-s[0] <= self.stopped]

    def velocity(self, t):
        if self.last_move is None or t-self.last_move >= self.stopped:
            return (0.0, 0.0)
        rows = [s for s in self.samples if 0 <= t-s[0] <= self.window]
        if len(rows) < 2 or rows[-1][0]-rows[0][0] < 0.002:
            return (0.0, 0.0)
        # Recent direction changes dominate, while every sample has nonzero weight.
        weights = [math.exp((s[0]-t)/0.025) for s in rows]
        total = sum(weights)
        means = [sum(w*s[i] for w,s in zip(weights,rows))/total for i in range(3)]
        denom = sum(w*(s[0]-means[0])**2 for w,s in zip(weights,rows))
        if denom < 1e-12:
            return (0.0, 0.0)
        decay = max(0.0, 1-max(0.0,t-self.last_move-0.025)/(self.stopped-0.025))
        return tuple(sum(w*(s[0]-means[0])*(s[i]-means[i]) for w,s in zip(weights,rows))/denom*decay for i in (1,2))


def release_velocity(pointer, tangent, config):
    speed = math.hypot(*pointer)
    gain = config['pointerGain'] * min(1.0, speed/config['lowSpeed'])
    v = [pointer[i]*gain+tangent[i] for i in range(2)]
    factor = min(1.0, config['maxSpeed']/max(math.hypot(*v), 1e-9))
    return tuple(n*factor for n in v)
