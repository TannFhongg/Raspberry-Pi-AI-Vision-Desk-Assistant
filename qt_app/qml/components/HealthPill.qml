import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property QtObject theme
    required property string label
    required property string value
    required property string state
    required property string message
    required property string valueSize

    width: root.theme.healthPillWidth
    height: root.theme.healthPillHeight
    radius: root.theme.radiusPill
    border.width: root.theme.borderStrong
    border.color: {
        if (root.state === "healthy") return "#2d9b5d"
        if (root.state === "warning") return "#d69c24"
        if (root.state === "error") return "#d14343"
        return "#bbc4ce"
    }
    color: {
        if (root.state === "healthy") return root.theme.successFill
        if (root.state === "warning") return root.theme.warningFill
        if (root.state === "error") return root.theme.errorFill
        return root.theme.mutedFill
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 4

        Text {
            text: root.label
            color: root.theme.text
            font.family: root.theme.displayFont
            font.pixelSize: 17
            font.weight: root.theme.weightStrong
            horizontalAlignment: Text.AlignHCenter
            Layout.alignment: Qt.AlignHCenter
        }

        Text {
            text: root.value
            color: root.theme.text
            font.family: root.theme.displayFont
            font.pixelSize: root.valueSize === "very-long" ? 18 : root.valueSize === "long" ? 22 : 28
            font.weight: root.theme.weightHeavy
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            Layout.alignment: Qt.AlignHCenter
        }
    }

    ToolTip.visible: pillArea.containsMouse
    ToolTip.text: root.message

    HoverHandler {
        id: pillArea
    }
}
