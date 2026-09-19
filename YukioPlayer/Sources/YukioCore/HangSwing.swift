import Foundation

/// 被一只看不见的大手拎着时的晃动：把雪绪当成吊在抓手下面的单摆。
///
/// 手往右一甩，身体因为惯性落在后面（往左偏）；手停住，身体越过竖直方向荡到另一边，再来回几次收住。
/// 匀速拖着走时只剩空气阻力，身体略微后仰；一停就回正。
/// 竖直方向另有一根「会伸缩的布」：手猛地往上提，身体先坠在下面再弹回来——沉甸甸的感觉主要来自这里。
///
/// 纯逻辑、不碰 UI，时间用毫秒（与播放器其余部分一致），可以用虚拟时钟测试。
public struct HangSwing: Sendable {
    public struct Tuning: Sendable {
        /// 小幅摆动一个来回的秒数。沉的东西摆得慢：0.9 秒比 0.6 秒明显更有分量。
        /// 固定周期是为了手感稳定：放大雪绪时摆得一样慢，只是摆幅小些。
        public var periodSec: Double = 0.9
        /// 阻尼比。0 一直晃，1 不过冲。沉的东西惯性大，晃两下才停。
        public var damping: Double = 0.13
        /// 松手后的阻尼比：快一些停稳，好接回原来的动作。
        public var releaseDamping: Double = 0.4
        /// 空气阻力（1/秒）：匀速移动时身体略微落在后面（600 点/秒约 3°），停下即回正。
        public var airDrag: Double = 0.43
        /// 手的加速度有多少真的甩到她身上。严格按「一个点当一毫米」算，随便一拖就甩到顶格、
        /// 每次都一个样；打折之后：轻轻挪 3°、正常拖 11°、大步拖 18°、用力甩才碰上限。
        public var handCoupling: Double = 0.11
        /// 手速的低通时间常数（秒）。鼠标事件一跳一跳地来，先抹平再求加速度，免得抖成毛刺；
        /// 调大一点也让她起步慢半拍，像拖着个有分量的东西。
        public var velocitySmoothingSec: Double = 0.07
        /// 最大倾角（度）。撞到这个角度就像碰到挡块，不再往外走。
        public var maxAngleDeg: Double = 20
        /// 积分子步长（秒）。一帧切成若干步，快速甩动也不会发散。
        public var stepSec: Double = 1.0 / 240
        /// 竖直方向那根布的伸缩：一个来回的秒数与阻尼比。比左右摆快，弹一下就收住。
        public var sagPeriodSec: Double = 0.42
        public var sagDamping: Double = 0.32
        /// 手上下动的速度有多少变成「坠」。0.25 时轻轻提坠 4–6 点，猛地提坠 11 点（还没到上限）。
        public var verticalCoupling: Double = 0.25
        /// 最多坠多少，按摆长的比例（放大时跟着放大）。
        public var maxSagRatio: Double = 0.16
        /// 判定“停稳了”的角度（度）、角速度（度/秒）与坠的距离（点）。
        public var settleAngleDeg: Double = 0.7
        public var settleRateDegPerSec: Double = 9
        public var settleSagPoints: Double = 0.6

        public init() {}
    }

    public let tuning: Tuning
    /// 抓手到身体重心的距离（点）。只用来把手的加速度换算成角加速度：
    /// 同样的甩动，雪绪放大时（重心更远）摆幅更小，和真东西一样。
    public let length: Double

    /// 身体偏离竖直方向的角度（弧度），正数表示脚偏向右边。
    public private(set) var angle: Double = 0
    /// 角速度（弧度／秒）。
    public private(set) var rate: Double = 0
    /// 身体比抓手点低多少（点，正数＝坠下去）。渲染时整张图往下挪这么多。
    public private(set) var sag: Double = 0
    private var sagRate: Double = 0

    /// 平滑后的手的横向、纵向速度（点／秒；纵向以屏幕坐标为准，向上为正）。
    private var handVelocity: Double = 0
    private var handVelocityY: Double = 0
    private var lastHandX: Double?
    private var lastHandY: Double?
    private var lastMs: Double
    private var released = false

    public init(now: Double, length: Double = 96, tuning: Tuning = Tuning()) {
        self.tuning = tuning
        self.length = max(length, 1)
        self.lastMs = now
    }

    public var angleDegrees: Double { angle * 180 / .pi }

    /// 松手后已经停稳，可以切回原来的动作。
    public var settled: Bool {
        released
            && abs(angleDegrees) < tuning.settleAngleDeg
            && abs(rate * 180 / .pi) < tuning.settleRateDegPerSec
            && abs(sag) < tuning.settleSagPoints
    }

    /// 松手：大手把她放下，之后只剩自己荡回来，阻尼加大。
    public mutating func release() {
        released = true
    }

    /// 还在晃的时候又被抓住：接着当前的角度和角速度继续，不要归零。
    public mutating func grab() {
        released = false
    }

    /// 推进到 now。handX、handY 是抓手当前在屏幕上的位置（点，y 向上为正）。
    public mutating func advance(to now: Double, handX: Double, handY: Double) {
        var dt = (now - lastMs) / 1000
        lastMs = now
        guard dt > 0 else { return }
        // 休眠、被遮挡后可能隔了很久才回来，不要一次补积分半秒。
        dt = min(dt, 0.1)
        let smooth = 1 - exp(-dt / max(tuning.velocitySmoothingSec, 1e-4))

        let rawX = (handX - (lastHandX ?? handX)) / dt
        lastHandX = handX
        let previousX = handVelocity
        handVelocity += (rawX - handVelocity) * smooth
        // 抓手横向加速给的惯性冲量，等于把 -a/L·cosθ 在这一帧上积分一次。
        rate -= tuning.handCoupling * (handVelocity - previousX) * cos(angle) / length

        // 竖直方向同理：手往上提得越猛，身体越是先坠在下面。
        let rawY = (handY - (lastHandY ?? handY)) / dt
        lastHandY = handY
        let previousY = handVelocityY
        handVelocityY += (rawY - handVelocityY) * smooth
        sagRate += tuning.verticalCoupling * (handVelocityY - previousY)

        let w0 = 2 * .pi / max(tuning.periodSec, 1e-3)
        let ws = 2 * .pi / max(tuning.sagPeriodSec, 1e-3)
        let zeta = released ? tuning.releaseDamping : tuning.damping
        let limit = tuning.maxAngleDeg * .pi / 180
        let sagLimit = tuning.maxSagRatio * length
        var remaining = dt
        while remaining > 0 {
            let h = min(tuning.stepSec, remaining)
            remaining -= h
            let gravity = -w0 * w0 * sin(angle)
            let friction = -2 * zeta * w0 * rate
            let air = -tuning.airDrag * handVelocity * cos(angle) / length
            rate += (gravity + friction + air) * h
            angle += rate * h
            if angle > limit { angle = limit; rate = min(rate, 0) }
            if angle < -limit { angle = -limit; rate = max(rate, 0) }

            sagRate += (-ws * ws * sag - 2 * tuning.sagDamping * ws * sagRate) * h
            sag += sagRate * h
            if sag > sagLimit { sag = sagLimit; sagRate = min(sagRate, 0) }
            if sag < -sagLimit { sag = -sagLimit; sagRate = max(sagRate, 0) }
        }
    }
}
