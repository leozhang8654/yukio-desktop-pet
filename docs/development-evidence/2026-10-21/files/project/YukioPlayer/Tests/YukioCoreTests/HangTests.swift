import Foundation
import Testing
@testable import YukioCore

/// 按 30 Hz 推进摆动，手的位置由一段轨迹给出。
private struct Hand {
    var swing: HangSwing
    var now: Double
    var x: Double
    var y: Double

    init(length: Double = 100, tuning: HangSwing.Tuning = HangSwing.Tuning(), x: Double = 500, y: Double = 400) {
        swing = HangSwing(now: 0, length: length, tuning: tuning)
        now = 0
        self.x = x
        self.y = y
    }

    /// 以速度 v（点／秒）横着走 ms 毫秒。v 为 0 就是停在原地。
    mutating func move(_ v: Double, ms: Double, step: Double = 1000.0 / 30) {
        move(v, up: 0, ms: ms, step: step)
    }

    /// 横向 v、纵向 up（向上为正，点／秒）走 ms 毫秒。
    mutating func move(_ v: Double, up: Double, ms: Double, step: Double = 1000.0 / 30) {
        var left = ms
        while left > 0 {
            let h = min(step, left)
            left -= h
            now += h
            x += v * h / 1000
            y += up * h / 1000
            swing.advance(to: now, handX: x, handY: y)
        }
    }

    var degrees: Double { swing.angleDegrees }
}

@Suite struct HangSwingTests {
    @Test func hangsStraightWhenNobodyMoves() {
        var hand = Hand()
        hand.move(0, ms: 2000)
        #expect(abs(hand.degrees) < 0.001)
    }

    @Test func bodyLagsBehindTheHand() {
        // 往右加速：身体落在后面，也就是脚偏向左（负角）。
        var right = Hand()
        right.move(900, ms: 200)
        #expect(right.degrees < -3)

        var left = Hand()
        left.move(-900, ms: 200)
        #expect(left.degrees > 3)
    }

    @Test func swingsPastVerticalAfterStopping() {
        var hand = Hand()
        hand.move(900, ms: 250)
        let lag = hand.degrees
        #expect(lag < -3)
        // 手停住，身体越过竖直方向荡到前面去。
        var overshoot = 0.0
        for _ in 0..<12 {
            hand.move(0, ms: 1000.0 / 30)
            overshoot = max(overshoot, hand.degrees)
        }
        #expect(overshoot > 2)
    }

    @Test func swingDiesDown() {
        var hand = Hand()
        hand.move(1200, ms: 200)
        hand.move(0, ms: 200)
        var first = 0.0, later = 0.0
        for _ in 0..<30 { hand.move(0, ms: 1000.0 / 30); first = max(first, abs(hand.degrees)) }
        for _ in 0..<30 { hand.move(0, ms: 1000.0 / 30); later = max(later, abs(hand.degrees)) }
        #expect(later < first * 0.7)
    }

    @Test func leansBackWhileCarriedAtConstantSpeed() {
        // 匀速拖着走：只剩空气阻力，身体稳定地略微落在后面，不会越摆越大。
        var hand = Hand()
        hand.move(600, ms: 3000)
        #expect(hand.degrees < -1 && hand.degrees > -12)
        // 停下就回正。
        hand.move(0, ms: 2500)
        #expect(abs(hand.degrees) < 1.5)
    }

    @Test func neverFoldsOverEvenWhenFlungAround() {
        var hand = Hand()
        var worst = 0.0
        for i in 0..<20 {
            hand.move(i % 2 == 0 ? 6000 : -6000, ms: 120)
            worst = max(worst, abs(hand.degrees))
        }
        #expect(worst <= HangSwing.Tuning().maxAngleDeg + 0.001)
    }

    @Test func biggerPetSwingsLess() {
        // 重心更远（放大后的雪绪）：同样的甩动，摆幅更小。
        var small = Hand(length: 100)
        var big = Hand(length: 160)
        small.move(900, ms: 200)
        big.move(900, ms: 200)
        #expect(abs(big.degrees) < abs(small.degrees))
    }

    @Test func settlesSoonAfterRelease() {
        var hand = Hand()
        hand.move(1500, up: 600, ms: 200)
        hand.swing.release()
        #expect(!hand.swing.settled)
        var msToSettle = 0.0
        while !hand.swing.settled && msToSettle < 4000 {
            hand.move(0, ms: 1000.0 / 30)
            msToSettle += 1000.0 / 30
        }
        #expect(hand.swing.settled)
        #expect(msToSettle < 2400)          // 播放器最多等 2400 ms 就放下
    }

    // MARK: 重量感：竖直方向那根会伸缩的布

    @Test func bodySinksWhenLiftedQuickly() {
        var hand = Hand()
        hand.move(0, up: 900, ms: 200)
        #expect(hand.swing.sag > 4)         // 手往上提，身体先坠在下面
        // 手停住后弹回来，越过原位一点再收住。
        var lowest = hand.swing.sag
        for _ in 0..<30 {
            hand.move(0, ms: 1000.0 / 30)
            lowest = min(lowest, hand.swing.sag)
        }
        #expect(lowest < 0)
        hand.move(0, ms: 1500)
        #expect(abs(hand.swing.sag) < 0.6)
    }

    @Test func pureSidewaysDragDoesNotSink() {
        var hand = Hand()
        hand.move(1200, ms: 400)
        #expect(abs(hand.swing.sag) < 0.001)
    }

    @Test func sinkingHasALimit() {
        var hand = Hand(length: 100)
        for _ in 0..<10 { hand.move(0, up: 9000, ms: 100); hand.move(0, up: -9000, ms: 100) }
        #expect(abs(hand.swing.sag) <= 0.16 * 100 + 0.001)
    }

    @Test func grabbingAgainKeepsTheCurrentSwing() {
        var hand = Hand()
        hand.move(1200, ms: 200)
        hand.swing.release()
        hand.move(0, ms: 100)
        let angle = hand.degrees
        hand.swing.grab()
        #expect(hand.swing.angleDegrees == angle)
        #expect(!hand.swing.settled)
    }

    @Test func survivesSleepAndFrameDrops() {
        // 窗口被遮住、机器休眠后隔很久才回来：不补积分，也不会炸成 NaN。
        var hand = Hand()
        hand.move(900, ms: 200)
        hand.now += 600_000
        hand.swing.advance(to: hand.now, handX: hand.x + 4000, handY: hand.y - 3000)
        #expect(hand.degrees.isFinite)
        #expect(abs(hand.degrees) <= HangSwing.Tuning().maxAngleDeg + 0.001)
    }
}
