import Foundation

/// 纯逻辑的帧时间线：给定当前时间，决定该显示哪一帧。与绘制无关，可用虚拟时钟测试。
public struct SpriteTimeline: Sendable {
    public let spec: AnimationSpec
    public private(set) var step: Int = 0
    public private(set) var stepStartedAt: Double
    /// 非循环动画播完后停在最后一帧（递交报告：递出一次后保持）。
    public private(set) var finished = false

    public init(spec: AnimationSpec, now: Double) {
        self.spec = spec
        self.stepStartedAt = now
        if spec.sequence.count <= 1 && !spec.loop { finished = true }
    }

    /// 当前应显示的图条帧索引。
    public var frame: Int { spec.sequence[step] }

    /// 下一次换帧的时间；停住时为 nil。
    public var nextChangeAt: Double? {
        finished ? nil : stepStartedAt + spec.durationsMs[step]
    }

    private var cycleMs: Double { spec.durationsMs.reduce(0, +) }

    /// 推进到 now。返回显示帧是否改变。
    @discardableResult
    public mutating func advance(to now: Double) -> Bool {
        let before = frame
        // 长时间挂起（休眠、窗口被遮挡）后不补播，直接从当前时刻重新计时。
        if spec.loop, cycleMs > 0, now - stepStartedAt > cycleMs * 2 {
            stepStartedAt = now
        }
        while let due = nextChangeAt, now >= due {
            if step + 1 < spec.sequence.count {
                step += 1
                stepStartedAt = due
            } else if spec.loop {
                // loopStart 之前的步只播一次（先递出报告，再循环眨眼）。
                step = min(spec.loopStart, spec.sequence.count - 1)
                stepStartedAt = due
            } else {
                finished = true
            }
        }
        return frame != before
    }
}
