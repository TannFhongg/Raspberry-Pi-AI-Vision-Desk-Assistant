import QtQuick
import QtQuick.Controls

TextField {
    id: root
    required property QtObject theme
    property bool secret: false

    implicitHeight: 54
    leftPadding: 22
    rightPadding: 22
    color: root.theme.text
    font.family: root.theme.displayFont
    font.pixelSize: 20
    font.weight: root.theme.weightStrong
    placeholderTextColor: "#aeb4be"
    selectionColor: root.theme.primaryStrong
    selectedTextColor: root.theme.surface
    echoMode: root.secret ? TextInput.Password : TextInput.Normal
    selectByMouse: true

    background: Rectangle {
        radius: root.theme.radiusPill
        color: root.theme.surface
        border.width: root.theme.borderStrong
        border.color: root.activeFocus ? root.theme.primary : root.theme.text
    }
}
