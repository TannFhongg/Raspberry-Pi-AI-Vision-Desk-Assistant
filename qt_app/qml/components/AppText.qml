import QtQuick

Text {
    id: root
    required property QtObject theme
    property string role: "body"
    property bool decorative: false
    property bool forceQtRendering: false

    color: root.theme.text
    font.family: root.decorative ? root.theme.displayFont : root.theme.bodyFont
    font.pixelSize: root.theme.fontSizeForRole(root.role)
    font.weight: root.decorative ? root.theme.weightHeavy
                                 : root.role === "button" || root.role === "status"
                                   ? root.theme.weightStrong : root.theme.weightRegular
    font.hintingPreference: root.theme.hintingPreference
    renderType: root.forceQtRendering ? Text.QtRendering : root.theme.textRenderType
    lineHeightMode: Text.ProportionalHeight
    lineHeight: root.theme.lineHeightForRole(root.role)
}
