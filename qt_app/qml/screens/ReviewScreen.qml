import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    // GPIO/keyboard focus is intentionally limited to controls which are
    // actually visible and useful in the compact panel. Retake is available
    // by Back and by the persistent touch button in the footer.
    property int navigationIndex: 7
    property real reviewZoom: 1.0
    property bool cropEditing: true

    function focusOrder() {
        var actions = [0, 1, 2, 3, 4]
        if (root.controller.captureReview.perspectiveAvailable
                && !root.controller.captureReview.perspectiveActive)
            actions.push(5)
        if (root.controller.captureReview.perspectiveActive)
            actions.push(6)
        actions.push(7)
        return actions
    }

    function moveFocus(direction) {
        var actions = root.focusOrder()
        var current = actions.indexOf(root.navigationIndex)
        if (current < 0) current = actions.length - 1
        current = Math.max(0, Math.min(actions.length - 1, current + direction))
        root.navigationIndex = actions[current]
    }

    function startCropEditing() {
        // Return to an unscaled canvas before exposing drag handles so every
        // handle remains inside the usable touch area.
        root.reviewZoom = 1.0
        root.cropEditing = true
    }

    function zoomCanvas(delta) {
        root.cropEditing = false
        root.reviewZoom = Math.max(1.0, Math.min(2.0, root.reviewZoom + delta))
    }

    function handleNavigation(action) {
        if (action === "up") { root.moveFocus(-1); return true }
        if (action === "down") { root.moveFocus(1); return true }
        if (action === "select") {
            if (root.navigationIndex === 0) root.startCropEditing()
            else if (root.navigationIndex === 1) root.controller.captureReview.resetCrop()
            else if (root.navigationIndex === 2) root.zoomCanvas(-0.2)
            else if (root.navigationIndex === 3) root.zoomCanvas(0.2)
            else if (root.navigationIndex === 4) root.controller.captureReview.setAutoEnhance(!root.controller.captureReview.autoEnhanceActive)
            else if (root.navigationIndex === 5) root.controller.captureReview.acceptPerspective()
            else if (root.navigationIndex === 6) root.controller.captureReview.rejectPerspective()
            else root.controller.confirmReviewedImage()
            return true
        }
        if (action === "back") { root.controller.retakeCapture(); return true }
        return false
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            Layout.minimumHeight: 52
            spacing: 12

            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2

                Text {
                    text: "Review and adjust"
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 30
                    font.weight: root.theme.weightHeavy
                }
                Text {
                    text: "Task: " + root.controller.selectedModeLabel + "  •  Capture profile: " + root.controller.captureReview.captureProfileLabel
                    color: root.theme.textMuted
                    font.family: root.theme.bodyFont
                    font.pixelSize: 15
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    elide: Text.ElideRight
                }
            }

            StatusChip {
                theme: root.theme
                label: "Privacy"
                value: "Not sent yet"
                tone: "info"
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            spacing: 12

            ContentCard {
                theme: root.theme
                padding: 12
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: 0
                clipContent: true

                Item {
                    anchors.fill: parent
                    clip: true

                    ReviewImageCanvas {
                        id: reviewCanvas
                        width: parent.width
                        height: parent.height
                        scale: root.reviewZoom
                        transformOrigin: Item.Center
                        theme: root.theme
                        review: root.controller.captureReview
                        cropEditing: root.cropEditing
                    }
                }
            }

            ContentCard {
                theme: root.theme
                padding: 14
                Layout.preferredWidth: 344
                Layout.minimumWidth: 320
                Layout.maximumWidth: 344
                Layout.fillHeight: true
                Layout.minimumHeight: 0
                clipContent: true

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8

                    Text {
                        text: "Adjustments"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 21
                        font.weight: root.theme.weightHeavy
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 3

                        Text {
                            text: "Camera"
                            color: root.theme.text
                            font.family: root.theme.displayFont
                            font.pixelSize: 16
                            font.weight: root.theme.weightHeavy
                        }
                        Text {
                            text: "• " + root.controller.captureReview.autofocusSupportMessage
                            color: root.controller.captureReview.autofocusSupported ? root.theme.successStrong : root.theme.textMuted
                            font.family: root.theme.bodyFont
                            font.pixelSize: 13
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                        Text {
                            text: "• " + root.controller.captureReview.exposureSupportMessage
                            color: root.controller.captureReview.exposureSupported ? root.theme.successStrong : root.theme.textMuted
                            font.family: root.theme.bodyFont
                            font.pixelSize: 13
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }

                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: root.theme.borderSoft }

                    Text {
                        text: "Crop"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 16
                        font.weight: root.theme.weightHeavy
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        SecondaryButton {
                            theme: root.theme
                            text: "CROP"
                            implicitWidth: 0
                            Layout.minimumWidth: 0
                            Layout.fillWidth: true
                            navigationFocused: root.navigationIndex === 0
                            onClicked: root.startCropEditing()
                        }
                        SecondaryButton {
                            theme: root.theme
                            text: "RESET CROP"
                            implicitWidth: 0
                            Layout.minimumWidth: 0
                            Layout.fillWidth: true
                            navigationFocused: root.navigationIndex === 1
                            onClicked: root.controller.captureReview.resetCrop()
                        }
                    }

                    Text {
                        text: "Zoom"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 16
                        font.weight: root.theme.weightHeavy
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        SecondaryButton {
                            theme: root.theme
                            text: "ZOOM −"
                            implicitWidth: 0
                            Layout.minimumWidth: 0
                            Layout.fillWidth: true
                            navigationFocused: root.navigationIndex === 2
                            onClicked: root.zoomCanvas(-0.2)
                        }
                        SecondaryButton {
                            theme: root.theme
                            text: "ZOOM +"
                            implicitWidth: 0
                            Layout.minimumWidth: 0
                            Layout.fillWidth: true
                            navigationFocused: root.navigationIndex === 3
                            onClicked: root.zoomCanvas(0.2)
                        }
                    }

                    Text {
                        text: "Enhancement"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 16
                        font.weight: root.theme.weightHeavy
                    }
                    SecondaryButton {
                        theme: root.theme
                        text: root.controller.captureReview.autoEnhanceActive ? "AUTO-ENHANCE ON" : "AUTO-ENHANCE"
                        Layout.fillWidth: true
                        navigationFocused: root.navigationIndex === 4
                        onClicked: root.controller.captureReview.setAutoEnhance(!root.controller.captureReview.autoEnhanceActive)
                    }

                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: root.theme.borderSoft }

                    Text {
                        text: "Perspective correction"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 16
                        font.weight: root.theme.weightHeavy
                    }
                    Text {
                        text: root.controller.captureReview.perspectiveActive
                              ? "Perspective correction is applied."
                              : root.controller.captureReview.perspectiveAvailable
                                ? "Document boundary detected."
                                : "No document boundary detected."
                        color: root.theme.textMuted
                        font.family: root.theme.bodyFont
                        font.pixelSize: 13
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                    RowLayout {
                        visible: root.controller.captureReview.perspectiveAvailable
                        Layout.fillWidth: true
                        spacing: 8

                        SecondaryButton {
                            visible: !root.controller.captureReview.perspectiveActive
                            theme: root.theme
                            text: "APPLY"
                            implicitWidth: 0
                            Layout.minimumWidth: 0
                            Layout.fillWidth: true
                            navigationFocused: root.navigationIndex === 5
                            onClicked: root.controller.captureReview.acceptPerspective()
                        }
                        SecondaryButton {
                            visible: root.controller.captureReview.perspectiveActive
                            theme: root.theme
                            text: "CANCEL"
                            implicitWidth: 0
                            Layout.minimumWidth: 0
                            Layout.fillWidth: true
                            navigationFocused: root.navigationIndex === 6
                            onClicked: root.controller.captureReview.rejectPerspective()
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            SecondaryButton {
                theme: root.theme
                text: "RETAKE"
                onClicked: root.controller.retakeCapture()
            }
            NavigationHint {
                theme: root.theme
                text: "UP/DOWN Choose  •  SELECT Confirm  •  BACK Retake"
                Layout.fillWidth: true
            }
            PrimaryButton {
                theme: root.theme
                tone: "success"
                text: root.controller.captureReview.state === "submitting" ? "ANALYZING…" : "CONFIRM AND ANALYZE"
                enabled: root.controller.captureReview.canSubmit && root.controller.captureReview.state !== "submitting"
                implicitWidth: 256
                navigationFocused: root.navigationIndex === 7
                onClicked: root.controller.confirmReviewedImage()
            }
        }
    }
}
