import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    required property QtObject theme
    required property string label
    required property string value
    required property string state
    required property string message

    implicitWidth: 154
    implicitHeight: 56
    radius: root.theme.radiusPill
    border.width: root.theme.borderStrong
    border.color: root.theme.text
    color: root.theme.surface

    Text {
        anchors.centerIn: parent
        text: root.label
        color: root.theme.text
        font.family: root.theme.displayFont
        font.pixelSize: 22
        font.weight: root.theme.weightHeavy
        renderType: Text.NativeRendering
    }

    ToolTip.visible: hoverHandler.hovered
    ToolTip.text: {
        const normalizedValue = (root.value || "").trim()
        const normalizedMessage = (root.message || "").trim()
        if (normalizedValue && normalizedMessage) {
            return normalizedValue + " - " + normalizedMessage
        }
        if (normalizedValue) {
            return normalizedValue
        }
        return normalizedMessage
    }

    HoverHandler {
        id: hoverHandler
    }
}
