import QtQuick

Item {
    id: root
    required property QtObject theme
    property bool compact: false

    implicitWidth: logoRow.implicitWidth
    implicitHeight: logoRow.implicitHeight
    width: implicitWidth
    height: implicitHeight

    Row {
        id: logoRow
        spacing: 0

        AppText {
            theme: root.theme
            role: "brand"
            decorative: true
            text: "Vision"
            color: root.theme.text
            font.pixelSize: root.compact ? root.theme.fontBrand : Math.round(root.theme.fontBrand * 1.25)
        }

        AppText {
            theme: root.theme
            role: "brand"
            decorative: true
            text: "Desk"
            color: root.theme.logoBlue
            font.pixelSize: root.compact ? root.theme.fontBrand : Math.round(root.theme.fontBrand * 1.25)
        }
    }
}
