import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller
    property int navigationIndex: 0

    function handleNavigation(action) {
        var retryAvailable = root.controller.canRetry
        if ((action === "up" || action === "down") && retryAvailable) {
            root.navigationIndex = root.navigationIndex === 0 ? 1 : 0
            return true
        }
        if (action === "select") {
            if (root.navigationIndex === 1 && retryAvailable)
                root.controller.retry()
            else
                root.controller.clearResult()
            return true
        }
        if (action === "back") {
            root.controller.clearResult()
            return true
        }
        return action === "up" || action === "down"
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        RowLayout {
            Layout.fillWidth: true

            Text {
                text: "Something needs attention"
                color: root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 34
                font.weight: root.theme.weightHeavy
                Layout.fillWidth: true
                renderType: Text.NativeRendering
            }

            StatusChip {
                theme: root.theme
                label: "Code"
                value: root.controller.errorCode || "UNKNOWN_ERROR"
                tone: "error"
            }
        }

        ContentCard {
            theme: root.theme
            padding: 28
            fillColor: "#FFFDFD"
            borderColor: "#F2D1D1"
            Layout.fillWidth: true
            Layout.preferredHeight: 480
            Layout.maximumHeight: 480

            ColumnLayout {
                anchors.fill: parent
                spacing: 18

                StatusCard {
                    theme: root.theme
                    padding: 20
                    title: "Capture error"
                    eyebrow: "Action needed"
                    value: root.controller.errorTitle
                    message: root.controller.errorMessage
                    tone: "error"
                    Layout.fillWidth: true
                }

                StatusCard {
                    theme: root.theme
                    padding: 20
                    fillColor: root.theme.warningFill
                    borderColor: "#F1D38C"
                    Layout.fillWidth: true
                    title: "What you can do"
                    eyebrow: "Recovery"
                    value: root.controller.canRetry ? "Try the capture again" : "Review device setup"
                    message: root.controller.canRetry
                        ? "Check the camera and network connection, then retry. VisionDesk keeps technical traces out of this screen."
                        : "Review the device setup and resolve the issue before trying again. VisionDesk keeps technical traces out of this screen."
                    tone: "warning"
                }

                Item { Layout.fillHeight: true }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            SecondaryButton {
                theme: root.theme
                text: "BACK"
                navigationFocused: root.navigationIndex === 0
                onClicked: root.controller.clearResult()
            }

            NavigationHint {
                theme: root.theme
                text: root.controller.canRetry
                      ? "UP/DOWN Choose  ·  SELECT Confirm  ·  BACK Home"
                      : "SELECT or BACK to return Home"
                Layout.fillWidth: true
            }

            PrimaryButton {
                theme: root.theme
                tone: "success"
                text: "RETRY"
                visible: root.controller.canRetry
                enabled: root.controller.canRetry
                navigationFocused: root.navigationIndex === 1 && root.controller.canRetry
                onClicked: root.controller.retry()
            }
        }
    }
}
