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

            Text {
                text: "Current Mode"
                color: root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 26
                font.weight: root.theme.weightHeavy
            }

            Rectangle {
                radius: root.theme.radiusPill
                border.width: root.theme.borderStrong
                border.color: root.theme.text
                color: root.theme.surface
                implicitHeight: 52
                implicitWidth: 280

                Text {
                    anchors.centerIn: parent
                    text: root.controller.selectedModeLabel.toUpperCase()
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 24
                    font.weight: root.theme.weightStrong
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 28

            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: root.theme.surfaceMuted
                radius: root.theme.radiusCard
                border.width: 2
                border.color: root.theme.primary
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

                Rectangle {
                    anchors.fill: parent
                    visible: !root.controller.cameraPreviewAvailable
                    color: "#d9d9d9"

                    ColumnLayout {
                        anchors.centerIn: parent
                        width: parent.width * 0.7
                        spacing: 12

                        Text {
                            text: root.controller.cameraPreviewTitle
                            color: root.theme.text
                            font.family: root.theme.displayFont
                            font.pixelSize: 40
                            font.weight: root.theme.weightStrong
                            horizontalAlignment: Text.AlignHCenter
                            Layout.fillWidth: true
                        }

                        Text {
                            text: root.controller.cameraPreviewMessage
                            color: root.theme.textSecondary
                            font.family: root.theme.bodyFont
                            font.pixelSize: 20
                            wrapMode: Text.WordWrap
                            horizontalAlignment: Text.AlignHCenter
                            Layout.fillWidth: true
                        }
                    }
                }
            }

            Rectangle {
                Layout.preferredWidth: 300
                Layout.fillHeight: true
                radius: root.theme.radiusCard
                border.width: root.theme.borderStrong
                border.color: root.theme.text
                color: root.theme.surface

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 22
                    spacing: 16

                    Text {
                        text: "Camera Analysis"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 28
                        font.weight: root.theme.weightHeavy
                        Layout.fillWidth: true
                    }

                    Repeater {
                        model: root.controller.cameraAnalysisModel.count

                        delegate: StatusPill {
                            required property int index
                            property var itemData: root.controller.cameraAnalysisModel.get(index)
                            theme: root.theme
                            label: itemData.key || ""
                            value: itemData.label || ""
                            tone: itemData.status || "unknown"
                            Layout.fillWidth: true
                        }
                    }

                    Item {
                        Layout.fillHeight: true
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            Item { Layout.fillWidth: true }

            ActionButton {
                theme: root.theme
                text: "BACK"
                onClicked: root.controller.goBack()
            }

            ActionButton {
                theme: root.theme
                primary: true
                text: "CAPTURE"
                enabled: !root.controller.applicationState.startsWith("CAPTUR")
                onClicked: root.controller.capture()
            }
        }
    }
}
