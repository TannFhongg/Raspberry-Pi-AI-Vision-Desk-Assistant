import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property QtObject theme
    required property string title
    property string note: ""
    property string html: ""
    property bool emphasizeError: false
    property bool emphasizeQueued: false

    radius: root.theme.radiusCard
    border.width: root.theme.borderStrong
    border.color: root.emphasizeError ? "#d14343" : root.emphasizeQueued ? root.theme.primary : root.theme.text
    color: root.theme.surface

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 26
        spacing: 14

        Text {
            text: root.title
            color: root.theme.text
            font.family: root.theme.displayFont
            font.pixelSize: 42
            font.weight: root.theme.weightStrong
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        Text {
            visible: root.note.length > 0
            text: root.note
            color: root.emphasizeError ? "#ac2b2b" : root.emphasizeQueued ? root.theme.primaryDark : "#5f6975"
            font.family: root.theme.displayFont
            font.pixelSize: 19
            font.weight: root.theme.weightStrong
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            TextArea {
                text: root.html
                readOnly: true
                textFormat: TextEdit.RichText
                wrapMode: TextEdit.Wrap
                font.family: root.theme.displayFont
                font.pixelSize: 28
                font.weight: root.theme.weightRegular
                color: root.theme.text
                background: null
                selectByMouse: false
            }
        }
    }
}

