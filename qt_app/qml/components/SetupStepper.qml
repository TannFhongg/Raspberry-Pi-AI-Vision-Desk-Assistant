import QtQuick
import QtQuick.Layouts

Item {
    id: root
    required property QtObject theme
    required property var controller
    required property var steps
    required property string currentStep

    implicitHeight: 64

    function stepIndex(stepId) {
        return root.steps.indexOf(stepId)
    }

    function shortLabel(stepId) {
        switch (stepId) {
        case "welcome":
            return "Welcome"
        case "wifi":
            return "Wi-Fi"
        case "openai":
            return "API Key"
        case "camera":
            return "Camera"
        case "gpio":
            return "GPIO"
        case "finish":
            return "Finish"
        default:
            return stepId
        }
    }

    readonly property int currentIndex: Math.max(0, root.stepIndex(root.currentStep))

    Rectangle {
        id: baseLine
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        anchors.leftMargin: 40
        anchors.rightMargin: 40
        height: 2
        radius: 1
        color: root.theme.borderSoft
    }

    Rectangle {
        anchors.left: baseLine.left
        anchors.verticalCenter: baseLine.verticalCenter
        width: root.steps.length > 1
               ? ((root.currentIndex) / (root.steps.length - 1)) * baseLine.width
               : 0
        height: 2
        radius: 1
        color: root.theme.primaryStrong
    }

    Repeater {
        model: root.steps.length

        delegate: Item {
            required property int index
            readonly property string stepId: root.steps[index]
            readonly property bool completed: index < root.currentIndex
            readonly property bool active: stepId === root.currentStep

            x: index * (root.width / Math.max(1, root.steps.length))
            width: root.width / Math.max(1, root.steps.length)
            height: root.height

            Column {
                anchors.top: parent.top
                anchors.topMargin: 0
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 4

                Rectangle {
                    width: 30
                    height: 30
                    radius: 15
                    color: completed || active ? root.theme.primaryStrong : root.theme.surface
                    border.width: 1
                    border.color: completed || active ? root.theme.primaryStrong : root.theme.borderMuted

                    Text {
                        anchors.centerIn: parent
                        text: completed ? "\u2713" : String(index + 1)
                        color: completed || active ? root.theme.surface : root.theme.textMuted
                        font.family: root.theme.bodyFont
                        font.pixelSize: root.theme.fontCaption
                        font.weight: root.theme.weightHeavy
                        renderType: root.theme.textRenderType
                    }
                }

                Text {
                    width: Math.max(84, parent.width - 12)
                    text: root.shortLabel(stepId)
                    color: active ? root.theme.text : root.theme.textMuted
                    font.family: root.theme.bodyFont
                    font.pixelSize: root.theme.fontCaption
                    font.weight: active ? root.theme.weightStrong : root.theme.weightRegular
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    renderType: root.theme.textRenderType
                }
            }

            MouseArea {
                anchors.fill: parent
                onClicked: root.controller.goToSetupStep(parent.stepId)
            }
        }
    }
}
