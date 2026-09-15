import Foundation

/// 一段图条动画：横向图条中按 sequence 取帧，每步停留 durationsMs。
public struct AnimationSpec: Equatable, Sendable {
    public let id: String
    public let label: String
    /// 相对资源根目录的路径，例如 "activities/thinking.webp"。
    public let assetPath: String
    public let frameWidth: Int
    public let frameHeight: Int
    public let sequence: [Int]
    public let durationsMs: [Double]
    public let loop: Bool
    public let holdLastFrame: Bool
    /// 循环时回到的步序号：前面的步只播一次（例如先递出报告，再循环眨眼）。
    public var loopStart: Int = 0

    public var maxFrameIndex: Int { sequence.max() ?? 0 }
}

public enum CatalogError: Error, CustomStringConvertible {
    case missing(String)
    case invalid(String)

    public var description: String {
        switch self {
        case .missing(let s): return "缺少资源：\(s)"
        case .invalid(let s): return "资源定义无效：\(s)"
        }
    }
}

/// 从 activities.json 与 base-animations.json 读取的动画索引；motion/motion.json 存在时，其中的小幅动作覆盖同名动画。
public struct AnimationCatalog: Sendable {
    public let specs: [String: AnimationSpec]

    public static let runningLeftID = "running-left"
    public static let runningRightID = "running-right"

    private struct ActivitiesFile: Decodable {
        struct State: Decodable {
            let id: String
            let label: String
            let asset: String
            let frameWidth: Int
            let frameHeight: Int
            let sequence: [Int]
            let durationsMs: [Double]
            let loop: Bool
            let holdLastFrame: Bool
        }
        let states: [State]
    }

    private struct BaseFile: Decodable {
        struct Anim: Decodable {
            let id: String
            let asset: String
            let frameWidth: Int
            let frameHeight: Int
            let frameCount: Int
            let nativeDurationsMs: [Double]?
        }
        let animations: [Anim]
    }

    /// tools/motion 生成的小幅动作：一张底图加局部平滑变形，逐帧图条放在 motion/ 目录。
    private struct MotionFile: Decodable {
        struct State: Decodable {
            let id: String
            let asset: String
            let frameWidth: Int
            let frameHeight: Int
            let sequence: [Int]
            let durationsMs: [Double]
            let loop: Bool
            let loopStart: Int?
        }
        let states: [State]
    }

    /// 播放器对一段基础图条的用法。
    private struct BaseUse {
        let label: String
        /// 播一次后停在最后一帧的序列与逐帧时长；nil 表示按原生时序循环全部帧。
        var once: (sequence: [Int], durationsMs: [Double])? = nil
    }

    /// 基础图条中播放器实际使用的动画。其余（旧原生槽位、视线方向）不加载。
    private static let usedBase: [String: BaseUse] = [
        "idle": BaseUse(label: "空闲"),
        runningLeftID: BaseUse(label: "向左跑动"),
        runningRightID: BaseUse(label: "向右跑动"),
        // 原生图条是 中立 #0–1 → 过渡 #2 → 垂眼 #3–5（三帧相同）→ 过渡 #6 → 中立 #7，140 ms 一帧循环，
        // 等于每 1.2 秒低落又恢复一次。这里只垂眼一次并停住，与“递交报告”一样播完保持。
        "failed": BaseUse(label: "失败／沮丧", once: (sequence: [0, 2, 3], durationsMs: [240, 180, 1000])),
    ]

    public init(specs: [String: AnimationSpec]) {
        self.specs = specs
    }

