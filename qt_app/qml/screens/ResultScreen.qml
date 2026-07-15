import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    function handleNavigation(action) {
        if (action === "up") {
            answerCard.scrollBy(-150)
            return true
        }
        if (action === "down") {
            answerCard.scrollBy(150)
            return true
        }
        if (action === "select" || action === "back") {
            root.controller.clearResult()
            return true
        }
        return false
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        RowLayout {
            Layout.fillWidth: true

            Text {
                text: "Result"
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
                value: root.controller.selectedModeLabel
                tone: root.controller.resultState === "ERROR" ? "error"
                      : root.controller.resultState === "RETRY_PENDING" ? "warning"
                      : "success"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            spacing: 12

            ColumnLayout {
                Layout.preferredWidth: root.theme.resultImagePanelWidth
                Layout.minimumWidth: root.theme.resultImagePanelWidth
                Layout.maximumWidth: root.theme.resultImagePanelWidth
                Layout.fillHeight: true
                spacing: 12

                ContentCard {
                    theme: root.theme
                    padding: 14
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        Text {
                            text: "Captured image"
                            color: root.theme.text
                            font.family: root.theme.bodyFont
                            font.pixelSize: root.theme.fontCardTitle
                            font.weight: root.theme.weightHeavy
                            Layout.fillWidth: true
                        }

                        Rectangle {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            radius: root.theme.radiusControl
                            color: root.theme.surfaceMuted
                            clip: true

                            Image {
                                anchors.fill: parent
                                fillMode: Image.PreserveAspectFit
                                cache: false
                                visible: root.controller.resultPreviewRevision > 0
                                source: "image://visiondesk/result/latest?rev=" + root.controller.resultPreviewRevision
                            }

                            Text {
                                anchors.centerIn: parent
                                width: parent.width * 0.72
                                visible: root.controller.resultPreviewRevision === 0
                                text: "No preview image was retained for this result."
                                color: root.theme.textMuted
                                font.family: root.theme.bodyFont
                                font.pixelSize: root.theme.fontSecondaryBody
                                horizontalAlignment: Text.AlignHCenter
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }

                ScrollableResultCard {
                    theme: root.theme
                    title: "Additional detail"
                    note: ""
                    html: root.controller.resultDetailVisible
                          ? root.controller.resultDetailHtml
                          : "<p class='answer-empty'>No additional detail available.</p>"
                    titlePixelSize: root.theme.fontCardTitle
                    bodyPixelSize: root.theme.fontSecondaryBody
                    notePixelSize: root.theme.fontCaption
                    Layout.fillWidth: true
                    Layout.preferredHeight: 188
                }
            }

            ScrollableResultCard {
                id: answerCard
                theme: root.theme
                title: root.controller.resultTitle
                note: root.controller.resultNote
                html: root.controller.resultHtml
                emphasizeError: root.controller.resultState === "ERROR"
                emphasizeQueued: root.controller.resultState === "RETRY_PENDING"
                titlePixelSize: root.theme.fontPageTitle
                bodyPixelSize: root.theme.fontResultContent
                notePixelSize: root.theme.fontCaption
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 0
                navigationFocused: true
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: root.theme.footerHeight
            spacing: 12

            SecondaryButton {
                theme: root.theme
                text: "Home"
                onClicked: root.controller.clearResult()
            }

            NavigationHint {
                theme: root.theme
                text: "UP/DOWN Scroll  ·  SELECT New Capture  ·  BACK Home"
                Layout.fillWidth: true
            }

            PrimaryButton {
                theme: root.theme
                tone: "success"
                text: "New Capture"
                onClicked: root.controller.clearResult()
            }
        }
    }
}
