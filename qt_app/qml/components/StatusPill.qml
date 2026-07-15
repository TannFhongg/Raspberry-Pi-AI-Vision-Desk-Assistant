import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    required property QtObject theme
    required property string label
    required property string value
    required property string tone

    radius: root.theme.radiusPill
    border.width: root.theme.borderStrong
    border.color: {
        if (root.tone === "pass" || root.tone === "healthy") return "#2d9b5d"
        if (root.tone === "warning" || root.tone === "running") return "#d69c24"
        if (root.tone === "fail" || root.tone === "error") return "#d14343"
        return "#bbc4ce"
    }
    color: {
        if (root.tone === "pass" || root.tone === "healthy") return root.theme.successFill
        if (root.tone === "warning" || root.tone === "running") return root.theme.warningFill
        if (root.tone === "fail" || root.tone === "error") return root.theme.errorFill
        return root.theme.mutedFill
    }

    implicitHeight: 56
    implicitWidth: 170

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 2

        Text {
            text: root.label
            color: root.theme.text
            font.family: root.theme.bodyFont
            font.pixelSize: root.theme.fontCaption
            font.weight: root.theme.weightStrong
            Layout.alignment: Qt.AlignHCenter
        }

        Text {
            text: root.value
            color: root.theme.text
            font.family: root.theme.bodyFont
            font.pixelSize: root.theme.fontCardTitle
            font.weight: root.theme.weightHeavy
            Layout.alignment: Qt.AlignHCenter
        }
    }
}

