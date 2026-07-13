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
            spacing: 12

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: "Camera"
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 34
                    font.weight: root.theme.weightHeavy
                    renderType: Text.NativeRendering
                }

                Text {
                    text: "Frame your subject, then capture when the preview is clear."
                    color: root.theme.textMuted
                    font.family: root.theme.bodyFont
                    font.pixelSize: 15
                    font.weight: root.theme.weightRegular
                    renderType: Text.NativeRendering
                }
            }

            StatusChip {
                theme: root.theme
                label: "Mode"
                value: root.controller.selectedModeLabel
                tone: "info"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: 480
            Layout.maximumHeight: 480
            spacing: 12

            ContentCard {
                theme: root.theme
                padding: 14
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 0

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10

                    RowLayout {
                        Layout.fillWidth: true

                        Text {
                            text: "Live preview"
                            color: root.theme.text
                            font.family: root.theme.displayFont
                            font.pixelSize: 22
                            font.weight: root.theme.weightHeavy
                            Layout.fillWidth: true
                            renderType: Text.NativeRendering
                        }

                        StatusChip {
                            theme: root.theme
                            label: root.controller.cameraPreviewAvailable ? "Camera" : "Camera"
                            value: root.controller.cameraPreviewAvailable ? "Ready" : "Waiting"
                            tone: root.controller.cameraPreviewAvailable ? "success" : "warning"
                        }
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
                            visible: root.controller.cameraPreviewAvailable
                            source: root.controller.cameraPreviewRevision > 0
                                    ? "image://visiondesk/camera/live?seq=" + root.controller.cameraPreviewRevision
                                    : ""
                        }

                        ColumnLayout {
                            anchors.centerIn: parent
                            width: parent.width * 0.66
                            visible: !root.controller.cameraPreviewAvailable
                            spacing: 8

                            Rectangle {
                                Layout.alignment: Qt.AlignHCenter
                                Layout.preferredWidth: 54
                                Layout.preferredHeight: 42
                                radius: 14
                                color: root.theme.primarySoft

                                Text {
                                    anchors.centerIn: parent
                                    text: "CAM"
                                    color: root.theme.primaryStrong
                                    font.family: root.theme.displayFont
                                    font.pixelSize: 14
                                    font.weight: root.theme.weightHeavy
                                }
                            }

                            Text {
                                text: root.controller.cameraPreviewTitle
                                color: root.theme.text
                                font.family: root.theme.displayFont
                                font.pixelSize: 28
                                font.weight: root.theme.weightHeavy
                                horizontalAlignment: Text.AlignHCenter
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                            }

                            Text {
                                text: root.controller.cameraPreviewMessage
                                color: root.theme.textMuted
                                font.family: root.theme.bodyFont
                                font.pixelSize: 16
                                horizontalAlignment: Text.AlignHCenter
                                Layout.fillWidth: true
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.preferredWidth: 300
                Layout.minimumWidth: 300
                Layout.maximumWidth: 300
                Layout.fillHeight: true
                spacing: 12

                StatusCard {
                    theme: root.theme
                    padding: 16
                    fillColor: root.theme.primarySoft
                    borderColor: "#C9DCFF"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 118
                    title: "Current mode"
                    eyebrow: "Capture"
                    value: root.controller.selectedModeLabel
                    message: "The selected mode controls the AI workflow after capture."
                    tone: "info"
                }

                ContentCard {
                    theme: root.theme
                    padding: 14
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        Text {
                            text: "Camera status"
                            color: root.theme.text
                            font.family: root.theme.displayFont
                            font.pixelSize: 21
                            font.weight: root.theme.weightHeavy
                            Layout.fillWidth: true
                        }

                        GridLayout {
                            columns: 1
                            columnSpacing: 8
                            rowSpacing: 8
                            Layout.fillWidth: true

                            Repeater {
                                model: root.controller.cameraAnalysisModel.count

                                delegate: StatusCard {
                                    required property int index
                                    property var itemData: root.controller.cameraAnalysisModel.get(index)
                                    theme: root.theme
                                    padding: 11
                                    title: itemData.key || "Camera"
                                    eyebrow: itemData.key || "Camera"
                                    value: itemData.label || "Waiting"
                                    message: ""
                                    tone: itemData.status || "info"
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 72
                                }
                            }
                        }

                        Item { Layout.fillHeight: true }
                    }
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

            PrimaryButton {
                theme: root.theme
                tone: "success"
                text: "CAPTURE"
                enabled: !root.controller.applicationState.startsWith("CAPTUR")
                onClicked: root.controller.capture()
            }
        }
    }
}
