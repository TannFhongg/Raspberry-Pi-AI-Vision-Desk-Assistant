import QtQuick
import QtQuick.Layouts

Item {
    id: root
    required property QtObject theme
    required property var controller

    implicitHeight: headerRow.implicitHeight

    RowLayout {
        id: headerRow
        anchors.fill: parent
        spacing: 14

        BrandLogo {
            theme: root.theme
            compact: true
            Layout.alignment: Qt.AlignVCenter
            Layout.preferredWidth: 250
            Layout.minimumWidth: 0
            Layout.maximumWidth: 250
        }

        Item {
            Layout.fillWidth: true
            Layout.minimumWidth: 10
            Layout.preferredWidth: 10
        }

        AppStatusBadge {
            theme: root.theme
            text: root.controller.globalStatusText
            tone: root.controller.globalStatusTone
            Layout.alignment: Qt.AlignVCenter
            Layout.maximumWidth: 330
        }
    }
}
