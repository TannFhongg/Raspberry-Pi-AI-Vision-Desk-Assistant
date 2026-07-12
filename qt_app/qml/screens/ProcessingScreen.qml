import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    RowLayout {
        anchors.fill: parent
        spacing: 30

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: root.theme.radiusCard
            border.width: root.theme.borderStrong
            border.color: root.theme.text
            color: root.theme.surface

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 34
                spacing: 28

                Text {
                    text: root.controller.processingTitle
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 64
                    font.weight: root.theme.weightHeavy
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }

                Text {
                    text: root.controller.processingSubtitle
                    color: root.theme.textSecondary
                    font.family: root.theme.displayFont
                    font.pixelSize: 28
                    font.weight: root.theme.weightStrong
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }

                ProgressSteps {
                    theme: root.theme
                    model: root.controller.progressStepsModel
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                }
            }
        }

        Rectangle {
            Layout.preferredWidth: 300
            Layout.fillHeight: true
            radius: root.theme.radiusCard
            border.width: root.theme.borderStrong
            border.color: root.controller.processingStatusTone === "error" ? root.theme.error
                         : root.controller.processingStatusTone === "queued" ? root.theme.warning
                         : root.controller.processingStatusTone === "done" ? root.theme.success
                         : root.theme.primary
            color: root.controller.processingStatusTone === "error" ? root.theme.errorFill
                 : root.controller.processingStatusTone === "queued" ? root.theme.warningFill
                 : root.controller.processingStatusTone === "done" ? root.theme.successFill
                 : root.theme.surface

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 24
                spacing: 18

                Text {
                    text: "Current Mode"
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 26
                    font.weight: root.theme.weightHeavy
                    Layout.fillWidth: true
                }

                Text {
                    text: root.controller.processingModeLabel
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 24
                    font.weight: root.theme.weightStrong
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 28
                    border.width: root.theme.borderStrong
                    border.color: parent.parent.border.color
                    color: parent.parent.color

                    Text {
                        anchors.centerIn: parent
                        width: parent.width - 36
                        text: root.controller.processingStatusMessage
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 26
                        font.weight: root.theme.weightStrong
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
}

