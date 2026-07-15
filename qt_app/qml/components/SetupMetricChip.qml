import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: root
    required property QtObject theme
    required property string label
    required property string value
    property string state: "unavailable"
    property string message: ""

    readonly property string normalizedState: (root.state || "").toLowerCase()
    readonly property color accentColor: {
        if (root.normalizedState === "healthy" || root.normalizedState === "pass") return root.theme.successStrong
        if (root.normalizedState === "warning" || root.normalizedState === "running") return root.theme.warningStrong
        if (root.normalizedState === "error" || root.normalizedState === "fail") return root.theme.errorStrong
        return root.theme.primaryStrong
    }

    implicitWidth: 118
    implicitHeight: 54
    radius: root.theme.radiusControl
    color: root.theme.surface
    border.width: 1
    border.color: root.theme.borderSoft
    clip: true

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 12
        anchors.rightMargin: 12
        anchors.topMargin: 8
        anchors.bottomMargin: 8
        spacing: 8

        Rectangle {
            Layout.preferredWidth: 22
            Layout.preferredHeight: 22
            radius: 11
            color: Qt.rgba(root.accentColor.r, root.accentColor.g, root.accentColor.b, 0.14)

            Rectangle {
                anchors.centerIn: parent
                width: 8
                height: 8
                radius: 4
                color: root.accentColor
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1

            Text {
                text: root.label
                color: root.theme.textMuted
                font.family: root.theme.bodyFont
                font.pixelSize: root.theme.fontCaption
                font.weight: root.theme.weightStrong
                renderType: root.theme.textRenderType
                elide: Text.ElideRight
                maximumLineCount: 1
                Layout.fillWidth: true
                Layout.minimumWidth: 0
            }

            Text {
                text: root.value
                color: root.theme.text
                font.family: root.theme.bodyFont
                font.pixelSize: root.value.length >= 8 ? root.theme.fontCaption
                                : root.value.length >= 6 ? root.theme.fontSecondaryBody
                                : root.theme.fontBody
                font.weight: root.theme.weightHeavy
                renderType: root.theme.textRenderType
                elide: Text.ElideRight
                maximumLineCount: 1
                Layout.fillWidth: true
                Layout.minimumWidth: 0
            }
        }
    }

    ToolTip.visible: metricHover.hovered
    ToolTip.text: root.message

    HoverHandler {
        id: metricHover
    }
}
