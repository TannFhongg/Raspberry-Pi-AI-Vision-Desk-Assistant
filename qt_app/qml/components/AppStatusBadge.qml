import QtQuick
import QtQuick.Layouts

Item {
    id: root
    required property QtObject theme
    property string text: "Starting"
    property string tone: "info"

    readonly property color accent: {
        if (root.tone === "success") return root.theme.successStrong
        if (root.tone === "error") return root.theme.errorStrong
        if (root.tone === "warning") return root.theme.warningStrong
        return root.theme.primaryStrong
    }
    implicitWidth: statusRow.implicitWidth + 20
    implicitHeight: 42

    Rectangle {
        anchors.fill: parent
        radius: root.theme.radiusPill
        color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.12)
        border.width: 1
        border.color: Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.28)
    }

    RowLayout {
        id: statusRow
        anchors.centerIn: parent
        spacing: 8

        Rectangle {
            Layout.preferredWidth: 10
            Layout.preferredHeight: 10
            radius: 5
            color: root.accent
        }

        Text {
            text: root.text
            color: root.theme.text
            font.family: root.theme.bodyFont
            font.pixelSize: 16
            font.weight: root.theme.weightStrong
            renderType: Text.NativeRendering
            wrapMode: Text.NoWrap
        }
    }
}
