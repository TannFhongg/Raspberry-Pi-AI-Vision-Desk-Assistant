import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: root
    required property QtObject theme
    required property string title
    property string subtitle: ""

    spacing: 2

    HeadingText {
        theme: root.theme
        text: root.title
        color: root.theme.text
        Layout.fillWidth: true
    }

    AppText {
        theme: root.theme
        role: "secondaryBody"
        visible: root.subtitle.length > 0
        text: root.subtitle
        color: root.theme.textMuted
        wrapMode: Text.WordWrap
        maximumLineCount: 2
        Layout.fillWidth: true
    }
}
