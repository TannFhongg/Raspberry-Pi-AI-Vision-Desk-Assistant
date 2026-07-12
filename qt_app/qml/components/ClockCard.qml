import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    required property QtObject theme

    width: 252
    height: 138
    radius: 30
    color: root.theme.surface
    border.width: root.theme.borderStrong
    border.color: root.theme.text

    property string timeText: ""
    property string dayText: ""

    function refreshClock() {
        const now = new Date()
        root.timeText = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        root.dayText = now.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" })
    }

    Component.onCompleted: refreshClock()

    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: root.refreshClock()
    }

    ColumnLayout {
        anchors.centerIn: parent
        spacing: 6

        Text {
            text: root.timeText
            font.family: root.theme.displayFont
            font.pixelSize: 36
            font.weight: root.theme.weightStrong
            color: root.theme.text
            Layout.alignment: Qt.AlignHCenter
        }

        Text {
            text: root.dayText
            font.family: root.theme.displayFont
            font.pixelSize: 28
            font.weight: root.theme.weightStrong
            color: root.theme.text
            Layout.alignment: Qt.AlignHCenter
        }
    }
}

