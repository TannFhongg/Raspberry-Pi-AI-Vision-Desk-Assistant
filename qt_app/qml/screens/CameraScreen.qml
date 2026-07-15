import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller
    property int navigationIndex: 1

    function handleNavigation(action) {
        if (action === "up") { root.navigationIndex = Math.max(0, root.navigationIndex - 1); return true }
        if (action === "down") { root.navigationIndex = Math.min(4, root.navigationIndex + 1); return true }
        if (action === "select") {
            if (root.navigationIndex === 0) root.controller.goBack()
            else if (root.navigationIndex === 1) root.controller.capture()
            else if (root.navigationIndex === 2) root.controller.captureReview.zoomPreviewIn()
            else if (root.navigationIndex === 3) root.controller.captureReview.zoomPreviewOut()
            else root.controller.captureReview.resetPreviewZoom()
            return true
        }
        if (action === "back") { root.controller.goBack(); return true }
        return false
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: root.theme.pageSpacing

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                HeadingText { theme: root.theme; text: "Camera preview" }
                AppText {
                    theme: root.theme
                    role: "secondaryBody"
                    text: "Task: " + root.controller.selectedModeLabel + "  •  Frame the area, then capture for review."
                    color: root.theme.textMuted
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                }
            }
            StatusChip { theme: root.theme; label: root.controller.cameraPreviewAvailable ? "LIVE" : "PREVIEW"; value: root.controller.cameraPreviewAvailable ? "Camera ready" : "Starting"; tone: root.controller.cameraPreviewAvailable ? "success" : "warning" }
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

                Rectangle {
                    id: previewFrame
                    anchors.fill: parent
                    radius: root.theme.radiusControl
                    color: "#17202D"
                    clip: true

                    function paintedX() { return previewImage.x + (previewImage.width - previewImage.paintedWidth) / 2 }
                    function paintedY() { return previewImage.y + (previewImage.height - previewImage.paintedHeight) / 2 }
                    function normalizedPaintedX(value) { return Math.max(0, Math.min(1, (value - paintedX()) / Math.max(1, previewImage.paintedWidth))) }
                    function normalizedPaintedY(value) { return Math.max(0, Math.min(1, (value - paintedY()) / Math.max(1, previewImage.paintedHeight))) }

                    Image {
                        id: previewImage
                        anchors.fill: parent
                        source: root.controller.cameraPreviewRevision > 0 ? "image://visiondesk/camera/live?seq=" + root.controller.cameraPreviewRevision : ""
                        fillMode: Image.PreserveAspectFit
                        cache: false
                        smooth: true
                        sourceClipRect: Qt.rect(
                            root.controller.captureReview.previewZoomX * sourceSize.width,
                            root.controller.captureReview.previewZoomY * sourceSize.height,
                            root.controller.captureReview.previewZoomWidth * sourceSize.width,
                            root.controller.captureReview.previewZoomHeight * sourceSize.height
                        )
                        visible: root.controller.cameraPreviewAvailable
                    }

                    CameraGuideOverlay {
                        x: previewFrame.paintedX()
                        y: previewFrame.paintedY()
                        width: previewImage.paintedWidth
                        height: previewImage.paintedHeight
                        visible: root.controller.cameraPreviewAvailable && width > 0 && height > 0
                        theme: root.theme
                        profile: root.controller.captureReview.captureProfile
                        zoomActive: root.controller.captureReview.previewZoomActive
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.margins: 12
                        width: liveLabel.implicitWidth + 22
                        height: 34
                        radius: root.theme.radiusPill
                        color: root.controller.cameraPreviewAvailable ? Qt.rgba(0.07, 0.45, 0.22, 0.94) : Qt.rgba(0.1, 0.12, 0.18, 0.88)
                        StatusText { id: liveLabel; anchors.centerIn: parent; theme: root.theme; text: root.controller.cameraPreviewAvailable ? "● LIVE" : "● PREVIEW"; color: "white" }
                    }

                    ColumnLayout {
                        anchors.centerIn: parent
                        width: Math.min(parent.width * 0.68, 640)
                        visible: !root.controller.cameraPreviewAvailable
                        AppText { theme: root.theme; role: "sectionTitle"; decorative: true; text: root.controller.cameraPreviewTitle || "Camera unavailable"; color: "white"; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        BodyText { theme: root.theme; text: root.controller.cameraPreviewMessage; color: "#E4E7EC"; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true }
                    }

                    MouseArea {
                        anchors.fill: parent
                        enabled: root.controller.cameraPreviewAvailable && root.controller.captureReview.previewZoomActive
                        onPositionChanged: function(mouse) {
                            var regionWidth = root.controller.captureReview.previewZoomWidth
                            var regionHeight = root.controller.captureReview.previewZoomHeight
                            var sourceX = root.controller.captureReview.previewZoomX
                                          + previewFrame.normalizedPaintedX(mouse.x) * regionWidth
                            var sourceY = root.controller.captureReview.previewZoomY
                                          + previewFrame.normalizedPaintedY(mouse.y) * regionHeight
                            root.controller.captureReview.setPreviewZoomRegion(
                                Math.max(0, Math.min(1 - regionWidth, sourceX - regionWidth / 2)),
                                Math.max(0, Math.min(1 - regionHeight, sourceY - regionHeight / 2)),
                                regionWidth, regionHeight)
                        }
                    }
                }
            }

            ContentCard {
                theme: root.theme
                padding: 16
                Layout.preferredWidth: root.theme.sidePanelWidth
                Layout.minimumWidth: root.theme.sidePanelWidth
                Layout.maximumWidth: root.theme.sidePanelWidth
                Layout.fillHeight: true
                Layout.minimumHeight: 0

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10
                    AppText { theme: root.theme; role: "cardTitle"; text: "Capture profile" }
                    Repeater {
                        model: root.controller.captureReview.captureProfilesModel.count
                        delegate: SecondaryButton {
                            required property int index
                            property var itemData: root.controller.captureReview.captureProfilesModel.get(index)
                            theme: root.theme
                            text: itemData.label || "Profile"
                            Layout.fillWidth: true
                            tone: root.controller.captureReview.captureProfile === (itemData.id || "") ? "primary" : "neutral"
                            onClicked: root.controller.captureReview.setCaptureProfile(itemData.id || "document")
                        }
                    }
                    BodyText { theme: root.theme; role: "caption"; text: "Focus: " + root.controller.captureReview.autofocusSupportMessage; color: root.theme.textMuted; Layout.fillWidth: true }
                    BodyText { theme: root.theme; role: "caption"; text: "Exposure: " + root.controller.captureReview.exposureSupportMessage; color: root.theme.textMuted; Layout.fillWidth: true }
                    Item { Layout.fillHeight: true }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 10
                        SecondaryButton { theme: root.theme; text: "Zoom In"; implicitWidth: 0; Layout.fillWidth: true; navigationFocused: root.navigationIndex === 2; onClicked: root.controller.captureReview.zoomPreviewIn() }
                        SecondaryButton { theme: root.theme; text: "Zoom Out"; implicitWidth: 0; Layout.fillWidth: true; navigationFocused: root.navigationIndex === 3; onClicked: root.controller.captureReview.zoomPreviewOut() }
                    }
                    SecondaryButton { theme: root.theme; text: "Reset Zoom"; Layout.fillWidth: true; navigationFocused: root.navigationIndex === 4; onClicked: root.controller.captureReview.resetPreviewZoom() }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: root.theme.footerHeight
            SecondaryButton { theme: root.theme; text: "Back"; navigationFocused: root.navigationIndex === 0; onClicked: root.controller.goBack() }
            NavigationHint { theme: root.theme; text: "UP/DOWN Choose  ·  SELECT Confirm  ·  BACK Return"; Layout.fillWidth: true }
            PrimaryButton { theme: root.theme; tone: "success"; text: root.controller.captureReview.state === "capturing" ? "Capturing…" : "Capture"; enabled: root.controller.cameraPreviewAvailable && root.controller.captureReview.state !== "capturing"; navigationFocused: root.navigationIndex === 1; onClicked: root.controller.capture() }
        }
    }
}
