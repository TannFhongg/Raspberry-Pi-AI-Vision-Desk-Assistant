import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property QtObject theme
    required property var model
    spacing: 28

    Repeater {
        model: root.model.count

        delegate: RowLayout {
            required property int index
            property var itemData: root.model.get(index)
            spacing: 18
            Layout.fillWidth: true

            Rectangle {
                width: 38
                height: 38
                radius: 19
                border.width: root.theme.borderStrong
                border.color: itemData.state === "error" ? root.theme.error : root.theme.text
                color: "transparent"

                Rectangle {
                    anchors.centerIn: parent
                    width: 18
                    height: 18
                    radius: 9
                    visible: itemData.state === "active" || itemData.state === "error"
                    color: itemData.state === "error" ? root.theme.error : root.theme.primary
                }

                Text {
                    anchors.centerIn: parent
                    visible: itemData.state === "complete"
                    text: "OK"
                    color: root.theme.success
                    font.family: root.theme.bodyFont
                    font.pixelSize: root.theme.fontCardTitle
                    font.weight: root.theme.weightHeavy
                }
            }

            Text {
                text: itemData.label || ""
                color: root.theme.text
                font.family: root.theme.bodyFont
                font.pixelSize: root.theme.fontPageTitle
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
            }
        }
    }
}
