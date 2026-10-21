import Foundation

public struct DragVelocityTracker {
    private var samples: [(Double, Double, Double)] = []
    private var lastMove: Double?
    public init() {}
    public mutating func add(time: Double, x: Double, y: Double) {
        guard time.isFinite, x.isFinite, y.isFinite else { return }
        if let last = samples.last, time <= last.0 { return }
        if samples.last.map({ hypot(x - $0.1, y - $0.2) > 0.01 }) ?? true { lastMove = time }
        samples.append((time, x, y))
        samples.removeAll { time - $0.0 > 0.120 }
    }
    public func velocity(at time: Double) -> ThrowVector {
        guard let lastMove, time - lastMove < 0.120 else { return .zero }
        let rows = samples.filter { time >= $0.0 && time - $0.0 <= 0.100 }
        guard rows.count > 1, rows.last!.0 - rows.first!.0 >= 0.002 else { return .zero }
        let ws = rows.map { exp(($0.0 - time) / 0.025) }, total = ws.reduce(0,+)
        let mt = zip(rows,ws).reduce(0) { $0 + $1.0.0 * $1.1 } / total
        let mx = zip(rows,ws).reduce(0) { $0 + $1.0.1 * $1.1 } / total
        let my = zip(rows,ws).reduce(0) { $0 + $1.0.2 * $1.1 } / total
        let den = zip(rows,ws).reduce(0) { $0 + $1.1 * pow($1.0.0 - mt, 2) }
        guard den > 1e-12 else { return .zero }
        let decay = max(0, 1 - max(0, time - lastMove - 0.025) / 0.095)
        return ThrowVector(zip(rows,ws).reduce(0) { $0 + $1.1 * ($1.0.0-mt) * ($1.0.1-mx) } / den * decay,
                           zip(rows,ws).reduce(0) { $0 + $1.1 * ($1.0.0-mt) * ($1.0.2-my) } / den * decay)
    }
    public static func release(pointer: ThrowVector, tangent: ThrowVector, config c: ThrowConfig) -> ThrowVector {
        let gain = c.pointerGain * min(1, hypot(pointer.x,pointer.y) / c.lowSpeed)
        var v = ThrowVector(pointer.x * gain + tangent.x, pointer.y * gain + tangent.y)
        let factor = min(1, c.maxSpeed / max(hypot(v.x,v.y),1e-9))
        v.x *= factor; v.y *= factor
        return v
    }
}
