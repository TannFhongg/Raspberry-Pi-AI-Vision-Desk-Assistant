import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    readonly property bool hasSelection: root.controller.hasSelectedHistoryItem

    function handleNavigation(action) {
        if (deleteItemDialog.visible) {
            if (action === "back")
                deleteItemDialog.close()
            return true
        }
        if (action === "up") {
            selectedResultCard.scrollBy(-150)
            return true
        }
        if (action === "down") {
            selectedResultCard.scrollBy(150)
            return true
        }
        if (action === "select" || action === "back") {
            root.controller.goBack()
            return true
        }
        return false
    }

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
                    font.family: root.theme.bodyFont
                    font.pixelSize: root.theme.fontPageTitle
                    font.weight: root.theme.weightHeavy
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                    renderType: root.theme.textRenderType
                }

                Text {
                    visible: root.hasSelection
                    text: root.controller.selectedHistoryCreatedAt
                    color: root.theme.textMuted
                    font.family: root.theme.bodyFont
                    font.pixelSize: root.theme.fontCaption
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
                    font.pixelSize: root.theme.fontCaption
                }

                Text {
                    visible: root.controller.selectedHistoryDurationLabel.length > 0
                    text: "Time: " + root.controller.selectedHistoryDurationLabel
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: root.theme.fontCaption
                }

                Text {
                    visible: root.controller.selectedHistoryRetryStatus.length > 0
                    text: "Retry: " + root.controller.selectedHistoryRetryStatus
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: root.theme.fontCaption
                }

                Text {
                    visible: root.controller.selectedHistoryErrorSummary.length > 0
                    text: "Note: " + root.controller.selectedHistoryErrorSummary
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: root.theme.fontCaption
                }
            }
        }

        RowLayout {
            visible: root.hasSelection
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            spacing: 12

            ScrollableResultCard {
                id: selectedResultCard
                theme: root.theme
                title: root.controller.selectedHistoryTitle || "Result"
                note: root.controller.selectedHistoryNote
                html: root.controller.selectedHistoryResultHtml
                emphasizeError: root.controller.selectedHistoryStatus === "error"
                emphasizeQueued: root.controller.selectedHistoryStatus === "queued"
                titlePixelSize: root.theme.fontPageTitle
                bodyPixelSize: root.theme.fontResultContent
                notePixelSize: root.theme.fontCaption
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 0
                navigationFocused: true
            }

            ScrollableResultCard {
                theme: root.theme
                title: "Additional detail"
                note: ""
                html: root.controller.selectedHistoryDetailHtml
                titlePixelSize: root.theme.fontCardTitle
                bodyPixelSize: root.theme.fontSecondaryBody
                notePixelSize: root.theme.fontCaption
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
                    font.family: root.theme.bodyFont
                    font.pixelSize: root.theme.fontPageTitle
                    font.weight: root.theme.weightHeavy
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }

                Text {
                    text: "This record may have been removed during retention cleanup."
                    color: root.theme.textMuted
                    font.family: root.theme.bodyFont
                    font.pixelSize: root.theme.fontSecondaryBody
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: root.theme.footerHeight
            spacing: 12

            SecondaryButton {
                theme: root.theme
                text: "Back"
                navigationFocused: true
                onClicked: root.controller.goBack()
            }

            NavigationHint {
                theme: root.theme
                text: "UP/DOWN Scroll  ·  SELECT or BACK Return"
                Layout.fillWidth: true
            }

            SecondaryButton {
                theme: root.theme
                tone: "danger"
                text: "Delete Result"
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
                font.family: root.theme.bodyFont
                font.pixelSize: root.theme.fontCardTitle
                font.weight: root.theme.weightHeavy
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Text {
                text: "This removes the selected history item only."
                color: root.theme.textMuted
                font.family: root.theme.bodyFont
                font.pixelSize: root.theme.fontSecondaryBody
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item { Layout.fillWidth: true }

                SecondaryButton {
                    theme: root.theme
                    text: "Cancel"
                    onClicked: deleteItemDialog.close()
                }

                PrimaryButton {
                    theme: root.theme
                    tone: "danger"
                    text: "Delete"
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
