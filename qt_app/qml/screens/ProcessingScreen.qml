import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        RowLayout {
            Layout.fillWidth: true

            Text {
                text: "Processing"
                color: root.theme.text
                font.family: root.theme.bodyFont
                font.pixelSize: root.theme.fontPageTitle
                font.weight: root.theme.weightHeavy
                Layout.fillWidth: true
                renderType: root.theme.textRenderType
            }

            StatusChip {
                theme: root.theme
                label: "Mode"
                value: root.controller.processingModeLabel
                tone: "info"
            }
        }

        ContentCard {
            theme: root.theme
            padding: 28
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0

            ColumnLayout {
                anchors.fill: parent
                spacing: 20

                ColumnLayout {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 620
                    Layout.fillWidth: true
                    spacing: 6

                    Text {
                        text: root.controller.processingTitle
                        color: root.theme.text
                        font.family: root.theme.bodyFont
                        font.pixelSize: root.theme.fontBrand
                        font.weight: root.theme.weightHeavy
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        text: root.controller.processingSubtitle
                        color: root.theme.textMuted
                        font.family: root.theme.bodyFont
                        font.pixelSize: root.theme.fontBody
                        font.weight: root.theme.weightRegular
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }

                PipelineProgress {
                    theme: root.theme
                    backendState: root.controller.applicationState
                    tone: root.controller.processingStatusTone
                    Layout.fillWidth: true
                    Layout.preferredHeight: 94
                }

                Item { Layout.fillHeight: true }

                StatusCard {
                    theme: root.theme
                    padding: 20
                    fillColor: root.controller.processingStatusTone === "error" ? root.theme.errorFill
                               : root.controller.processingStatusTone === "queued" ? root.theme.warningFill
                               : root.theme.primarySoft
                    borderColor: root.controller.processingStatusTone === "error" ? "#F0BABA"
                                 : root.controller.processingStatusTone === "queued" ? "#F1D38C"
                                 : "#C9DCFF"
                    Layout.alignment: Qt.AlignHCenter
                    Layout.maximumWidth: 620
                    Layout.fillWidth: true
                    title: "Live pipeline status"
                    eyebrow: root.controller.processingStatusTone === "queued" ? "Retry queued" : "In progress"
                    value: root.controller.processingStatusMessage
                    message: "Progress reflects the active capture and analysis worker."
                    tone: root.controller.processingStatusTone

                    Rectangle {
                        visible: root.controller.processingStatusTone === "active"
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 9
                        Layout.preferredHeight: 9
                        radius: 5
                        color: root.theme.primaryStrong

                        SequentialAnimation on opacity {
                            running: root.controller.processingStatusTone === "active"
                            loops: Animation.Infinite
                            NumberAnimation { to: 0.28; duration: 650 }
                            NumberAnimation { to: 1.0; duration: 650 }
                        }
                    }
                }

                Item { Layout.fillHeight: true }
            }
        }
    }
}
