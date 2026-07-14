import QtQuick

Item {
    id: root
    required property QtObject theme
    property string profile: "document"
    property bool showCrosshair: true
    property bool zoomActive: false

    Rectangle {
        id: guide
        anchors.centerIn: parent
        width: root.profile === "computer_screen" ? parent.width * 0.84 : parent.width * 0.72
        height: root.profile === "document" ? parent.height * 0.78 : parent.height * 0.68
        color: "transparent"
        border.width: 3
        border.color: Qt.rgba(1, 1, 1, 0.86)
        radius: root.profile === "document" ? 8 : 18
    }

    Repeater {
        visible: root.profile === "diagram"
        model: 2
        delegate: Rectangle {
            width: 1
            height: guide.height
            x: guide.x + guide.width * ((index + 1) / 3)
            y: guide.y
            color: Qt.rgba(1, 1, 1, 0.55)
        }
    }

    Repeater {
        visible: root.profile === "diagram"
        model: 2
        delegate: Rectangle {
            width: guide.width
            height: 1
            x: guide.x
            y: guide.y + guide.height * ((index + 1) / 3)
            color: Qt.rgba(1, 1, 1, 0.55)
        }
    }

    Rectangle {
        visible: root.showCrosshair
        anchors.centerIn: parent
        width: 28
        height: 1
        color: Qt.rgba(1, 1, 1, 0.88)
    }
    Rectangle {
        visible: root.showCrosshair
        anchors.centerIn: parent
        width: 1
        height: 28
        color: Qt.rgba(1, 1, 1, 0.88)
    }

    Rectangle {
        visible: root.zoomActive
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 12
        radius: root.theme.radiusPill
        color: Qt.rgba(0.06, 0.09, 0.16, 0.76)
        width: zoomLabel.implicitWidth + 22
        height: 32
        Text {
            id: zoomLabel
            anchors.centerIn: parent
            text: "ZOOM REGION"
            color: "white"
            font.family: root.theme.bodyFont
            font.pixelSize: 13
            font.weight: root.theme.weightStrong
        }
    }
}
