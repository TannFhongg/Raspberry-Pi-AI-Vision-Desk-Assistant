import QtQuick

Item {
    id: root
    required property QtObject theme
    property string text: "UP/DOWN Navigate  ·  SELECT Confirm  ·  BACK Return"

    implicitWidth: hintText.implicitWidth
    implicitHeight: hintText.implicitHeight

    AppText {
        id: hintText
        theme: root.theme
        role: "caption"
        anchors.centerIn: parent
        text: root.text
        color: root.theme.textMuted
        font.weight: root.theme.weightStrong
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
    }
}
