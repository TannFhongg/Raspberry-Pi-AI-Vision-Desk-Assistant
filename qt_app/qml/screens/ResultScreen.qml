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
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 24

            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 18

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.theme.radiusCard
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
                        width: parent.width * 0.7
                        visible: root.controller.resultPreviewRevision === 0
                        text: "No preview image was retained for this result."
                        color: root.theme.textSecondary
                        font.family: root.theme.bodyFont
                        font.pixelSize: 20
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                    }
                }

                ScrollableResultCard {
                    theme: root.theme
                    title: "Additional Detail"
                    note: ""
                    html: root.controller.resultDetailVisible
                          ? root.controller.resultDetailHtml
                          : "<p class='answer-empty'>No additional detail available.</p>"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 210
                }
            }

            ScrollableResultCard {
                theme: root.theme
                title: root.controller.resultTitle
                note: root.controller.resultNote
                html: root.controller.resultHtml
                emphasizeError: root.controller.resultState === "ERROR"
                emphasizeQueued: root.controller.resultState === "RETRY_PENDING"
                Layout.fillWidth: true
                Layout.fillHeight: true
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            Item { Layout.fillWidth: true }

            ActionButton {
                theme: root.theme
                text: "HOME"
                onClicked: root.controller.clearResult()
            }

            ActionButton {
                theme: root.theme
                primary: true
                text: "NEW CAPTURE"
                onClicked: root.controller.clearResult()
            }
        }
    }
}

