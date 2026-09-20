import AppKit
import YukioCore

/// 菜单里那一行大小滑条：左边写“大小”，中间一条滑条，右边是当前百分比。
/// 拖动时雪绪实时跟着变大变小，松手即生效——不用再在几个固定档位里挑。
/// 落点吸到整 5%，既不会因手抖变成 137%，也能一眼滑回 100%。
final class ScaleSliderView: NSView {
    static let range: ClosedRange<Double> = 0.5...2.0
    static let step = 0.05

    /// 夹进可选范围，再吸到最近的一档。
    static func snap(_ value: Double) -> Double {
        let clamped = min(max(value, range.lowerBound), range.upperBound)
        return ((clamped / step).rounded() * step * 100).rounded() / 100
    }

    private let slider = NSSlider()
    private let readout = NSTextField(labelWithString: "")
    private let onChange: (CGFloat) -> Void
    /// 已经生效的档位：同一档内的鼠标移动不重复缩放窗口。
    private var applied: Double

    init(scale: CGFloat, onChange: @escaping (CGFloat) -> Void) {
        self.onChange = onChange
        self.applied = Self.snap(Double(scale))
        super.init(frame: NSRect(x: 0, y: 0, width: 260, height: 30))

        let menuFont = NSFont.menuFont(ofSize: 0)
        let title = NSTextField(labelWithString: tr("Size", "大小"))
        title.font = menuFont
        title.textColor = .labelColor

        // 等宽数字：拖动时百分比不会左右抖。
        readout.font = NSFont.monospacedDigitSystemFont(ofSize: menuFont.pointSize, weight: .regular)
        readout.textColor = .secondaryLabelColor
        readout.alignment = .right

        slider.minValue = Self.range.lowerBound
        slider.maxValue = Self.range.upperBound
        slider.doubleValue = applied
        slider.isContinuous = true
        slider.target = self
        slider.action = #selector(sliderMoved(_:))

        for v in [title, slider, readout] as [NSView] {
            v.translatesAutoresizingMaskIntoConstraints = false
            addSubview(v)
        }
        NSLayoutConstraint.activate([
            // 20 pt：与带勾的菜单项文字大致对齐。
            title.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 20),
            title.centerYAnchor.constraint(equalTo: centerYAnchor),
            slider.leadingAnchor.constraint(equalTo: title.trailingAnchor, constant: 10),
            slider.centerYAnchor.constraint(equalTo: centerYAnchor),
            readout.leadingAnchor.constraint(equalTo: slider.trailingAnchor, constant: 10),
            readout.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -14),
            readout.centerYAnchor.constraint(equalTo: centerYAnchor),
            readout.widthAnchor.constraint(equalToConstant: 44),
        ])
        // 菜单按最宽的一条撑开这一行；滑条跟着变长。
        autoresizingMask = .width
        showReadout()
    }

    required init?(coder: NSCoder) { fatalError("not used") }

    @objc private func sliderMoved(_ sender: NSSlider) {
        let value = Self.snap(sender.doubleValue)
        if value != sender.doubleValue { sender.doubleValue = value }
        guard value != applied else { return }
        applied = value
        showReadout()
        onChange(CGFloat(value))
    }

    private func showReadout() {
        readout.stringValue = "\(Int((applied * 100).rounded()))%"
    }
}
