import QtQuick
import QtQuick.Layouts

InfoCard {
    id: root
    required property string title
    property string value: ""
    property string message: ""
    property string tone: "info"
    property string eyebrow: ""
    property bool compact: false
    property bool showFullMessage: !root.compact

    padding: root.compact ? root.theme.spaceSm : root.theme.diagnosticCardPadding

    readonly property string normalizedTone: (root.tone || "").toLowerCase()
    readonly property color accentColor: {
        if (root.normalizedTone === "pass" || root.normalizedTone === "success" || root.normalizedTone === "healthy") return root.theme.successStrong
        if (root.normalizedTone === "fail" || root.normalizedTone === "danger" || root.normalizedTone === "error") return root.theme.errorStrong
        if (root.normalizedTone === "warning" || root.normalizedTone === "running") return root.theme.warningStrong
        return root.theme.primaryStrong
    }
    readonly property color toneFill: {
        if (root.normalizedTone === "pass" || root.normalizedTone === "success" || root.normalizedTone === "healthy") return root.theme.successFill
        if (root.normalizedTone === "fail" || root.normalizedTone === "danger" || root.normalizedTone === "error") return root.theme.errorFill
        if (root.normalizedTone === "warning" || root.normalizedTone === "running") return root.theme.warningFill
        return root.theme.primarySoft
    }

    fillColor: root.toneFill
    borderColor: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.20)

    ColumnLayout {
        id: statusContent
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        spacing: root.compact ? 5 : root.theme.diagnosticCardSpacing

        RowLayout {
            spacing: 7

            Rectangle {
                Layout.preferredWidth: 9
                Layout.preferredHeight: 9
                radius: 5
                color: root.accentColor
            }

            Text {
                text: root.eyebrow.length > 0 ? root.eyebrow : root.title
                color: root.accentColor
                font.family: root.theme.bodyFont
                font.pixelSize: root.theme.fontCaption
                font.weight: root.theme.weightStrong
                renderType: root.theme.textRenderType
                font.hintingPreference: root.theme.hintingPreference
                elide: Text.ElideRight
                maximumLineCount: 1
                Layout.fillWidth: true
                Layout.minimumWidth: 0
            }
        }

        Text {
            text: root.value.length > 0 ? root.value : root.title
            color: root.theme.text
            font.family: root.theme.bodyFont
            font.pixelSize: root.compact ? root.theme.fontBody : root.theme.fontCardTitle
            font.weight: root.theme.weightHeavy
            wrapMode: Text.Wrap
            renderType: root.theme.textRenderType
            font.hintingPreference: root.theme.hintingPreference
            maximumLineCount: root.compact ? 1 : 2147483647
            elide: root.compact ? Text.ElideRight : Text.ElideNone
            lineHeightMode: Text.ProportionalHeight
            lineHeight: root.theme.headingLineHeight
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }

        Text {
            id: descriptionText
            objectName: root.objectName.length > 0 ? root.objectName + "Description" : ""
            visible: root.message.length > 0
            text: root.message
            color: root.theme.textMuted
            font.family: root.theme.bodyFont
            font.pixelSize: root.compact ? root.theme.fontCaption : root.theme.fontSecondaryBody
            font.weight: root.theme.weightRegular
            font.hintingPreference: root.theme.hintingPreference
            renderType: root.theme.textRenderType
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            maximumLineCount: root.showFullMessage ? 2147483647 : 2
            elide: root.showFullMessage ? Text.ElideNone : Text.ElideRight
            lineHeightMode: Text.ProportionalHeight
            lineHeight: root.theme.bodyLineHeight
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }
    }
}
