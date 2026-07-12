import QtQuick

Item {
    id: root
    required property QtObject theme

    implicitWidth: logoRow.implicitWidth
    implicitHeight: logoRow.implicitHeight
    width: implicitWidth
    height: implicitHeight

    Row {
        id: logoRow
        spacing: 0

        Text {
            text: "Vision"
            color: root.theme.text
            font.family: root.theme.displayFont
            font.pixelSize: 60
            font.weight: root.theme.weightHeavy
            renderType: Text.NativeRendering
        }

        Text {
            text: "Desk"
            color: root.theme.logoBlue
            font.family: root.theme.displayFont
            font.pixelSize: 60
            font.weight: root.theme.weightHeavy
            renderType: Text.NativeRendering
        }
    }
}
