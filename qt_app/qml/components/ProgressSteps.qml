import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property QtObject theme
    required property var model
    spacing: 28

    Repeater {
        model: root.model

        delegate: RowLayout {
            spacing: 18
            Layout.fillWidth: true

            Rectangle {
                width: 38
                height: 38
                radius: 19
                border.width: root.theme.borderStrong
                border.color: model.state === "error" ? root.theme.error : root.theme.text
                color: "transparent"

                Rectangle {
                    anchors.centerIn: parent
                    width: 18
                    height: 18
                    radius: 9
                    visible: model.state === "active" || model.state === "error"
                    color: model.state === "error" ? root.theme.error : root.theme.primary
                }

                Text {
                    anchors.centerIn: parent
                    visible: model.state === "complete"
                    text: "✓"
                    color: root.theme.success
                    font.family: root.theme.displayFont
                    font.pixelSize: 20
                    font.weight: root.theme.weightHeavy
                }
            }

            Text {
                text: model.label
                color: root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 32
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
            }
        }
    }
}

