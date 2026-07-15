import QtQuick

Item {
    id: root
    required property QtObject theme
    required property var review
    property bool cropEditing: true
    property string dragMode: ""
    property real startX: 0
    property real startY: 0
    property real startCropX: 0
    property real startCropY: 0
    property real startCropWidth: 1
    property real startCropHeight: 1
    readonly property real minCrop: 0.055
    // Leave room for the 22 px drag handles and the capture label. This keeps
    // a full-frame crop editable without clipping its touch targets.
    readonly property int imageEdgeInset: Math.ceil(root.theme.minimumTouchTarget / 2) + 2
    readonly property int imageTopInset: 46
    readonly property real handleHitRadius: root.theme.minimumTouchTarget / 2

    function imageX() { return sourceImage.x + (sourceImage.width - sourceImage.paintedWidth) / 2 }
    function imageY() { return sourceImage.y + (sourceImage.height - sourceImage.paintedHeight) / 2 }
    function normalizedX(value) { return Math.max(0, Math.min(1, (value - imageX()) / Math.max(1, sourceImage.paintedWidth))) }
    function normalizedY(value) { return Math.max(0, Math.min(1, (value - imageY()) / Math.max(1, sourceImage.paintedHeight))) }
    function containsImagePoint(x, y) {
        return x >= imageX() && x <= imageX() + sourceImage.paintedWidth
            && y >= imageY() && y <= imageY() + sourceImage.paintedHeight
    }
    function setCrop(x, y, width, height) {
        var w = Math.max(root.minCrop, Math.min(1, width))
        var h = Math.max(root.minCrop, Math.min(1, height))
        var left = Math.max(0, Math.min(1 - w, x))
        var top = Math.max(0, Math.min(1 - h, y))
        root.review.setCropNormalized(left, top, w, h)
    }
    function handleAt(mouseX, mouseY) {
        var radius = root.handleHitRadius
        var points = [
            [cropBox.x, cropBox.y, "topLeft"], [cropBox.x + cropBox.width, cropBox.y, "topRight"],
            [cropBox.x, cropBox.y + cropBox.height, "bottomLeft"], [cropBox.x + cropBox.width, cropBox.y + cropBox.height, "bottomRight"]
        ]
        for (var index = 0; index < points.length; ++index) {
            var point = points[index]
            if (Math.abs(mouseX - point[0]) <= radius && Math.abs(mouseY - point[1]) <= radius)
                return point[2]
        }
        return "move"
    }

    Rectangle { anchors.fill: parent; radius: root.theme.radiusControl; color: "#101827"; clip: true }

    Image {
        id: sourceImage
        anchors.fill: parent
        anchors.leftMargin: root.imageEdgeInset
        anchors.rightMargin: root.imageEdgeInset
        anchors.bottomMargin: root.imageEdgeInset
        anchors.topMargin: root.imageTopInset
        source: root.review.sourceRevision > 0 ? "image://visiondesk/review/source?seq=" + root.review.sourceRevision : ""
        fillMode: Image.PreserveAspectFit
        cache: false
        smooth: true
    }

    Canvas {
        id: perspectiveCanvas
        anchors.fill: parent
        visible: root.review.perspectiveAvailable && !root.review.perspectiveActive
        onPaint: {
            var points = root.review.perspectivePoints
            if (!points || points.length !== 4 || sourceImage.paintedWidth <= 0) return
            var context = getContext("2d")
            context.clearRect(0, 0, width, height)
            context.strokeStyle = "#F5A623"
            context.lineWidth = 3
            context.beginPath()
            for (var index = 0; index < points.length; ++index) {
                var px = root.imageX() + points[index].x * sourceImage.paintedWidth
                var py = root.imageY() + points[index].y * sourceImage.paintedHeight
                if (index === 0) context.moveTo(px, py)
                else context.lineTo(px, py)
            }
            context.closePath()
            context.stroke()
        }
    }

    Rectangle {
        id: cropBox
        visible: root.cropEditing && root.review.hasCapturedImage
        x: root.imageX() + root.review.cropX * sourceImage.paintedWidth
        y: root.imageY() + root.review.cropY * sourceImage.paintedHeight
        width: root.review.cropWidth * sourceImage.paintedWidth
        height: root.review.cropHeight * sourceImage.paintedHeight
        color: "transparent"
        border.width: 3
        border.color: "#FFFFFF"

        Repeater {
            model: 4
            delegate: Rectangle {
                width: 22; height: 22; radius: 11; color: root.theme.primaryStrong; border.width: 2; border.color: "white"
                x: index % 2 === 0 ? -width / 2 : cropBox.width - width / 2
                y: index < 2 ? -height / 2 : cropBox.height - height / 2
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.cropEditing && root.review.hasCapturedImage
        preventStealing: true
        onPressed: function(mouse) {
            if (!root.containsImagePoint(mouse.x, mouse.y)) {
                mouse.accepted = false
                return
            }
            root.dragMode = root.handleAt(mouse.x, mouse.y)
            root.startX = root.normalizedX(mouse.x)
            root.startY = root.normalizedY(mouse.y)
            root.startCropX = root.review.cropX
            root.startCropY = root.review.cropY
            root.startCropWidth = root.review.cropWidth
            root.startCropHeight = root.review.cropHeight
        }
        onPositionChanged: function(mouse) {
            if (!pressed || root.dragMode.length === 0) return
            var currentX = root.normalizedX(mouse.x)
            var currentY = root.normalizedY(mouse.y)
            var deltaX = currentX - root.startX
            var deltaY = currentY - root.startY
            var x = root.startCropX
            var y = root.startCropY
            var width = root.startCropWidth
            var height = root.startCropHeight
            if (root.dragMode === "move") { x += deltaX; y += deltaY }
            else {
                if (root.dragMode === "topLeft" || root.dragMode === "bottomLeft") { x += deltaX; width -= deltaX }
                if (root.dragMode === "topRight" || root.dragMode === "bottomRight") width += deltaX
                if (root.dragMode === "topLeft" || root.dragMode === "topRight") { y += deltaY; height -= deltaY }
                if (root.dragMode === "bottomLeft" || root.dragMode === "bottomRight") height += deltaY
            }
            root.setCrop(x, y, width, height)
        }
        onReleased: root.dragMode = ""
    }

    Rectangle {
        anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 12
        width: originalLabel.implicitWidth + 20; height: 30; radius: root.theme.radiusPill
        color: Qt.rgba(0.06, 0.09, 0.16, 0.78)
        AppText { id: originalLabel; anchors.centerIn: parent; theme: root.theme; role: "caption"; forceQtRendering: true; text: "Original capture"; color: "white"; font.weight: root.theme.weightStrong }
    }

    Connections {
        target: root.review
        function onStateChanged() { perspectiveCanvas.requestPaint() }
    }
    onWidthChanged: perspectiveCanvas.requestPaint()
    onHeightChanged: perspectiveCanvas.requestPaint()
}
