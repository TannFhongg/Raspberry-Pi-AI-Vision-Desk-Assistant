import QtQuick
import QtQuick.Layouts

Item {
    id: root
    required property QtObject theme
    property int padding: 18
    property color fillColor: root.theme.surface
    property color borderColor: root.theme.borderSoft
    property int radius: root.theme.radiusSetupCard
    property bool elevated: true
    property bool clipContent: false
    default property alias contentData: contentHost.data
    Layout.minimumWidth: 0

    Rectangle {
        visible: root.elevated
        anchors.fill: surface
        anchors.leftMargin: 3
        anchors.topMargin: 5
        radius: root.radius + 2
        color: Qt.rgba(
            root.theme.cardShadow.r,
            root.theme.cardShadow.g,
            root.theme.cardShadow.b,
            root.theme.cardShadowOpacity
        )
    }

    Rectangle {
        id: surface
        anchors.fill: parent
        radius: root.radius
        color: root.fillColor
        border.width: 1
        border.color: root.borderColor

        Behavior on color {
            ColorAnimation { duration: root.theme.animationShort }
        }
    }

    Item {
        id: contentHost
        anchors.fill: surface
        anchors.margins: root.padding
        clip: root.clipContent
    }
}
