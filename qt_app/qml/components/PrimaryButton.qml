import QtQuick
import QtQuick.Controls

Button {
    id: root
    required property QtObject theme
    property string tone: "primary"
    property bool navigationFocused: false

    implicitHeight: root.theme.controlHeight
    implicitWidth: 164
    leftPadding: 18
    rightPadding: 18
    font.family: root.theme.bodyFont
    font.pixelSize: root.theme.fontButton
    font.weight: root.theme.weightStrong
    hoverEnabled: true

    readonly property color fillColor: {
        if (!root.enabled) return root.theme.borderSoft
        if (root.tone === "secondary" || root.tone === "neutral") return root.theme.surface
        if (root.tone === "success") return root.theme.successStrong
        if (root.tone === "danger") return root.theme.errorStrong
        return root.theme.primaryStrong
    }

    readonly property color borderColorValue: {
        if (!root.enabled) return root.theme.borderMuted
        if (root.tone === "secondary" || root.tone === "neutral") return root.theme.borderMuted
        if (root.tone === "success") return "#23964A"
        if (root.tone === "danger") return "#C83E3E"
        return root.theme.primaryDark
    }

    readonly property color textColor: !root.enabled ? root.theme.unavailable
                                     : root.tone === "secondary" || root.tone === "neutral" ? root.theme.text
                                     : root.theme.surface

    contentItem: Text {
        text: root.text
        color: root.textColor
        font.family: root.font.family
        font.pixelSize: root.font.pixelSize
        font.weight: root.font.weight
        font.hintingPreference: root.theme.hintingPreference
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        renderType: root.theme.textRenderType
    }

    background: Rectangle {
        radius: root.theme.radiusControl
        color: {
            if (!root.enabled) return root.fillColor
            if (root.down) return Qt.darker(root.fillColor, 1.06)
            if (root.hovered) return Qt.lighter(root.fillColor, 1.04)
            return root.fillColor
        }
        border.width: 1
        border.color: root.borderColorValue

        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 1
            radius: parent.radius
            color: "transparent"
            border.width: root.visualFocus || root.navigationFocused ? root.theme.focusBorderWidth : 0
            border.color: "#9DC2FF"
            opacity: root.visualFocus || root.navigationFocused ? 1.0 : 0.0
        }
    }
}
