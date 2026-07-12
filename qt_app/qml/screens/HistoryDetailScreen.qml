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
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            spacing: 18

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: root.hasSelection ? root.controller.selectedHistoryModeLabel : "Saved Result"
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 44
                    font.weight: root.theme.weightHeavy
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }

                Text {
                    visible: root.hasSelection
                    text: root.controller.selectedHistoryCreatedAt
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: 18
                    font.weight: root.theme.weightRegular
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
            }

            Rectangle {
                visible: root.hasSelection
                radius: root.theme.radiusPill
                border.width: root.theme.borderStrong
                border.color: root.theme.text
                color: root.theme.surface
                implicitWidth: statusText.implicitWidth + 34
                implicitHeight: statusText.implicitHeight + 22

                Text {
                    id: statusText
                    anchors.centerIn: parent
                    text: root.controller.selectedHistoryStatusLabel
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 18
                    font.weight: root.theme.weightStrong
                }
            }
        }

        Rectangle {
            visible: root.hasSelection
            Layout.fillWidth: true
            radius: root.theme.radiusCardSm
            border.width: 2
            border.color: "#c6d0da"
            color: "#f8fafc"
            implicitHeight: metadataFlow.implicitHeight + 28

            Flow {
                id: metadataFlow
                anchors.fill: parent
                anchors.margins: 14
                spacing: 14

                Text {
                    visible: root.controller.selectedHistoryModelUsed.length > 0
                    text: "Model: " + root.controller.selectedHistoryModelUsed
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: 16
                    font.weight: root.theme.weightRegular
                }

                Text {
                    visible: root.controller.selectedHistoryDurationLabel.length > 0
                    text: "Time: " + root.controller.selectedHistoryDurationLabel
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: 16
                    font.weight: root.theme.weightRegular
                }

                Text {
                    visible: root.controller.selectedHistoryRetryStatus.length > 0
                    text: "Retry: " + root.controller.selectedHistoryRetryStatus
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: 16
                    font.weight: root.theme.weightRegular
                }

                Text {
                    visible: root.controller.selectedHistoryErrorSummary.length > 0
                    text: "Error: " + root.controller.selectedHistoryErrorSummary
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: 16
                    font.weight: root.theme.weightRegular
                }
            }
        }

        RowLayout {
            visible: root.hasSelection
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 20

            ScrollableResultCard {
                theme: root.theme
                title: root.controller.selectedHistoryTitle || "Result"
                note: root.controller.selectedHistoryNote
                html: root.controller.selectedHistoryResultHtml
                emphasizeError: root.controller.selectedHistoryStatus === "error"
                emphasizeQueued: root.controller.selectedHistoryStatus === "queued"
                titlePixelSize: 30
                bodyPixelSize: 18
                notePixelSize: 15
                Layout.fillWidth: true
                Layout.fillHeight: true
            }

            ScrollableResultCard {
                theme: root.theme
                title: "Additional Detail"
                note: ""
                html: root.controller.selectedHistoryDetailHtml
                titlePixelSize: 30
                bodyPixelSize: 16
                notePixelSize: 14
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }

        Rectangle {
            visible: !root.hasSelection
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: root.theme.radiusCard
            border.width: root.theme.borderStrong
            border.color: root.theme.text
            color: root.theme.surface

            Text {
                anchors.centerIn: parent
                width: parent.width * 0.7
                text: "This saved result is no longer available."
                color: root.theme.textSecondary
                font.family: root.theme.displayFont
                font.pixelSize: 30
                font.weight: root.theme.weightStrong
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            ActionButton {
                theme: root.theme
                text: "BACK"
                onClicked: root.controller.goBack()
            }

            Item {
                Layout.fillWidth: true
            }

            ActionButton {
                theme: root.theme
                destructive: true
                text: "DELETE RESULT"
                implicitWidth: 220
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
        padding: 0
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            radius: root.theme.radiusCard
            border.width: root.theme.borderStrong
            border.color: root.theme.text
            color: root.theme.surface
        }

        contentItem: ColumnLayout {
            spacing: 20

            Text {
                text: "Delete this saved result?"
                color: root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 30
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Text {
                text: "This removes the selected history item only."
                color: root.theme.textSecondary
                font.family: root.theme.bodyFont
                font.pixelSize: 19
                font.weight: root.theme.weightRegular
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item {
                    Layout.fillWidth: true
                }

                ActionButton {
                    theme: root.theme
                    text: "CANCEL"
                    onClicked: deleteItemDialog.close()
                }

                ActionButton {
                    theme: root.theme
                    destructive: true
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
