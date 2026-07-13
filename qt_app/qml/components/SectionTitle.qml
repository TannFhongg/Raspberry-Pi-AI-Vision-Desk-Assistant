import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property QtObject theme
    required property string title
    property string subtitle: ""

    spacing: 2

    Text {
        text: root.title
        color: root.theme.text
        font.family: root.theme.displayFont
        font.pixelSize: 30
        font.weight: root.theme.weightHeavy
        renderType: Text.NativeRendering
        Layout.fillWidth: true
    }

    Text {
        visible: root.subtitle.length > 0
        text: root.subtitle
        color: root.theme.textMuted
        font.family: root.theme.bodyFont
        font.pixelSize: 14
        font.weight: root.theme.weightRegular
        wrapMode: Text.WordWrap
        maximumLineCount: 1
        elide: Text.ElideRight
        Layout.fillWidth: true
    }
}
