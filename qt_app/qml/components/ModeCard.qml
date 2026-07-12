import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: root
    required property QtObject theme
    required property string title
    required property string description
    property bool selected: false

    implicitHeight: 152

    contentItem: ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        Text {
            text: root.title
            color: root.selected ? "#ffffff" : root.theme.text
            font.family: root.theme.displayFont
            font.pixelSize: 28
            font.weight: root.theme.weightStrong
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
        }

        Text {
            text: root.description
            color: root.selected ? "#ffffff" : root.theme.textSecondary
            font.family: root.theme.bodyFont
            font.pixelSize: 18
            font.weight: root.theme.weightRegular
            wrapMode: Text.WordWrap
            horizontalAlignment: Text.AlignHCenter
            Layout.fillWidth: true
        }
    }

    background: Rectangle {
        radius: root.theme.radiusCard
        border.width: root.theme.borderStrong
        border.color: root.selected ? "#1753c7" : root.theme.text
        color: root.selected ? "#1f6bff" : root.theme.surface
    }
}
