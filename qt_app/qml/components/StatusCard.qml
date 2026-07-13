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
        spacing: root.compact ? 5 : 8

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
                font.pixelSize: root.compact ? 11 : 12
                font.weight: root.theme.weightStrong
                renderType: Text.NativeRendering
                elide: Text.ElideRight
                maximumLineCount: 1
                Layout.fillWidth: true
                Layout.minimumWidth: 0
            }
        }

        Text {
            text: root.value.length > 0 ? root.value : root.title
            color: root.theme.text
            font.family: root.theme.displayFont
            font.pixelSize: root.compact ? 19 : 22
            font.weight: root.theme.weightHeavy
            wrapMode: Text.WordWrap
            renderType: Text.NativeRendering
            maximumLineCount: root.compact ? 1 : 2
            elide: Text.ElideRight
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }

        Text {
            visible: root.message.length > 0
            text: root.message
            color: root.theme.textMuted
            font.family: root.theme.bodyFont
            font.pixelSize: 13
            font.weight: root.theme.weightRegular
            wrapMode: Text.WordWrap
            maximumLineCount: root.compact ? 2 : 3
            elide: Text.ElideRight
            Layout.fillWidth: true
            Layout.minimumWidth: 0
        }
    }
}
