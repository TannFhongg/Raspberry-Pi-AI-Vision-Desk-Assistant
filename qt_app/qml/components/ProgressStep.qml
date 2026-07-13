import QtQuick
import QtQuick.Layouts

Item {
    id: root
    required property QtObject theme
    required property string label
    property string state: "pending"

    readonly property bool complete: root.state === "complete"
    readonly property bool active: root.state === "active"
    readonly property bool failed: root.state === "error"
    readonly property color accent: root.failed ? root.theme.errorStrong
                                  : root.complete ? root.theme.successStrong
                                  : root.active ? root.theme.primaryStrong
                                  : root.theme.borderMuted

    implicitHeight: stepColumn.implicitHeight

    ColumnLayout {
        id: stepColumn
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width
        spacing: 8

        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 38
            Layout.preferredHeight: 38
            radius: 19
            color: root.complete || root.active || root.failed ? root.accent : root.theme.surface
            border.width: 1
            border.color: root.accent

            Text {
                anchors.centerIn: parent
                text: root.complete ? "OK" : root.failed ? "!" : ""
                color: root.theme.surface
                font.family: root.theme.displayFont
                font.pixelSize: root.complete ? 13 : 20
                font.weight: root.theme.weightHeavy
                renderType: Text.NativeRendering
            }
        }

        Text {
            text: root.label
            color: root.active ? root.theme.text : root.theme.textMuted
            font.family: root.theme.bodyFont
            font.pixelSize: 14
            font.weight: root.active ? root.theme.weightStrong : root.theme.weightRegular
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            maximumLineCount: 2
            elide: Text.ElideRight
            renderType: Text.NativeRendering
        }
    }
}
