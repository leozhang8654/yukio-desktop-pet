import Testing
@testable import YukioCore

@Suite struct MotionTimelineTests {
    @Test func introPlaysOnceThenLoopsFromLoopStart() {
        let spec = AnimationSpec(id: "respond", label: "", assetPath: "", frameWidth: 1, frameHeight: 1,
                                 sequence: [0, 1, 2, 3, 4, 3], durationsMs: [100, 100, 100, 1000, 60, 1000],
                                 loop: true, holdLastFrame: false, loopStart: 3)
        var tl = SpriteTimeline(spec: spec, now: 0)
        tl.advance(to: 250)
        #expect(tl.frame == 2)
        tl.advance(to: 1350)
        #expect(tl.frame == 4)
        tl.advance(to: 2400)
        // 一轮播完回到 loopStart（第 3 步），不再从递出报告的第 0 帧重播。
        #expect(tl.frame == 3 && tl.step == 3)
        var seen = Set<Int>()
        for t in stride(from: 2400.0, to: 20_000, by: 20) {
            tl.advance(to: t)
            seen.insert(tl.frame)
        }
        #expect(seen == [3, 4])
    }
}
