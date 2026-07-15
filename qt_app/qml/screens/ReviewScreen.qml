import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller
    property int navigationIndex: 7
    property real reviewZoom: 1.0
    property bool cropEditing: true

    function focusOrder() {
        var actions = [0, 1, 2, 3, 4]
        if (root.controller.captureReview.perspectiveAvailable && !root.controller.captureReview.perspectiveActive) actions.push(5)
        if (root.controller.captureReview.perspectiveActive) actions.push(6)
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
        spacing: root.theme.pageSpacing

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                spacing: 2
                HeadingText { theme: root.theme; text: "Review and adjust" }
                AppText {
                    theme: root.theme
                    role: "secondaryBody"
                    text: "Task: " + root.controller.selectedModeLabel + "  •  Profile: " + root.controller.captureReview.captureProfileLabel
                    color: root.theme.textMuted
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                }
            }
            StatusChip { theme: root.theme; label: "Privacy"; value: "Not sent yet"; tone: "info" }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 0
            spacing: root.theme.cardSpacing

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
                Layout.preferredWidth: root.theme.sidePanelWidth
                Layout.minimumWidth: root.theme.sidePanelWidth
                Layout.maximumWidth: root.theme.sidePanelWidth
                Layout.fillHeight: true
                Layout.minimumHeight: 0
                clipContent: true

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 8
                    AppText { theme: root.theme; role: "cardTitle"; text: "Adjustments" }

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        columnSpacing: 10
                        rowSpacing: 8

                        AppText { theme: root.theme; role: "status"; text: "Camera"; Layout.alignment: Qt.AlignTop }
                        BodyText {
                            theme: root.theme
                            role: "caption"
                            text: "Focus: " + root.controller.captureReview.autofocusSupportMessage
                                  + "\nExposure: " + root.controller.captureReview.exposureSupportMessage
                            color: root.theme.textMuted
                            Layout.fillWidth: true
                        }

                        Rectangle { Layout.columnSpan: 2; Layout.fillWidth: true; Layout.preferredHeight: 1; color: root.theme.borderSoft }

                        AppText { theme: root.theme; role: "status"; text: "Crop" }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            SecondaryButton { theme: root.theme; text: "Crop"; implicitWidth: 0; Layout.fillWidth: true; navigationFocused: root.navigationIndex === 0; onClicked: root.startCropEditing() }
                            SecondaryButton { theme: root.theme; text: "Reset"; implicitWidth: 0; Layout.fillWidth: true; navigationFocused: root.navigationIndex === 1; onClicked: root.controller.captureReview.resetCrop() }
                        }

                        AppText { theme: root.theme; role: "status"; text: "Zoom" }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            SecondaryButton { theme: root.theme; text: "Out"; implicitWidth: 0; Layout.fillWidth: true; navigationFocused: root.navigationIndex === 2; onClicked: root.zoomCanvas(-0.2) }
                            SecondaryButton { theme: root.theme; text: "In"; implicitWidth: 0; Layout.fillWidth: true; navigationFocused: root.navigationIndex === 3; onClicked: root.zoomCanvas(0.2) }
                        }

                        AppText { theme: root.theme; role: "status"; text: "Enhance" }
                        SecondaryButton {
                            theme: root.theme
                            text: root.controller.captureReview.autoEnhanceActive ? "Auto Enhance: On" : "Auto Enhance"
                            Layout.fillWidth: true
                            navigationFocused: root.navigationIndex === 4
                            onClicked: root.controller.captureReview.setAutoEnhance(!root.controller.captureReview.autoEnhanceActive)
                        }

                        Rectangle { Layout.columnSpan: 2; Layout.fillWidth: true; Layout.preferredHeight: 1; color: root.theme.borderSoft }

                        AppText { theme: root.theme; role: "status"; text: "Perspective"; Layout.alignment: Qt.AlignTop }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            BodyText {
                                theme: root.theme
                                role: "caption"
                                text: root.controller.captureReview.perspectiveActive
                                      ? "Correction applied."
                                      : root.controller.captureReview.perspectiveAvailable
                                        ? "Document boundary detected."
                                        : "No boundary detected."
                                color: root.theme.textMuted
                                Layout.fillWidth: true
                            }
                            SecondaryButton {
                                visible: root.controller.captureReview.perspectiveAvailable
                                theme: root.theme
                                text: root.controller.captureReview.perspectiveActive ? "Cancel" : "Apply"
                                Layout.fillWidth: true
                                navigationFocused: root.navigationIndex === (root.controller.captureReview.perspectiveActive ? 6 : 5)
                                onClicked: root.controller.captureReview.perspectiveActive
                                           ? root.controller.captureReview.rejectPerspective()
                                           : root.controller.captureReview.acceptPerspective()
                            }
                        }
                    }
                    Item { Layout.fillHeight: true }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: root.theme.footerHeight
            spacing: root.theme.cardSpacing
            SecondaryButton { theme: root.theme; text: "Retake"; onClicked: root.controller.retakeCapture() }
            NavigationHint { theme: root.theme; text: "UP/DOWN Choose  •  SELECT Confirm  •  BACK Retake"; Layout.fillWidth: true }
            PrimaryButton {
                theme: root.theme
                tone: "success"
                text: root.controller.captureReview.state === "submitting" ? "Analyzing…" : "Confirm and Analyze"
                enabled: root.controller.captureReview.canSubmit && root.controller.captureReview.state !== "submitting"
                implicitWidth: 246
                navigationFocused: root.navigationIndex === 7
                onClicked: root.controller.confirmReviewedImage()
            }
        }
    }
}
