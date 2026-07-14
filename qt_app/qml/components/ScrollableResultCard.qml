import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: root
    required property QtObject theme
    required property string title
    Layout.minimumWidth: 0
    property string note: ""
    property string html: ""
    property bool emphasizeError: false
    property bool emphasizeQueued: false
    property int titlePixelSize: 30
    property int notePixelSize: 15
    property int bodyPixelSize: 18
    property string contentFontFamily: root.theme.bodyFont
    property bool navigationFocused: false
    readonly property color accentColor: root.emphasizeError ? root.theme.errorStrong
                                       : root.emphasizeQueued ? root.theme.warningStrong
                                       : root.theme.primaryStrong
    readonly property color surfaceColor: root.emphasizeError ? root.theme.errorCardFill
                                        : root.emphasizeQueued ? root.theme.warningFill
                                        : root.theme.surface
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

    function scrollBy(delta) {
        var flickable = scrollView.contentItem
        if (!flickable || flickable.contentY === undefined)
            return
        var maximum = Math.max(0, flickable.contentHeight - flickable.height)
        flickable.contentY = Math.max(0, Math.min(maximum, flickable.contentY + delta))
    }

    ContentCard {
        anchors.fill: parent
        theme: root.theme
        padding: 20
        navigationFocused: root.navigationFocused
        fillColor: root.surfaceColor
        borderColor: root.emphasizeError ? "#F0BABA"
                     : root.emphasizeQueued ? "#F1D38C"
                     : root.theme.borderSoft

        ColumnLayout {
            anchors.fill: parent
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Rectangle {
                    visible: root.emphasizeError || root.emphasizeQueued
                    Layout.preferredWidth: 8
                    Layout.preferredHeight: 8
                    radius: 4
                    color: root.accentColor
                }

                Text {
                    text: root.title
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: root.titlePixelSize
                    font.weight: root.theme.weightHeavy
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    renderType: Text.NativeRendering
                }
            }

            Text {
                visible: root.note.length > 0
                text: root.note
                color: root.accentColor
                font.family: root.theme.bodyFont
                font.pixelSize: root.notePixelSize
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            ScrollView {
                id: scrollView
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

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
                    leftPadding: 0
                    rightPadding: 4
                    topPadding: 0
                    bottomPadding: 0
                }
            }
        }
    }
}
