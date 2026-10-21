import Foundation

/// Independent, reproducible wall-clock eyelids. Keep this instance when the
/// action changes: selecting a new seed never cancels an already scheduled blink.
public struct BlinkClock: Sendable {
    public private(set) var seed: UInt32
    public private(set) var nextStart: Double
    public private(set) var duration: Double
    private var randomState: UInt32
    private var second: (start: Double, duration: Double)?

    public init(seed: UInt32, now: Double) {
        self.seed = seed
        randomState = seed
        nextStart = now
        duration = 220
        schedule(after: now)
    }

    public mutating func selectSeed(_ value: UInt32) {
        guard seed != value else { return }
        seed = value
        randomState = value
        // nextStart, duration and a pending double blink deliberately survive.
    }

    private mutating func random(_ low: Double, _ high: Double) -> Double {
        randomState = 1_664_525 &* randomState &+ 1_013_904_223
        return low + (high - low) * Double(randomState) / 4_294_967_296
    }

    private mutating func schedule(after end: Double) {
        nextStart = end + random(2800, 7000)
        duration = random(180, 260)
        second = nil
        if random(0, 1) < 0.125 {
            let start = nextStart + duration + random(100, 180)
            second = (start, random(180, 260))
        }
    }

    public mutating func level(at now: Double, levels: Int = 6) -> Int {
        var skipped = 0
        while now >= nextStart + duration {
            if let pending = second {
                nextStart = pending.start
                duration = pending.duration
                second = nil
            } else {
                schedule(after: nextStart + duration)
            }
            skipped += 1
            // A very long machine sleep may discard old invisible events, but
            // normal action switches never enter this recovery path.
            if skipped > 10_000 { schedule(after: now); break }
        }
        let u = (now - nextStart) / duration
        guard u > 0, u < 1 else { return 0 }
        func smooth(_ x: Double) -> Double {
            let x = min(max(x, 0), 1)
            return x * x * (3 - 2 * x)
        }
        let amount = u < 0.36 ? smooth(u / 0.36)
            : (u < 0.52 ? 1 : 1 - smooth((u - 0.52) / 0.48))
        return Int((amount * Double(levels)).rounded())
    }
}
