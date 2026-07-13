import QtQuick
import QtQuick.Controls

Button {
    id: root
    required property QtObject theme
    property string tone: "neutral"

    implicitHeight: 50
    implicitWidth: 148
    leftPadding: 18
    rightPadding: 18
    font.family: root.theme.displayFont
    font.pixelSize: 18
    font.weight: root.theme.weightStrong
    hoverEnabled: true

    readonly property color borderColorValue: {
        if (!root.enabled) return root.theme.borderMuted
        if (root.tone === "danger") return root.theme.errorStrong
        if (root.tone === "success") return root.theme.successStrong
        if (root.tone === "primary") return root.theme.primaryStrong
        return root.theme.borderMuted
    }

    readonly property color fillColor: {
        if (!root.enabled) return root.theme.mutedFill
        if (root.down) return "#F3F6FA"
        if (root.hovered) return "#FBFCFE"
        return root.theme.surface
    }

    readonly property color textColor: {
        if (!root.enabled) return root.theme.unavailable
        if (root.tone === "danger") return root.theme.errorStrong
        if (root.tone === "success") return root.theme.successStrong
        if (root.tone === "primary") return root.theme.primaryStrong
        return root.theme.text
    }

    contentItem: Text {
        text: root.text
        color: root.textColor
        font: root.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        renderType: Text.NativeRendering
    }

    background: Rectangle {
        radius: root.theme.radiusControl
        color: root.fillColor
        border.width: 1
        border.color: root.borderColorValue

        Rectangle {
            anchors.fill: parent
            anchors.topMargin: 1
            radius: parent.radius
            color: "transparent"
            border.width: root.visualFocus ? 2 : 0
            border.color: "#C5DAFF"
            opacity: root.visualFocus ? 1.0 : 0.0
        }
    }
}
