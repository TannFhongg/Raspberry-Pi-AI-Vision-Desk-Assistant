import QtQuick
import QtQuick.Layouts

Item {
    id: root
    required property QtObject theme
    property int padding: 18
    property color fillColor: root.theme.surfaceElevated
    property color borderColor: root.theme.borderSoft
    property int radius: root.theme.radiusSetupCard
    property bool elevated: true
    default property alias contentData: contentLayout.data
    Layout.minimumWidth: 0

    implicitWidth: Math.max(120, contentLayout.implicitWidth + (root.padding * 2) + 8)
    implicitHeight: Math.max(80, contentLayout.implicitHeight + (root.padding * 2) + 8)

    Rectangle {
        visible: root.elevated
        anchors.left: card.left
        anchors.right: card.right
        anchors.top: card.top
        anchors.bottom: card.bottom
        anchors.leftMargin: 4
        anchors.rightMargin: -2
        anchors.topMargin: 6
        anchors.bottomMargin: -6
        radius: root.radius + 2
        color: Qt.rgba(0.06, 0.09, 0.16, 0.08)
    }

    Rectangle {
        id: card
        anchors.fill: parent
        radius: root.radius
        color: root.fillColor
        border.width: 1
        border.color: root.borderColor
    }

    ColumnLayout {
        id: contentLayout
        anchors.fill: card
        anchors.margins: root.padding
        spacing: 10
    }
}
