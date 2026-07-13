import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    required property QtObject theme
    required property string label
    property string value: ""
    property string tone: "info"

    readonly property string normalizedTone: (root.tone || "").toLowerCase()
    readonly property color accentColor: {
        if (root.normalizedTone === "pass" || root.normalizedTone === "success" || root.normalizedTone === "healthy") return root.theme.successStrong
        if (root.normalizedTone === "fail" || root.normalizedTone === "danger" || root.normalizedTone === "error") return root.theme.errorStrong
        if (root.normalizedTone === "warning" || root.normalizedTone === "running") return root.theme.warningStrong
        return root.theme.primaryStrong
    }
    readonly property color fillColor: {
        if (root.normalizedTone === "pass" || root.normalizedTone === "success" || root.normalizedTone === "healthy") return root.theme.successFill
        if (root.normalizedTone === "fail" || root.normalizedTone === "danger" || root.normalizedTone === "error") return root.theme.errorFill
        if (root.normalizedTone === "warning" || root.normalizedTone === "running") return root.theme.warningFill
        return root.theme.primarySoft
    }

    radius: root.theme.radiusPill
    color: root.fillColor
    border.width: 1
    border.color: Qt.rgba(accentColor.r, accentColor.g, accentColor.b, 0.28)
    implicitHeight: 34
    implicitWidth: chipRow.implicitWidth + 20

    RowLayout {
        id: chipRow
        anchors.centerIn: parent
        spacing: 8

        Rectangle {
            Layout.preferredWidth: 8
            Layout.preferredHeight: 8
            radius: 4
            color: root.accentColor
        }

        Text {
            text: root.value.length > 0 ? root.label + " " + root.value : root.label
            color: root.accentColor
            font.family: root.theme.bodyFont
            font.pixelSize: 14
            font.weight: root.theme.weightStrong
            renderType: Text.NativeRendering
        }
    }
}
