import QtQuick

Item {
    id: root
    required property QtObject theme
    property bool primary: false
    property bool destructive: false
    property alias text: button.text
    property alias enabled: button.enabled
    signal clicked()

    implicitWidth: root.theme.footerButtonWidth
    implicitHeight: root.theme.footerButtonHeight

    PrimaryButton {
        id: button
        anchors.fill: parent
        theme: root.theme
        tone: root.destructive ? "danger" : root.primary ? "success" : "secondary"
        onClicked: root.clicked()
    }
}
