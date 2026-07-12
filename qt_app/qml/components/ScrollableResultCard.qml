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
    property int titlePixelSize: 36
    property int notePixelSize: 17
    property int bodyPixelSize: 21
    property string contentFontFamily: root.theme.bodyFont
    readonly property string styledHtml: {
        var bodyFont = (root.contentFontFamily || root.theme.bodyFont).replace(/'/g, "&apos;")
        var headingFont = (root.theme.displayFont || bodyFont).replace(/'/g, "&apos;")
        var bodySize = Math.max(14, root.bodyPixelSize)
        var heading3 = Math.round(bodySize * 1.22)
        var heading4 = Math.round(bodySize * 1.1)
        var heading5 = Math.round(bodySize * 1.04)
        return "<html><head><style>" +
               "body { margin: 0; font-family: '" + bodyFont + "'; font-size: " + bodySize + "px; font-weight: 600; color: " + root.theme.text + "; line-height: 1.28; }" +
               "h3, h4, h5 { margin: 0 0 10px 0; font-family: '" + headingFont + "'; font-weight: 800; line-height: 1.02; color: " + root.theme.text + "; }" +
               "h3 { font-size: " + heading3 + "px; }" +
               "h4 { font-size: " + heading4 + "px; }" +
               "h5 { font-size: " + heading5 + "px; }" +
               "p, ul, ol { margin: 0 0 10px 0; }" +
               "ul, ol { padding-left: 22px; }" +
               "li { margin: 0 0 6px 0; }" +
               ".answer-empty { color: " + root.theme.textSecondary + "; }" +
               "</style></head><body>" + root.html + "</body></html>"
    }

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
            font.pixelSize: root.titlePixelSize
            font.weight: root.theme.weightStrong
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        Text {
            visible: root.note.length > 0
            text: root.note
            color: root.emphasizeError ? "#ac2b2b" : root.emphasizeQueued ? root.theme.primaryDark : "#5f6975"
            font.family: root.theme.displayFont
            font.pixelSize: root.notePixelSize
            font.weight: root.theme.weightStrong
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            TextArea {
                text: root.styledHtml
                readOnly: true
                textFormat: TextEdit.RichText
                wrapMode: TextEdit.Wrap
                font.family: root.contentFontFamily
                font.pixelSize: root.bodyPixelSize
                font.weight: root.theme.weightRegular
                color: root.theme.text
                background: null
                selectByMouse: false
            }
        }
    }
}
