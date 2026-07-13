import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    readonly property bool hasSelection: root.controller.hasSelectedHistoryItem

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: root.hasSelection ? root.controller.selectedHistoryModeLabel : "Saved result"
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 34
                    font.weight: root.theme.weightHeavy
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    renderType: Text.NativeRendering
                }

                Text {
                    visible: root.hasSelection
                    text: root.controller.selectedHistoryCreatedAt
                    color: root.theme.textMuted
                    font.family: root.theme.bodyFont
                    font.pixelSize: 15
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }

            StatusChip {
                visible: root.hasSelection
                theme: root.theme
                label: "Status"
                value: root.controller.selectedHistoryStatusLabel
                tone: root.controller.selectedHistoryStatus === "error" ? "error"
                      : root.controller.selectedHistoryStatus === "queued" ? "warning"
                      : "success"
            }
        }

        ContentCard {
            visible: root.hasSelection
            theme: root.theme
            padding: 14
            fillColor: root.theme.primarySoft
            borderColor: "#C9DCFF"
            Layout.fillWidth: true
            Layout.preferredHeight: metadataFlow.implicitHeight + 28

            Flow {
                id: metadataFlow
                anchors.fill: parent
                spacing: 16

                Text {
                    visible: root.controller.selectedHistoryModelUsed.length > 0
                    text: "Model: " + root.controller.selectedHistoryModelUsed
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: 14
                }

                Text {
                    visible: root.controller.selectedHistoryDurationLabel.length > 0
                    text: "Time: " + root.controller.selectedHistoryDurationLabel
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: 14
                }

                Text {
                    visible: root.controller.selectedHistoryRetryStatus.length > 0
                    text: "Retry: " + root.controller.selectedHistoryRetryStatus
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: 14
                }

                Text {
                    visible: root.controller.selectedHistoryErrorSummary.length > 0
                    text: "Note: " + root.controller.selectedHistoryErrorSummary
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: 14
                }
            }
        }

        RowLayout {
            visible: root.hasSelection
            Layout.fillWidth: true
            Layout.preferredHeight: 385
            Layout.maximumHeight: 385
            spacing: 12

            ScrollableResultCard {
                theme: root.theme
                title: root.controller.selectedHistoryTitle || "Result"
                note: root.controller.selectedHistoryNote
                html: root.controller.selectedHistoryResultHtml
                emphasizeError: root.controller.selectedHistoryStatus === "error"
                emphasizeQueued: root.controller.selectedHistoryStatus === "queued"
                titlePixelSize: 28
                bodyPixelSize: 17
                notePixelSize: 14
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 0
            }

            ScrollableResultCard {
                theme: root.theme
                title: "Additional detail"
                note: ""
                html: root.controller.selectedHistoryDetailHtml
                titlePixelSize: 23
                bodyPixelSize: 15
                notePixelSize: 13
                Layout.preferredWidth: 360
                Layout.minimumWidth: 360
                Layout.maximumWidth: 360
                Layout.fillHeight: true
            }
        }

        ContentCard {
            visible: !root.hasSelection
            theme: root.theme
            padding: 24
            Layout.fillWidth: true
            Layout.fillHeight: true

            ColumnLayout {
                anchors.centerIn: parent
                width: Math.min(parent.width * 0.58, 500)
                spacing: 8

                Text {
                    text: "Saved result unavailable"
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 30
                    font.weight: root.theme.weightHeavy
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }

                Text {
                    text: "This record may have been removed during retention cleanup."
                    color: root.theme.textMuted
                    font.family: root.theme.bodyFont
                    font.pixelSize: 16
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            SecondaryButton {
                theme: root.theme
                text: "BACK"
                onClicked: root.controller.goBack()
            }

            Item { Layout.fillWidth: true }

            SecondaryButton {
                theme: root.theme
                tone: "danger"
                text: "DELETE RESULT"
                implicitWidth: 190
                enabled: root.hasSelection
                onClicked: deleteItemDialog.open()
            }
        }
    }

    Dialog {
        id: deleteItemDialog
        anchors.centerIn: parent
        modal: true
        focus: true
        width: 500
        padding: 24
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            radius: root.theme.radiusSetupCard
            border.width: 1
            border.color: root.theme.borderSoft
            color: root.theme.surface
        }

        contentItem: ColumnLayout {
            spacing: 16

            Text {
                text: "Delete this saved result?"
                color: root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 28
                font.weight: root.theme.weightHeavy
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Text {
                text: "This removes the selected history item only."
                color: root.theme.textMuted
                font.family: root.theme.bodyFont
                font.pixelSize: 16
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item { Layout.fillWidth: true }

                SecondaryButton {
                    theme: root.theme
                    text: "CANCEL"
                    onClicked: deleteItemDialog.close()
                }

                PrimaryButton {
                    theme: root.theme
                    tone: "danger"
                    text: "DELETE"
                    onClicked: {
                        var entryId = root.controller.selectedHistoryId
                        deleteItemDialog.close()
                        root.controller.deleteHistoryItem(entryId)
                    }
                }
            }
        }
    }
}
