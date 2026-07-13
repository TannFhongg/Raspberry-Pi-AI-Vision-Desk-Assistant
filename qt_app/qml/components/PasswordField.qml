import QtQuick
import QtQuick.Controls

InputField {
    id: root
    property bool revealed: false
    property bool toggleEnabled: true

    secret: !root.revealed
    trailingText: root.toggleEnabled ? (root.revealed ? "HIDE" : "SHOW") : ""

    MouseArea {
        anchors.right: parent.right
        anchors.rightMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        width: root.toggleEnabled ? 52 : 0
        height: parent.height
        enabled: root.toggleEnabled
        onClicked: root.revealed = !root.revealed
    }
}
