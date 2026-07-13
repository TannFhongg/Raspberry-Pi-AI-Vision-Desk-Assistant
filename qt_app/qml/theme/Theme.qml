import QtQuick

Item {
    id: root
    visible: false

    FontLoader {
        id: bodyFontLoader
        source: Qt.resolvedUrl("../fonts/Roboto.ttf")
    }

    FontLoader {
        id: displayFontLoader
        source: Qt.resolvedUrl("../fonts/RobotoCondensed.ttf")
    }

    readonly property color shellOuter: "#20132f"
    readonly property color pageBackground: "#F6F8FB"
    readonly property color setupPageBackground: "#F6F8FB"
    readonly property color surface: "#ffffff"
    readonly property color surfaceElevated: "#ffffff"
    readonly property color surfaceMuted: "#d9d9d9"
    readonly property color surfacePanel: "#c4c4c4"
    readonly property color primary: "#2d9cff"
    readonly property color primarySoft: "#EAF2FF"
    readonly property color primaryStrong: "#1f6bff"
    readonly property color primaryDark: "#1753c7"
    readonly property color logoBlue: "#1f46ff"
    readonly property color text: "#111111"
    readonly property color textSecondary: "#333333"
    readonly property color textMuted: "#6B7280"
    readonly property color success: "#0da252"
    readonly property color successStrong: "#2DBE60"
    readonly property color warning: "#b57b00"
    readonly property color warningStrong: "#F5A623"
    readonly property color error: "#bf3030"
    readonly property color errorStrong: "#E04E4E"
    readonly property color unavailable: "#5c6773"
    readonly property color mutedFill: "#f2f4f7"
    readonly property color borderSoft: "#E4E7EC"
    readonly property color borderMuted: "#D0D5DD"
    readonly property color successFill: "#ecf9f1"
    readonly property color warningFill: "#fff3d9"
    readonly property color errorFill: "#fdeaea"
    readonly property color errorCardFill: "#fff4f4"
    readonly property color shadowColor: "#0F172A"
    readonly property color cardShadow: "#0F172A"

    readonly property string bodyFont: bodyFontLoader.name || displayFontLoader.name || ""
    readonly property string displayFont: displayFontLoader.name || bodyFontLoader.name || ""
    readonly property int weightRegular: 600
    readonly property int weightStrong: 800
    readonly property int weightHeavy: 900

    readonly property int space2xs: 4
    readonly property int spaceXs: 8
    readonly property int spaceSm: 12
    readonly property int spaceMd: 16
    readonly property int spaceLg: 24
    readonly property int spaceXl: 32
    readonly property int space2xl: 40

    readonly property int radiusShell: 30
    readonly property int radiusCard: 34
    readonly property int radiusCardMd: 30
    readonly property int radiusCardSm: 24
    readonly property int radiusControl: 16
    readonly property int radiusSetupCard: 24
    readonly property int radiusPill: 999
    readonly property int borderStrong: 3
    readonly property int dividerStrong: 4
    readonly property int healthPillWidth: 126
    readonly property int healthPillHeight: 72
    readonly property int footerButtonWidth: 164
    readonly property int footerButtonHeight: 54
    readonly property int controlHeight: 58
    readonly property int minimumTouchTarget: 50
    readonly property int animationShort: 220
    readonly property real cardShadowOpacity: 0.08
}
