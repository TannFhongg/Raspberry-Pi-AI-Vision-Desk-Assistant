import QtQuick

Item {
    id: root
    required property QtObject theme
    required property var controller

    implicitHeight: header.implicitHeight

    AppHeader {
        id: header
        anchors.fill: parent
        theme: root.theme
        controller: root.controller
    }
}
