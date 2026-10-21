import Foundation

/// 让显示的文字至少停留一段时间：同一动作里细节变得太快（连续读几个文件）时不逐个闪过。
/// 调用方每帧传入最新的值；停留期内的变化在期满后直接显示最新值，中间值被跳过。
public struct HeldValue<Value: Equatable> {
    public private(set) var value: Value
    public var minHoldMs: Double
    private var changedAt: Double = -.infinity

    public init(_ value: Value, minHoldMs: Double) {
        self.value = value
        self.minHoldMs = minHoldMs
    }

    /// immediate：跳过停留（例如气泡出现或消失）。返回显示值是否改变。
    @discardableResult
    public mutating func update(_ new: Value, now: Double, immediate: Bool = false) -> Bool {
        guard new != value else { return false }
        guard immediate || now - changedAt >= minHoldMs else { return false }
        value = new
        changedAt = now
        return true
    }
}