    public static func load(assetsRoot: URL) throws -> AnimationCatalog {
        var specs: [String: AnimationSpec] = [:]

        let activitiesURL = assetsRoot.appendingPathComponent("activities/activities.json")
        guard let activitiesData = try? Data(contentsOf: activitiesURL) else {
            throw CatalogError.missing(activitiesURL.path)
        }
        let activities = try JSONDecoder().decode(ActivitiesFile.self, from: activitiesData)
        for s in activities.states {
            guard s.sequence.count == s.durationsMs.count, !s.sequence.isEmpty else {
                throw CatalogError.invalid("\(s.id)：sequence 与 durationsMs 长度不一致")
            }
            specs[s.id] = AnimationSpec(
                id: s.id, label: s.label, assetPath: "activities/\(s.asset)",
                frameWidth: s.frameWidth, frameHeight: s.frameHeight,
                sequence: s.sequence, durationsMs: s.durationsMs,
                loop: s.loop, holdLastFrame: s.holdLastFrame)
        }

        let baseURL = assetsRoot.appendingPathComponent("base/base-animations.json")
        guard let baseData = try? Data(contentsOf: baseURL) else {
            throw CatalogError.missing(baseURL.path)
        }
        let base = try JSONDecoder().decode(BaseFile.self, from: baseData)
        for a in base.animations {
            guard let use = usedBase[a.id] else { continue }
            if let once = use.once {
                guard once.sequence.count == once.durationsMs.count, !once.sequence.isEmpty else {
                    throw CatalogError.invalid("\(a.id)：sequence 与 durationsMs 长度不一致")
                }
                specs[a.id] = AnimationSpec(
                    id: a.id, label: use.label, assetPath: "base/\(a.asset)",
                    frameWidth: a.frameWidth, frameHeight: a.frameHeight,
                    sequence: once.sequence, durationsMs: once.durationsMs,
                    loop: false, holdLastFrame: true)
                continue
            }
            guard let durations = a.nativeDurationsMs, durations.count == a.frameCount else {
                throw CatalogError.invalid("\(a.id)：缺少逐帧时序")
            }
            specs[a.id] = AnimationSpec(
                id: a.id, label: use.label, assetPath: "base/\(a.asset)",
                frameWidth: a.frameWidth, frameHeight: a.frameHeight,
                sequence: Array(0..<a.frameCount), durationsMs: durations,
                loop: true, holdLastFrame: false)
        }

        // 小幅动作覆盖同名动画；没有这个文件时按原图条播放。
        let motionURL = assetsRoot.appendingPathComponent("motion/motion.json")
        if let motionData = try? Data(contentsOf: motionURL) {
            let motion = try JSONDecoder().decode(MotionFile.self, from: motionData)
            for m in motion.states {
                guard m.sequence.count == m.durationsMs.count, !m.sequence.isEmpty else {
                    throw CatalogError.invalid("motion \(m.id)：sequence 与 durationsMs 长度不一致")
                }
                let loopStart = m.loopStart ?? 0
                guard loopStart >= 0, loopStart < m.sequence.count else {
                    throw CatalogError.invalid("motion \(m.id)：loopStart 越界")
                }
                specs[m.id] = AnimationSpec(
                    id: m.id, label: specs[m.id]?.label ?? m.id, assetPath: "motion/\(m.asset)",
                    frameWidth: m.frameWidth, frameHeight: m.frameHeight,
                    sequence: m.sequence, durationsMs: m.durationsMs,
                    loop: m.loop, holdLastFrame: !m.loop, loopStart: loopStart)
            }
        }

        let catalog = AnimationCatalog(specs: specs)
        for state in PetState.allCases where catalog.specs[state.rawValue] == nil {
            throw CatalogError.missing("状态 \(state.rawValue) 没有对应动画")
        }
        for id in [runningLeftID, runningRightID] where specs[id] == nil {
            throw CatalogError.missing("基础动画 \(id)")
        }
        return catalog
    }

    /// 状态对应的动画；缺失时回退到默认电脑桌。
    public func spec(for state: PetState) -> AnimationSpec {
        specs[state.rawValue] ?? specs[PetState.default_work.rawValue]!
    }

    public func label(for state: PetState) -> String {
        spec(for: state).label
    }

    /// 检查每段动画的帧索引不越过图条宽度、帧尺寸一致。imageSize 返回资源的像素尺寸。
    public func validate(imageSize: (String) -> (width: Int, height: Int)?) -> [String] {
        var problems: [String] = []
        for spec in specs.values.sorted(by: { $0.id < $1.id }) {
            guard let size = imageSize(spec.assetPath) else {
                problems.append("\(spec.id)：无法读取 \(spec.assetPath)")
                continue
            }
            if size.height != spec.frameHeight {
                problems.append("\(spec.id)：图高 \(size.height) ≠ 帧高 \(spec.frameHeight)")
            }
            if size.width % spec.frameWidth != 0 {
                problems.append("\(spec.id)：图宽 \(size.width) 不是帧宽 \(spec.frameWidth) 的整数倍")
            }
            let frames = size.width / spec.frameWidth
            if spec.maxFrameIndex >= frames {
                problems.append("\(spec.id)：帧索引 \(spec.maxFrameIndex) 越界（共 \(frames) 帧）")
            }
        }
        return problems
    }
}
