import QtQuick
import QtQuick.Controls

TextField {
    id: root
    required property QtObject theme
    property string leadingText: ""
    property string trailingText: ""
    property bool secret: false
    property bool invalid: false

    implicitHeight: 52
    leftPadding: root.leadingText.length > 0 ? 52 : 18
    rightPadding: root.trailingText.length > 0 ? 54 : 18
    color: root.theme.text
    font.family: root.theme.bodyFont
    font.pixelSize: root.theme.fontButton
    font.weight: root.theme.weightRegular
    placeholderTextColor: "#98A2B3"
    selectionColor: root.theme.primaryStrong
    selectedTextColor: root.theme.surface
    echoMode: root.secret ? TextInput.Password : TextInput.Normal
    selectByMouse: true

    background: Rectangle {
        radius: root.theme.radiusControl
        color: root.theme.surface
        border.width: 1
        border.color: root.invalid
                      ? root.theme.errorStrong
                      : root.activeFocus
                        ? root.theme.primaryStrong
                        : root.theme.borderSoft
    }

    Rectangle {
        visible: root.leadingText.length > 0
        width: 24
        height: 24
        radius: 12
        color: root.activeFocus ? root.theme.primarySoft : root.theme.mutedFill
        anchors.left: parent.left
        anchors.leftMargin: 16
        anchors.verticalCenter: parent.verticalCenter

        Text {
            anchors.centerIn: parent
            text: root.leadingText
            color: root.theme.primaryStrong
            font.family: root.theme.bodyFont
            font.pixelSize: root.theme.fontCaption
            font.weight: root.theme.weightHeavy
            renderType: root.theme.textRenderType
        }
    }

    Text {
        visible: root.trailingText.length > 0
        text: root.trailingText
        color: root.invalid ? root.theme.errorStrong : root.theme.textMuted
        font.family: root.theme.bodyFont
        font.pixelSize: root.theme.fontCaption
        font.weight: root.theme.weightStrong
        anchors.right: parent.right
        anchors.rightMargin: 16
        anchors.verticalCenter: parent.verticalCenter
        renderType: root.theme.textRenderType
    }
}
