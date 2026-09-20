import Testing
@testable import YukioCore

@Suite struct L10nTests {
    @Test func recognisesLanguageCodes() {
        #expect(UILanguage(code: nil) == .english)
        #expect(UILanguage(code: "en") == .english)
        #expect(UILanguage(code: "zh") == .chinese)
        #expect(UILanguage(code: "zh-Hans") == .chinese)
        #expect(UILanguage(code: "ZH_CN") == .chinese)
        #expect(UILanguage(code: "fr") == .english)
    }

    @Test func picksTextByLanguage() {
        #expect(tr("Idle", "空闲", in: .english) == "Idle")
        #expect(tr("Idle", "空闲", in: .chinese) == "空闲")
    }
}
