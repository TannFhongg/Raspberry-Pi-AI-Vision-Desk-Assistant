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
        if (action === "up") {
            root.navigationIndex = Math.max(0, root.navigationIndex - 1)
            return true
        }
        if (action === "down") {
            root.navigationIndex = Math.min(4, root.navigationIndex + 1)
            return true
        }
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
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text { text: "Camera preview"; color: root.theme.text; font.family: root.theme.displayFont; font.pixelSize: 34; font.weight: root.theme.weightHeavy }
                Text { text: "Task: " + root.controller.selectedModeLabel + "  •  Frame the area, then capture for review."; color: root.theme.textMuted; font.family: root.theme.bodyFont; font.pixelSize: 15; Layout.fillWidth: true; elide: Text.ElideRight }
            }
            StatusChip { theme: root.theme; label: root.controller.cameraPreviewAvailable ? "LIVE" : "PREVIEW"; value: root.controller.cameraPreviewAvailable ? "Camera ready" : "Starting"; tone: root.controller.cameraPreviewAvailable ? "success" : "warning" }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            ContentCard {
                theme: root.theme
                padding: 12
                Layout.fillWidth: true
                Layout.preferredHeight: 480

                Rectangle {
                    id: previewFrame
                    anchors.fill: parent
                    radius: root.theme.radiusControl
                    color: "#17202d"
                    clip: true

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
                        anchors.fill: parent
                        theme: root.theme
                        profile: root.controller.captureReview.captureProfile
                        zoomActive: root.controller.captureReview.previewZoomActive
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.top: parent.top
                        anchors.margins: 12
                        width: liveLabel.implicitWidth + 22
                        height: 32
                        radius: root.theme.radiusPill
                        color: root.controller.cameraPreviewAvailable ? Qt.rgba(0.12, 0.55, 0.28, 0.86) : Qt.rgba(0.1, 0.12, 0.18, 0.82)
                        Text { id: liveLabel; anchors.centerIn: parent; text: root.controller.cameraPreviewAvailable ? "● LIVE" : "● PREVIEW"; color: "white"; font.family: root.theme.bodyFont; font.pixelSize: 13; font.weight: root.theme.weightHeavy }
                    }

                    ColumnLayout {
                        anchors.centerIn: parent
                        width: parent.width * 0.62
                        visible: !root.controller.cameraPreviewAvailable
                        Text { text: root.controller.cameraPreviewTitle || "Camera unavailable"; color: "white"; font.family: root.theme.displayFont; font.pixelSize: 28; font.weight: root.theme.weightHeavy; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                        Text { text: root.controller.cameraPreviewMessage; color: "#E4E7EC"; font.family: root.theme.bodyFont; font.pixelSize: 16; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    }

                    MouseArea {
                        anchors.fill: parent
                        enabled: root.controller.cameraPreviewAvailable && root.controller.captureReview.previewZoomActive
                        onPositionChanged: function(mouse) {
                            var width = root.controller.captureReview.previewZoomWidth
                            var height = root.controller.captureReview.previewZoomHeight
                            root.controller.captureReview.setPreviewZoomRegion(
                                Math.max(0, Math.min(1 - width, mouse.x / previewFrame.width - width / 2)),
                                Math.max(0, Math.min(1 - height, mouse.y / previewFrame.height - height / 2)),
                                width, height)
                        }
                    }
                }
            }

            ContentCard {
                theme: root.theme
                padding: 16
                Layout.preferredWidth: 300
                Layout.minimumWidth: 300
                Layout.maximumWidth: 300
                Layout.preferredHeight: 480

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 10
                    Text { text: "Capture profile"; color: root.theme.text; font.family: root.theme.displayFont; font.pixelSize: 21; font.weight: root.theme.weightHeavy }
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
                    Text { text: "Focus: " + root.controller.captureReview.autofocusSupportMessage; color: root.theme.textMuted; font.family: root.theme.bodyFont; font.pixelSize: 14; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Text { text: "Exposure: " + root.controller.captureReview.exposureSupportMessage; color: root.theme.textMuted; font.family: root.theme.bodyFont; font.pixelSize: 14; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Item { Layout.fillHeight: true }
                    RowLayout {
                        Layout.fillWidth: true
                        SecondaryButton { theme: root.theme; text: "ZOOM +"; implicitWidth: 132; navigationFocused: root.navigationIndex === 2; onClicked: root.controller.captureReview.zoomPreviewIn() }
                        SecondaryButton { theme: root.theme; text: "ZOOM −"; implicitWidth: 132; navigationFocused: root.navigationIndex === 3; onClicked: root.controller.captureReview.zoomPreviewOut() }
                    }
                    SecondaryButton { theme: root.theme; text: "RESET ZOOM"; Layout.fillWidth: true; navigationFocused: root.navigationIndex === 4; onClicked: root.controller.captureReview.resetPreviewZoom() }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            SecondaryButton { theme: root.theme; text: "BACK"; navigationFocused: root.navigationIndex === 0; onClicked: root.controller.goBack() }
            NavigationHint { theme: root.theme; text: "UP/DOWN Choose  ·  SELECT Confirm  ·  BACK Return"; Layout.fillWidth: true }
            PrimaryButton { theme: root.theme; tone: "success"; text: root.controller.captureReview.state === "capturing" ? "CAPTURING…" : "CAPTURE"; enabled: root.controller.cameraPreviewAvailable && root.controller.captureReview.state !== "capturing"; navigationFocused: root.navigationIndex === 1; onClicked: root.controller.capture() }
        }
    }
}
