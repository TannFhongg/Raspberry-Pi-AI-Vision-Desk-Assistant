import QtQuick

Item {
    id: root
    required property QtObject theme
    property string tone: "secondary"
    property bool navigationFocused: false
    property alias text: button.text
    property alias enabled: button.enabled
    signal clicked()

    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    PrimaryButton {
        id: button
        anchors.fill: parent
        theme: root.theme
        tone: root.tone === "neutral" ? "secondary" : root.tone
        navigationFocused: root.navigationFocused
        onClicked: root.clicked()
    }
}
