import Testing
@testable import YukioCore

@Suite struct BlinkClockTests {
    @Test func matchesReviewSchedulerFixture() {
        var clock = BlinkClock(seed: 173, now: 0)
        #expect(abs(clock.nextStart - 4073.081079497934) < 0.000001)
        #expect(abs(clock.duration - 257.62546254321933) < 0.000001)
        _ = clock.level(at: clock.nextStart + clock.duration + 0.01)
        #expect(abs(clock.nextStart - 7431.838982841001) < 0.000001)
    }

    @Test func switchingPreservesPendingSecondBlink() {
        var clock = BlinkClock(seed: 12, now: 0)
        let end = clock.nextStart + clock.duration
        clock.selectSeed(941)
        _ = clock.level(at: end + 0.01)
        #expect(abs(clock.nextStart - 4129.344158610329) < 0.000001)
        #expect(abs(clock.duration - 210.53379712626338) < 0.000001)
    }

    @Test func fixedSeedReproducesIrregularSchedule() {
        var a = BlinkClock(seed: 173, now: 0)
        var b = BlinkClock(seed: 173, now: 0)
        var c = BlinkClock(seed: 941, now: 0)
        var differs = false
        var starts: [Double] = []
        var last = 0
        for t in stride(from: 0.0, to: 180_000, by: 10) {
            let x = a.level(at: t)
            #expect(x == b.level(at: t))
            if x != c.level(at: t) { differs = true }
            if x > 0 && last == 0 { starts.append(t) }
            last = x
        }
        #expect(differs)
        #expect(starts.count > 25)
        let gaps = zip(starts, starts.dropFirst()).map { $1 - $0 }
        #expect(Set(gaps).count > 10)
        #expect(gaps.contains { $0 < 500 })
    }

    @Test func switchingStateDoesNotRestartPendingOrActiveBlink() {
        var clock = BlinkClock(seed: 173, now: 1000)
        let due = clock.nextStart
        let duration = clock.duration
        clock.selectSeed(941)
        #expect(clock.nextStart == due && clock.duration == duration)
        let closed = clock.level(at: due + duration * 0.44)
        clock.selectSeed(3251)
        #expect(closed == 6)
        #expect(clock.level(at: due + duration * 0.44) == closed)
        #expect(clock.nextStart == due)
    }

    @Test func durationAndDoubleBlinkGapStayInRange() {
        var c = BlinkClock(seed: 4567, now: 0)
        for _ in 0..<100 {
            let start = c.nextStart, duration = c.duration
            #expect(duration >= 180 && duration <= 260)
            #expect(c.level(at: start + duration * 0.44) == 6)
            _ = c.level(at: start + duration + 0.001)
            let gap = c.nextStart - start - duration
            #expect((100...180).contains(gap) || (2800...7000).contains(gap))
        }
    }
}
