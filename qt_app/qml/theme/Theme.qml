import QtQuick

Item {
    id: root
    visible: false

    property string bodyFontOverride: ""
    property string textSize: "standard"
    property string renderingPolicy: "qt"

    DisplayMetrics { id: displayMetrics }
    Typography { id: typography; textSize: root.textSize }

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
    readonly property color surfaceMuted: "#E2E7EF"
    readonly property color surfacePanel: "#D4DBE6"
    readonly property color primary: "#2d9cff"
    readonly property color primarySoft: "#EAF2FF"
    readonly property color primaryStrong: "#1f6bff"
    readonly property color primaryDark: "#1753c7"
    readonly property color logoBlue: "#1f46ff"
    readonly property color text: "#111111"
    readonly property color textSecondary: "#333333"
    readonly property color textMuted: "#4B5565"
    readonly property color success: "#0da252"
    readonly property color successStrong: "#2DBE60"
    readonly property color warning: "#b57b00"
    readonly property color warningStrong: "#F5A623"
    readonly property color error: "#bf3030"
    readonly property color errorStrong: "#E04E4E"
    readonly property color unavailable: "#566171"
    readonly property color mutedFill: "#f2f4f7"
    readonly property color borderSoft: "#E4E7EC"
    readonly property color borderMuted: "#D0D5DD"
    readonly property color successFill: "#ecf9f1"
    readonly property color warningFill: "#fff3d9"
    readonly property color errorFill: "#fdeaea"
    readonly property color errorCardFill: "#fff4f4"
    readonly property color shadowColor: "#0F172A"
    readonly property color cardShadow: "#0F172A"

    readonly property string bodyFont: root.bodyFontOverride || bodyFontLoader.name || displayFontLoader.name || "sans-serif"
    readonly property string displayFont: displayFontLoader.name || bodyFontLoader.name || ""
    readonly property int weightRegular: 400
    readonly property int weightStrong: 600
    readonly property int weightHeavy: 700

    readonly property int textRenderType: root.renderingPolicy === "native"
                                          ? Text.NativeRendering : Text.QtRendering
    readonly property int hintingPreference: Font.PreferVerticalHinting

    readonly property int referenceWidth: displayMetrics.referenceWidth
    readonly property int referenceHeight: displayMetrics.referenceHeight
    readonly property int pageMargin: displayMetrics.pageMargin
    readonly property int appHeaderHeight: displayMetrics.appHeaderHeight
    readonly property int headerDividerGap: displayMetrics.headerDividerGap
    readonly property int pageTopGap: displayMetrics.pageTopGap
    readonly property int footerHeight: displayMetrics.footerHeight
    readonly property int pageSpacing: displayMetrics.pageSpacing
    readonly property int standardSpacing: displayMetrics.standardSpacing
    readonly property int cardSpacing: displayMetrics.cardSpacing
    readonly property int diagnosticCardPadding: displayMetrics.diagnosticCardPadding
    readonly property int diagnosticCardSpacing: displayMetrics.diagnosticCardSpacing
    readonly property int diagnosticGridSpacing: displayMetrics.diagnosticGridSpacing
    readonly property int sidePanelWidth: displayMetrics.sidePanelWidth
    readonly property int resultImagePanelWidth: displayMetrics.resultImagePanelWidth
    readonly property int focusBorderWidth: displayMetrics.focusBorderWidth
    readonly property int iconSmall: displayMetrics.iconSmall
    readonly property int iconMedium: displayMetrics.iconMedium
    readonly property int iconLarge: displayMetrics.iconLarge

    readonly property int fontBrand: typography.brand
    readonly property int fontPageTitle: typography.pageTitle
    readonly property int fontSectionTitle: typography.sectionTitle
    readonly property int fontCardTitle: typography.cardTitle
    readonly property int fontBody: typography.body
    readonly property int fontSecondaryBody: typography.secondaryBody
    readonly property int fontButton: typography.button
    readonly property int fontStatus: typography.status
    readonly property int fontResultContent: typography.resultContent
    readonly property int fontCaption: typography.caption
    readonly property int fontTechnicalMetadata: typography.technicalMetadata
    readonly property real headingLineHeight: typography.headingLineHeight
    readonly property real bodyLineHeight: typography.bodyLineHeight
    readonly property real resultLineHeight: typography.resultLineHeight

    function fontSizeForRole(role) {
        if (role === "brand") return fontBrand
        if (role === "pageTitle") return fontPageTitle
        if (role === "sectionTitle") return fontSectionTitle
        if (role === "cardTitle") return fontCardTitle
        if (role === "secondaryBody") return fontSecondaryBody
        if (role === "button") return fontButton
        if (role === "status") return fontStatus
        if (role === "resultContent") return fontResultContent
        if (role === "caption") return fontCaption
        if (role === "technicalMetadata") return fontTechnicalMetadata
        return fontBody
    }

    function lineHeightForRole(role) {
        if (role === "resultContent") return resultLineHeight
        if (role === "brand" || role === "pageTitle" || role === "sectionTitle" || role === "cardTitle")
            return headingLineHeight
        return bodyLineHeight
    }

    readonly property int space2xs: 4
    readonly property int spaceXs: 8
    readonly property int spaceSm: 12
    readonly property int spaceMd: 16
    readonly property int spaceLg: 24
    readonly property int spaceXl: 32
    readonly property int space2xl: 40

    readonly property int radiusShell: displayMetrics.radiusShell
    readonly property int radiusCard: displayMetrics.radiusCard
    readonly property int radiusCardMd: displayMetrics.radiusCardMedium
    readonly property int radiusCardSm: displayMetrics.radiusCardSmall
    readonly property int radiusControl: displayMetrics.radiusControl
    readonly property int radiusSetupCard: displayMetrics.radiusCardMedium
    readonly property int radiusPill: 999
    readonly property int borderStrong: displayMetrics.focusBorderWidth
    readonly property int dividerStrong: displayMetrics.dividerWidth
    readonly property int healthPillWidth: 126
    readonly property int healthPillHeight: 72
    readonly property int footerButtonWidth: 164
    readonly property int footerButtonHeight: displayMetrics.buttonHeight
    readonly property int controlHeight: displayMetrics.buttonHeight
    readonly property int minimumTouchTarget: displayMetrics.minimumTouchTarget
    readonly property int animationShort: 220
    readonly property real cardShadowOpacity: 0.08
}
