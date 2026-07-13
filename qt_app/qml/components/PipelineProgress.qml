import QtQuick
import QtQuick.Layouts

Item {
    id: root
    required property QtObject theme
    required property string backendState
    property string tone: "active"

    readonly property var labels: ["Image captured", "Preprocessing", "AI analysis", "Result ready"]
    readonly property int activeIndex: {
        if (root.backendState === "DONE") return 3
        if (root.backendState === "ANALYZING") return 2
        if (root.backendState === "PREPROCESSING") return 1
        return 0
    }
    readonly property int errorIndex: root.backendState === "ERROR" || root.backendState === "RETRY_QUEUED"
                                          ? Math.min(2, Math.max(0, root.activeIndex))
                                          : -1

    implicitHeight: 86

    Rectangle {
        id: track
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: 64
        anchors.rightMargin: 64
        height: 2
        radius: 1
        color: root.theme.borderSoft
    }

    Rectangle {
        anchors.left: track.left
        anchors.verticalCenter: track.verticalCenter
        width: root.activeIndex / (root.labels.length - 1) * track.width
        height: 2
        radius: 1
        color: root.tone === "error" ? root.theme.errorStrong
             : root.tone === "queued" ? root.theme.warningStrong
             : root.theme.primaryStrong
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0

        Repeater {
            model: root.labels.length

            delegate: ProgressStep {
                required property int index
                theme: root.theme
                label: root.labels[index]
                state: root.errorIndex === index ? "error"
                       : root.backendState === "DONE" || index < root.activeIndex ? "complete"
                       : index === root.activeIndex ? "active"
                       : "pending"
                Layout.fillWidth: true
            }
        }
    }
}
