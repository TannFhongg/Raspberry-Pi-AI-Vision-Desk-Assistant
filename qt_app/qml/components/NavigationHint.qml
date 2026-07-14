import QtQuick

Item {
    id: root
    required property QtObject theme
    property string text: "UP/DOWN Navigate  ·  SELECT Confirm  ·  BACK Return"

    implicitWidth: hintText.implicitWidth
    implicitHeight: hintText.implicitHeight

    Text {
        id: hintText
        anchors.centerIn: parent
        text: root.text
        color: root.theme.textMuted
        font.family: root.theme.bodyFont
        font.pixelSize: 14
        font.weight: root.theme.weightStrong
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        renderType: Text.NativeRendering
    }
}
