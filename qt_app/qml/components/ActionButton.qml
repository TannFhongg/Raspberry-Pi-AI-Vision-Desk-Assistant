import QtQuick
import QtQuick.Controls

Button {
    id: root
    required property QtObject theme
    property bool primary: false
    property bool destructive: false

    font.family: root.theme.displayFont
    font.pixelSize: 24
    font.weight: root.theme.weightStrong
    implicitWidth: root.theme.footerButtonWidth
    implicitHeight: root.theme.footerButtonHeight

    contentItem: Text {
        text: root.text
        color: root.enabled ? root.theme.text : root.theme.unavailable
        font: root.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        renderType: Text.NativeRendering
    }

    background: Rectangle {
        radius: root.theme.radiusPill
        border.width: root.theme.borderStrong
        border.color: root.enabled ? root.theme.text : "#bbc4ce"
        color: {
            if (!root.enabled) return root.theme.mutedFill
            if (root.destructive) return root.theme.errorFill
            if (root.primary) return "#38c653"
            return root.theme.surface
        }
    }
}

