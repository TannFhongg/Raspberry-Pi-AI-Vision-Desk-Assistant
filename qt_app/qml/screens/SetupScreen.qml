import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    property string selectedSsid: ""
    property bool showApiKey: false

    readonly property var stepOrder: ["welcome", "wifi", "openai", "camera", "gpio", "finish"]
    readonly property var stepTitles: ({
        "welcome": "Welcome + Device Check",
        "wifi": "Wi-Fi Setup",
        "openai": "OpenAI API Key",
        "camera": "Camera Test",
        "gpio": "GPIO Button Test",
        "finish": "Finish Setup"
    })

    function stepIndex(step) {
        const index = stepOrder.indexOf(step || "")
        return index >= 0 ? index : 0
    }

    function isCurrentStep(step) {
        return root.controller.setupCurrentStep === step
    }

    function statusColor(status) {
        const normalized = (status || "").toLowerCase()
        if (normalized === "pass" || normalized === "healthy") return root.theme.success
        if (normalized === "fail" || normalized === "error") return root.theme.error
        if (normalized === "running" || normalized === "warning") return root.theme.warning
        return root.theme.textSecondary
    }

    function statusText(status) {
        const normalized = (status || "").toLowerCase()
        if (normalized === "pass") return "PASS"
        if (normalized === "fail") return "FAIL"
        if (normalized === "running") return "RUNNING"
        if (normalized === "idle") return "IDLE"
        return (status || "UNKNOWN").toUpperCase()
    }

    function canAdvance() {
        switch (root.controller.setupCurrentStep) {
        case "welcome":
            return true
        case "wifi":
            return root.controller.setupWifiStatus === "pass"
        case "openai":
            return root.controller.setupApiKeyVerified
        case "camera":
            return root.controller.setupCameraStatus === "pass"
        case "gpio":
            return root.controller.setupGpioStatus === "pass"
        case "finish":
            return root.controller.setupReadyToFinish
        default:
            return false
        }
    }

    Component.onCompleted: {
        if (root.controller.deviceChecksModel.count === 0
                && root.controller.setupDeviceChecksStatus === "idle") {
            root.controller.runSetupDeviceChecks()
        }
        if (root.controller.wifiNetworksModel.count === 0
                && root.controller.setupWifiStatus === "idle"
                && root.controller.setupWifiMessage.length === 0) {
            root.controller.scanWifi()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 18

        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Repeater {
                model: root.stepOrder.length

                delegate: Rectangle {
                    required property int index
                    readonly property string stepId: root.stepOrder[index]
                    readonly property bool active: root.isCurrentStep(stepId)
                    readonly property bool completed: index < root.stepIndex(root.controller.setupCurrentStep)
                    color: active ? root.theme.primary : completed ? root.theme.successFill : root.theme.surface
                    border.width: root.theme.borderStrong
                    border.color: active ? root.theme.primaryDark : root.theme.text
                    radius: root.theme.radiusPill
                    implicitHeight: 48
                    implicitWidth: Math.max(136, label.implicitWidth + 34)

                    Text {
                        id: label
                        anchors.centerIn: parent
                        text: (index + 1) + ". " + root.stepTitles[stepId]
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 18
                        font.weight: root.theme.weightHeavy
                        renderType: Text.NativeRendering
                    }

                    MouseArea {
                        anchors.fill: parent
                        onClicked: root.controller.goToSetupStep(parent.stepId)
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: root.theme.radiusCard
            border.width: root.theme.borderStrong
            border.color: root.theme.text
            color: root.theme.surface

            ScrollView {
                anchors.fill: parent
                anchors.margins: 22
                clip: true

                ColumnLayout {
                    width: availableWidth
                    spacing: 20

                    Text {
                        text: root.stepTitles[root.controller.setupCurrentStep]
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 40
                        font.weight: root.theme.weightHeavy
                        Layout.fillWidth: true
                    }

                    Item {
                        visible: root.isCurrentStep("welcome")
                        Layout.fillWidth: true
                        implicitHeight: welcomeColumn.implicitHeight

                        ColumnLayout {
                            id: welcomeColumn
                            anchors.left: parent.left
                            anchors.right: parent.right
                            spacing: 18

                            Text {
                                text: "Run first-boot checks for config access, writable storage, NetworkManager, display session, camera, and GPIO."
                                color: root.theme.textSecondary
                                font.family: root.theme.bodyFont
                                font.pixelSize: 18
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 12

                                StatusPill {
                                    theme: root.theme
                                    label: "Checks"
                                    value: root.statusText(root.controller.setupDeviceChecksStatus)
                                    tone: root.controller.setupDeviceChecksStatus
                                }

                                ActionButton {
                                    theme: root.theme
                                    primary: true
                                    text: "RUN CHECKS"
                                    implicitWidth: 220
                                    onClicked: root.controller.runSetupDeviceChecks()
                                }
                            }

                            Text {
                                visible: root.controller.setupDeviceChecksMessage.length > 0
                                text: root.controller.setupDeviceChecksMessage
                                color: root.statusColor(root.controller.setupDeviceChecksStatus)
                                font.family: root.theme.bodyFont
                                font.pixelSize: 17
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }

                            Repeater {
                                model: root.controller.deviceChecksModel.count

                                delegate: Rectangle {
                                    required property int index
                                    readonly property var itemData: root.controller.deviceChecksModel.get(index)
                                    Layout.fillWidth: true
                                    implicitHeight: contentColumn.implicitHeight + 24
                                    radius: root.theme.radiusCardSm
                                    border.width: 2
                                    border.color: root.statusColor(itemData.status || "")
                                    color: itemData.status === "pass" ? root.theme.successFill
                                          : itemData.status === "fail" ? root.theme.errorFill
                                          : root.theme.mutedFill

                                    ColumnLayout {
                                        id: contentColumn
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 8

                                        RowLayout {
                                            Layout.fillWidth: true

                                            Text {
                                                text: (itemData.name || "").replace(/_/g, " ").toUpperCase()
                                                color: root.theme.text
                                                font.family: root.theme.displayFont
                                                font.pixelSize: 18
                                                font.weight: root.theme.weightHeavy
                                            }

                                            Item { Layout.fillWidth: true }

                                            Text {
                                                text: root.statusText(itemData.status || "")
                                                color: root.statusColor(itemData.status || "")
                                                font.family: root.theme.displayFont
                                                font.pixelSize: 18
                                                font.weight: root.theme.weightHeavy
                                            }
                                        }

                                        Text {
                                            text: itemData.message || ""
                                            color: root.theme.textSecondary
                                            font.family: root.theme.bodyFont
                                            font.pixelSize: 16
                                            wrapMode: Text.WordWrap
                                            Layout.fillWidth: true
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Item {
                        visible: root.isCurrentStep("wifi")
                        Layout.fillWidth: true
                        implicitHeight: wifiColumn.implicitHeight

                        ColumnLayout {
                            id: wifiColumn
                            anchors.left: parent.left
                            anchors.right: parent.right
                            spacing: 16

                            Text {
                                text: "Scan nearby networks or enter a hidden SSID manually. Wi-Fi is required before setup can finish."
                                color: root.theme.textSecondary
                                font.family: root.theme.bodyFont
                                font.pixelSize: 18
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }

                            RowLayout {
                                spacing: 12

                                StatusPill {
                                    theme: root.theme
                                    label: "Wi-Fi"
                                    value: root.statusText(root.controller.setupWifiStatus)
                                    tone: root.controller.setupWifiStatus
                                }

                                ActionButton {
                                    theme: root.theme
                                    text: "RESCAN"
                                    implicitWidth: 140
                                    onClicked: root.controller.scanWifi()
                                }
                            }

                            ComboBox {
                                id: scanWifiCombo
                                Layout.fillWidth: true
                                height: 54
                                model: root.controller.wifiNetworksModel.count
                                currentIndex: -1
                                enabled: model > 0
                                font.family: root.theme.displayFont
                                font.pixelSize: 20
                                font.weight: root.theme.weightStrong
                                leftPadding: 22
                                rightPadding: 52
                                displayText: root.selectedSsid.length > 0 ? root.selectedSsid : "Select a scanned SSID"

                                indicator: Text {
                                    text: "v"
                                    color: root.theme.text
                                    font.family: root.theme.displayFont
                                    font.pixelSize: 20
                                    font.weight: root.theme.weightHeavy
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.right: parent.right
                                    anchors.rightMargin: 20
                                }

                                contentItem: Text {
                                    leftPadding: scanWifiCombo.leftPadding
                                    rightPadding: scanWifiCombo.rightPadding
                                    verticalAlignment: Text.AlignVCenter
                                    text: scanWifiCombo.displayText
                                    color: root.selectedSsid.length > 0 ? root.theme.text : "#aeb4be"
                                    font: scanWifiCombo.font
                                    elide: Text.ElideRight
                                    renderType: Text.NativeRendering
                                }

                                background: Rectangle {
                                    radius: root.theme.radiusPill
                                    color: root.theme.surface
                                    border.width: root.theme.borderStrong
                                    border.color: scanWifiCombo.activeFocus ? root.theme.primary : root.theme.text
                                    opacity: scanWifiCombo.enabled ? 1.0 : 0.72
                                }

                                delegate: ItemDelegate {
                                    id: scanWifiDelegate
                                    required property int index
                                    readonly property var itemData: root.controller.wifiNetworksModel.get(index)
                                    width: ListView.view ? ListView.view.width : scanWifiCombo.width
                                    highlighted: scanWifiCombo.highlightedIndex === index

                                    contentItem: Text {
                                        text: (scanWifiDelegate.itemData.ssid || "")
                                              + ((scanWifiDelegate.itemData.security || "").length > 0
                                                 ? " - " + scanWifiDelegate.itemData.security
                                                 : "")
                                        color: root.theme.text
                                        font.family: root.theme.displayFont
                                        font.pixelSize: 18
                                        font.weight: root.theme.weightStrong
                                        verticalAlignment: Text.AlignVCenter
                                        elide: Text.ElideRight
                                        renderType: Text.NativeRendering
                                    }

                                    background: Rectangle {
                                        color: scanWifiDelegate.highlighted ? "#eef6ff" : root.theme.surface
                                        radius: 16
                                    }

                                    onClicked: {
                                        root.selectedSsid = itemData.ssid || ""
                                        scanWifiCombo.currentIndex = index
                                        manualSsidField.text = ""
                                        scanWifiCombo.popup.close()
                                    }
                                }

                                popup: Popup {
                                    y: scanWifiCombo.height + 8
                                    width: scanWifiCombo.width
                                    padding: 8

                                    contentItem: ListView {
                                        clip: true
                                        implicitHeight: Math.min(contentHeight, 220)
                                        model: scanWifiCombo.popup.visible ? scanWifiCombo.delegateModel : null
                                        currentIndex: scanWifiCombo.highlightedIndex
                                        ScrollBar.vertical: ScrollBar {}
                                    }

                                    background: Rectangle {
                                        radius: 24
                                        color: root.theme.surface
                                        border.width: root.theme.borderStrong
                                        border.color: root.theme.text
                                    }
                                }
                            }

                            SetupInputField {
                                id: manualSsidField
                                theme: root.theme
                                Layout.fillWidth: true
                                placeholderText: "Manual SSID for hidden networks"
                                onTextEdited: {
                                    if (text.length > 0) {
                                        root.selectedSsid = ""
                                        scanWifiCombo.currentIndex = -1
                                    }
                                }
                            }

                            SetupInputField {
                                id: passwordField
                                theme: root.theme
                                Layout.fillWidth: true
                                secret: true
                                placeholderText: "Leave blank for open networks"
                            }

                            ActionButton {
                                theme: root.theme
                                primary: true
                                text: "CONNECT WIFI"
                                implicitWidth: 220
                                onClicked: {
                                    root.controller.connectWifi(root.selectedSsid, manualSsidField.text, passwordField.text)
                                    passwordField.text = ""
                                }
                            }

                            Text {
                                visible: root.controller.setupWifiMessage.length > 0
                                text: root.controller.setupWifiMessage
                                color: root.statusColor(root.controller.setupWifiStatus === "fail"
                                                        ? "fail"
                                                        : root.controller.setupWifiScanStatus)
                                font.family: root.theme.bodyFont
                                font.pixelSize: 16
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
                    }

                    Item {
                        visible: root.isCurrentStep("openai")
                        Layout.fillWidth: true
                        implicitHeight: openAiColumn.implicitHeight

                        ColumnLayout {
                            id: openAiColumn
                            anchors.left: parent.left
                            anchors.right: parent.right
                            spacing: 16

                            Text {
                                text: "Save the API key into the protected VisionDesk environment file. The raw key never returns to QML after saving."
                                color: root.theme.textSecondary
                                font.family: root.theme.bodyFont
                                font.pixelSize: 18
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }

                            RowLayout {
                                spacing: 12

                                StatusPill {
                                    theme: root.theme
                                    label: "API Key"
                                    value: root.controller.setupApiKeyVerified ? "VERIFIED" : root.controller.setupHasApiKey ? "SAVED" : "MISSING"
                                    tone: root.controller.setupOpenAiStatus
                                }

                                ActionButton {
                                    theme: root.theme
                                    text: root.showApiKey ? "HIDE KEY" : "SHOW KEY"
                                    implicitWidth: 170
                                    onClicked: root.showApiKey = !root.showApiKey
                                }

                                ActionButton {
                                    theme: root.theme
                                    destructive: true
                                    text: "CLEAR KEY"
                                    implicitWidth: 170
                                    enabled: root.controller.setupHasApiKey
                                    onClicked: root.controller.clearApiKey()
                                }
                            }

                            SetupInputField {
                                id: openAiKeyField
                                theme: root.theme
                                Layout.fillWidth: true
                                secret: !root.showApiKey
                                placeholderText: "Paste OPENAI_API_KEY"
                            }

                            Text {
                                visible: root.controller.setupMaskedApiKey.length > 0
                                text: "Stored key: " + root.controller.setupMaskedApiKey
                                color: root.theme.success
                                font.family: root.theme.bodyFont
                                font.pixelSize: 16
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }

                            ActionButton {
                                theme: root.theme
                                primary: true
                                text: "SAVE + VERIFY"
                                implicitWidth: 220
                                onClicked: {
                                    root.controller.verifyApiKey(openAiKeyField.text)
                                    openAiKeyField.text = ""
                                }
                            }

                            Text {
                                visible: root.controller.setupOpenAiMessage.length > 0
                                text: root.controller.setupOpenAiMessage
                                color: root.statusColor(root.controller.setupOpenAiStatus)
                                font.family: root.theme.bodyFont
                                font.pixelSize: 16
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
                    }

                    Item {
                        visible: root.isCurrentStep("camera")
                        Layout.fillWidth: true
                        implicitHeight: cameraColumn.implicitHeight

                        ColumnLayout {
                            id: cameraColumn
                            anchors.left: parent.left
                            anchors.right: parent.right
                            spacing: 16

                            RowLayout {
                                spacing: 12

                                StatusPill {
                                    theme: root.theme
                                    label: "Camera"
                                    value: root.statusText(root.controller.setupCameraStatus)
                                    tone: root.controller.setupCameraStatus
                                }

                                StatusPill {
                                    theme: root.theme
                                    label: "Focus"
                                    value: root.controller.setupCameraAutofocusMode.toUpperCase()
                                    tone: "running"
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 360
                                radius: root.theme.radiusCard
                                border.width: 2
                                border.color: root.theme.primary
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

                                Rectangle {
                                    anchors.fill: parent
                                    visible: !root.controller.cameraPreviewAvailable
                                    color: "#d9d9d9"

                                    ColumnLayout {
                                        anchors.centerIn: parent
                                        width: parent.width * 0.7
                                        spacing: 10

                                        Text {
                                            text: root.controller.cameraPreviewTitle
                                            color: root.theme.text
                                            font.family: root.theme.displayFont
                                            font.pixelSize: 32
                                            font.weight: root.theme.weightStrong
                                            horizontalAlignment: Text.AlignHCenter
                                            Layout.fillWidth: true
                                        }

                                        Text {
                                            text: root.controller.cameraPreviewMessage
                                            color: root.theme.textSecondary
                                            font.family: root.theme.bodyFont
                                            font.pixelSize: 18
                                            wrapMode: Text.WordWrap
                                            horizontalAlignment: Text.AlignHCenter
                                            Layout.fillWidth: true
                                        }
                                    }
                                }
                            }

                            ActionButton {
                                theme: root.theme
                                primary: true
                                text: "RUN CAMERA TEST"
                                implicitWidth: 250
                                onClicked: root.controller.runCameraTest()
                            }

                            Text {
                                visible: root.controller.setupCameraMessage.length > 0
                                text: root.controller.setupCameraMessage
                                color: root.statusColor(root.controller.setupCameraStatus)
                                font.family: root.theme.bodyFont
                                font.pixelSize: 16
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
                    }

                    Item {
                        visible: root.isCurrentStep("gpio")
                        Layout.fillWidth: true
                        implicitHeight: gpioColumn.implicitHeight

                        ColumnLayout {
                            id: gpioColumn
                            anchors.left: parent.left
                            anchors.right: parent.right
                            spacing: 16

                            RowLayout {
                                spacing: 12

                                StatusPill {
                                    theme: root.theme
                                    label: "GPIO"
                                    value: root.statusText(root.controller.setupGpioStatus)
                                    tone: root.controller.setupGpioStatus
                                }

                                ActionButton {
                                    theme: root.theme
                                    primary: true
                                    text: root.controller.setupGpioActive ? "TEST RUNNING" : "START TEST"
                                    enabled: !root.controller.setupGpioActive
                                    implicitWidth: 220
                                    onClicked: root.controller.startGpioTest()
                                }

                                ActionButton {
                                    theme: root.theme
                                    text: "STOP TEST"
                                    enabled: root.controller.setupGpioActive
                                    implicitWidth: 160
                                    onClicked: root.controller.stopGpioTest()
                                }
                            }

                            Text {
                                text: "Press each configured hardware button once. Matching rows turn green when their press is detected."
                                color: root.theme.textSecondary
                                font.family: root.theme.bodyFont
                                font.pixelSize: 18
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }

                            Repeater {
                                model: root.controller.gpioRequirementsModel.count

                                delegate: Rectangle {
                                    required property int index
                                    readonly property var itemData: root.controller.gpioRequirementsModel.get(index)
                                    Layout.fillWidth: true
                                    implicitHeight: 62
                                    radius: root.theme.radiusCardSm
                                    border.width: 2
                                    border.color: itemData.pressed ? root.theme.success : root.theme.text
                                    color: itemData.pressed ? root.theme.successFill : root.theme.surface

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.margins: 14

                                        Text {
                                            text: (itemData.label || "").replace(/_/g, " ").toUpperCase()
                                            color: root.theme.text
                                            font.family: root.theme.displayFont
                                            font.pixelSize: 20
                                            font.weight: root.theme.weightHeavy
                                        }

                                        Item { Layout.fillWidth: true }

                                        Text {
                                            text: "GPIO " + (itemData.pin || "")
                                            color: root.theme.textSecondary
                                            font.family: root.theme.displayFont
                                            font.pixelSize: 18
                                            font.weight: root.theme.weightStrong
                                        }

                                        Text {
                                            text: itemData.pressed ? "DETECTED" : "WAITING"
                                            color: itemData.pressed ? root.theme.success : root.theme.textSecondary
                                            font.family: root.theme.displayFont
                                            font.pixelSize: 18
                                            font.weight: root.theme.weightHeavy
                                        }
                                    }
                                }
                            }

                            Text {
                                visible: root.controller.setupGpioMessage.length > 0
                                text: root.controller.setupGpioMessage
                                color: root.statusColor(root.controller.setupGpioStatus)
                                font.family: root.theme.bodyFont
                                font.pixelSize: 16
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
                    }

                    Item {
                        visible: root.isCurrentStep("finish")
                        Layout.fillWidth: true
                        implicitHeight: finishColumn.implicitHeight

                        ColumnLayout {
                            id: finishColumn
                            anchors.left: parent.left
                            anchors.right: parent.right
                            spacing: 16

                            Text {
                                text: "Finish becomes available only after Wi-Fi, API key verification, camera test, and GPIO test all pass."
                                color: root.theme.textSecondary
                                font.family: root.theme.bodyFont
                                font.pixelSize: 18
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }

                            GridLayout {
                                columns: 2
                                columnSpacing: 12
                                rowSpacing: 12
                                Layout.fillWidth: true

                                StatusPill {
                                    theme: root.theme
                                    label: "Wi-Fi"
                                    value: root.statusText(root.controller.setupWifiStatus)
                                    tone: root.controller.setupWifiStatus
                                }

                                StatusPill {
                                    theme: root.theme
                                    label: "OpenAI"
                                    value: root.statusText(root.controller.setupOpenAiStatus)
                                    tone: root.controller.setupOpenAiStatus
                                }

                                StatusPill {
                                    theme: root.theme
                                    label: "Camera"
                                    value: root.statusText(root.controller.setupCameraStatus)
                                    tone: root.controller.setupCameraStatus
                                }

                                StatusPill {
                                    theme: root.theme
                                    label: "GPIO"
                                    value: root.statusText(root.controller.setupGpioStatus)
                                    tone: root.controller.setupGpioStatus
                                }
                            }

                            Text {
                                text: root.controller.setupFinishMessage.length > 0
                                      ? root.controller.setupFinishMessage
                                      : root.controller.setupWarningsText.length > 0
                                        ? root.controller.setupWarningsText
                                        : root.controller.setupReadyToFinish
                                          ? "All required checks passed. Finish setup to restart into Home."
                                          : "Complete the remaining required checks before finishing."
                                color: root.controller.setupReadyToFinish ? root.theme.success : root.theme.error
                                font.family: root.theme.bodyFont
                                font.pixelSize: 17
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }

                            ActionButton {
                                theme: root.theme
                                primary: true
                                text: "FINISH SETUP + RESTART"
                                enabled: root.controller.setupReadyToFinish
                                implicitWidth: 320
                                onClicked: root.controller.finishSetup()
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            ActionButton {
                theme: root.theme
                text: "BACK"
                enabled: root.stepIndex(root.controller.setupCurrentStep) > 0
                onClicked: root.controller.goToSetupPreviousStep()
            }

            Item { Layout.fillWidth: true }

            ActionButton {
                theme: root.theme
                primary: true
                text: root.controller.setupCurrentStep === "finish" ? "READY" : "NEXT"
                enabled: root.canAdvance() && root.controller.setupCurrentStep !== "finish"
                onClicked: root.controller.goToSetupNextStep()
            }
        }
    }
}
