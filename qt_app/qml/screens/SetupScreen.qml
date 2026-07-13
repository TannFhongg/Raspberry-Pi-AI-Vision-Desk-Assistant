import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    property string selectedSsid: ""
    property string manualSsidText: ""
    property string wifiPasswordText: ""
    property string apiKeyDraft: ""
    property bool showApiKey: false

    readonly property int cardPadding: 16
    readonly property int cardGap: 10
    readonly property int sidebarWidthWide: 286
    readonly property int sidebarWidthNarrow: 252
    readonly property int finishLeadWidth: 280
    readonly property var stepOrder: ["welcome", "wifi", "openai", "camera", "gpio", "finish"]
    readonly property var stepTitles: ({
        "welcome": "Welcome + Device Check",
        "wifi": "Wi-Fi Setup",
        "openai": "OpenAI API Key",
        "camera": "Camera Test",
        "gpio": "GPIO Button Test",
        "finish": "Finish Setup"
    })
    readonly property var stepSubtitles: ({
        "welcome": "Get VisionDesk ready with a quick health and environment check.",
        "wifi": "Connect the device to a nearby network or enter a hidden SSID manually.",
        "openai": "Save and verify the OpenAI key in the protected VisionDesk environment file.",
        "camera": "Confirm live preview, focus mode, and one-shot capture readiness.",
        "gpio": "Press each configured hardware button once to verify wiring and mapping.",
        "finish": "Review the setup gates, then restart directly into VisionDesk Home."
    })
    readonly property var welcomeHighlights: [
        "Config, environment, and writable storage",
        "Desktop session and NetworkManager readiness",
        "Camera preview path and GPIO access"
    ]

    function stepIndex(step) {
        const index = stepOrder.indexOf(step || "")
        return index >= 0 ? index : 0
    }

    function isCurrentStep(step) {
        return root.controller.setupCurrentStep === step
    }

    function normalizeStatus(status) {
        const normalized = (status || "").toLowerCase()
        return normalized.length > 0 ? normalized : "idle"
    }

    function statusText(status) {
        const normalized = normalizeStatus(status)
        if (normalized === "pass") return "Ready"
        if (normalized === "fail") return "Attention"
        if (normalized === "running") return "In Progress"
        if (normalized === "healthy") return "Healthy"
        if (normalized === "idle") return "Idle"
        return normalized.toUpperCase()
    }

    function statusTone(status) {
        const normalized = normalizeStatus(status)
        if (normalized === "pass" || normalized === "healthy") return "success"
        if (normalized === "fail" || normalized === "error") return "danger"
        if (normalized === "running" || normalized === "warning") return "warning"
        return "info"
    }

    function statusColor(status) {
        const tone = statusTone(status)
        if (tone === "success") return root.theme.successStrong
        if (tone === "danger") return root.theme.errorStrong
        if (tone === "warning") return root.theme.warningStrong
        return root.theme.primaryStrong
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

    function selectedOrManualSsid() {
        const manual = root.manualSsidText.trim()
        return manual.length > 0 ? manual : root.selectedSsid
    }

    function signalLabel(signalValue) {
        const signal = Number(signalValue || 0)
        if (signal >= 75) return "STRONG"
        if (signal >= 45) return "GOOD"
        if (signal > 0) return "WEAK"
        return "UNKNOWN"
    }

    function securityLabel(securityValue) {
        const value = (securityValue || "").trim()
        return value.length > 0 ? value.toUpperCase() : "OPEN"
    }

    function clearApiKeyEntry() {
        const hasStoredKey = root.controller.setupHasApiKey
        root.apiKeyDraft = ""
        root.showApiKey = false
        if (hasStoredKey) {
            root.controller.clearApiKey()
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

    Component {
        id: welcomeStepComponent

        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                spacing: root.cardGap

                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 182
                    Layout.minimumHeight: 182
                    Layout.maximumHeight: 182
                    spacing: root.cardGap

                    InfoCard {
                        theme: root.theme
                        padding: root.cardPadding
                        Layout.fillWidth: true
                        Layout.fillHeight: true

                        RowLayout {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            spacing: 16

                            Rectangle {
                                Layout.preferredWidth: 92
                                Layout.preferredHeight: 92
                                radius: 24
                                color: root.theme.primarySoft

                                Rectangle {
                                    anchors.centerIn: parent
                                    width: 58
                                    height: 44
                                    radius: 14
                                    color: root.theme.surface
                                    border.width: 1
                                    border.color: root.theme.borderSoft

                                    Rectangle {
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        anchors.bottom: parent.bottom
                                        anchors.bottomMargin: -8
                                        width: 28
                                        height: 8
                                        radius: 4
                                        color: root.theme.borderSoft
                                    }
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                spacing: 8

                                Text {
                                    text: "Before VisionDesk goes live, we verify the essentials that keep a kiosk deployment stable."
                                    color: root.theme.text
                                    font.family: root.theme.displayFont
                                    font.pixelSize: 16
                                    font.weight: root.theme.weightStrong
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }

                                Repeater {
                                    model: root.welcomeHighlights.length

                                    delegate: RowLayout {
                                        required property int index
                                        spacing: 8

                                        Rectangle {
                                            Layout.preferredWidth: 18
                                            Layout.preferredHeight: 18
                                            radius: 9
                                            color: root.theme.successFill

                                            Rectangle {
                                                anchors.centerIn: parent
                                                width: 7
                                                height: 7
                                                radius: 4
                                                color: root.theme.successStrong
                                            }
                                        }

                                        Text {
                                            text: root.welcomeHighlights[index]
                                            color: root.theme.textMuted
                                            font.family: root.theme.bodyFont
                                            font.pixelSize: 13
                                            font.weight: root.theme.weightRegular
                                            wrapMode: Text.WordWrap
                                            maximumLineCount: 2
                                            elide: Text.ElideRight
                                            Layout.fillWidth: true
                                        }
                                    }
                                }

                                Item {
                                    Layout.fillHeight: true
                                }
                            }
                        }
                    }

                    InfoCard {
                        theme: root.theme
                        padding: 14
                        fillColor: "#FBFCFE"
                        Layout.preferredWidth: 272
                        Layout.minimumHeight: 0
                        Layout.fillHeight: true

                        ColumnLayout {
                            spacing: 10

                            StatusChip {
                                theme: root.theme
                                label: "Checks"
                                value: root.controller.setupDeviceChecksBusy
                                       ? "Running"
                                       : root.statusText(root.controller.setupDeviceChecksStatus)
                                tone: root.controller.setupDeviceChecksBusy
                                      ? "warning"
                                      : root.statusTone(root.controller.setupDeviceChecksStatus)
                            }

                            Text {
                                text: root.controller.setupDeviceChecksMessage.length > 0
                                      ? root.controller.setupDeviceChecksMessage
                                      : "Check config, storage, display, camera, GPIO, and network readiness."
                                color: root.controller.setupDeviceChecksMessage.length > 0
                                       ? root.statusColor(root.controller.setupDeviceChecksStatus)
                                       : root.theme.textMuted
                                font.family: root.theme.bodyFont
                                font.pixelSize: 13
                                wrapMode: Text.WordWrap
                                maximumLineCount: 3
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            PrimaryButton {
                                theme: root.theme
                                tone: "success"
                                text: root.controller.setupDeviceChecksBusy ? "RUNNING..." : "RUN CHECKS"
                                enabled: !root.controller.setupDeviceChecksBusy
                                Layout.fillWidth: true
                                onClicked: root.controller.runSetupDeviceChecks()
                            }
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    columns: 3
                    rows: 2
                    columnSpacing: root.cardGap
                    rowSpacing: root.cardGap

                    Repeater {
                        model: Math.max(root.controller.deviceChecksModel.count, 6)

                        delegate: StatusCard {
                            required property int index
                            readonly property bool hasData: index < root.controller.deviceChecksModel.count
                            readonly property var itemData: hasData ? root.controller.deviceChecksModel.get(index) : null
                            theme: root.theme
                            padding: 14
                            compact: true
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.minimumHeight: 0
                            Layout.preferredHeight: 98
                            title: hasData ? ((itemData.name || "").replace(/_/g, " ")) : "Pending check"
                            eyebrow: hasData ? "Device check" : "Pending"
                            value: hasData ? root.statusText(itemData.status || "") : "Waiting"
                            message: hasData ? (itemData.message || "") : "Run diagnostics to populate this check."
                            tone: hasData ? root.statusTone(itemData.status || "") : "info"
                        }
                    }
                }
            }
        }
    }

    Component {
        id: wifiStepComponent

        Item {
            anchors.fill: parent

            Component.onCompleted: {
                if (!root.selectedSsid && root.controller.setupWifiSsid.length > 0) {
                    root.selectedSsid = root.controller.setupWifiSsid
                }
            }

            ColumnLayout {
                anchors.fill: parent
                spacing: root.cardGap

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Flow {
                        Layout.fillWidth: true
                        spacing: 8

                        StatusChip {
                            theme: root.theme
                            label: "Wi-Fi"
                            value: root.statusText(root.controller.setupWifiStatus)
                            tone: root.statusTone(root.controller.setupWifiStatus)
                        }

                        StatusChip {
                            visible: root.controller.setupWifiSsid.length > 0
                            theme: root.theme
                            label: "SSID"
                            value: root.controller.setupWifiSsid
                            tone: root.controller.setupWifiStatus === "pass" ? "success" : "info"
                        }
                    }

                    SecondaryButton {
                        theme: root.theme
                        tone: "primary"
                        text: "RESCAN"
                        implicitWidth: 122
                        onClicked: root.controller.scanWifi()
                    }
                }

                Text {
                    text: root.controller.setupWifiScanStatus === "fail"
                          ? root.controller.setupWifiMessage
                          : root.controller.wifiNetworksModel.count > 0
                            ? "Tap a network on the left, or enter a hidden SSID on the right."
                            : "Nearby networks will appear here after a scan."
                    color: root.controller.setupWifiScanStatus === "fail" ? root.theme.errorStrong : root.theme.textMuted
                    font.family: root.theme.bodyFont
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 20
                    color: "#FBFCFE"
                    border.width: 1
                    border.color: root.theme.borderSoft
                    clip: true

                    ListView {
                        id: wifiList
                        anchors.fill: parent
                        anchors.margins: 12
                        clip: true
                        spacing: 8
                        boundsBehavior: Flickable.StopAtBounds
                        model: root.controller.wifiNetworksModel.count

                        delegate: Rectangle {
                            required property int index
                            readonly property var itemData: root.controller.wifiNetworksModel.get(index)
                            readonly property bool selected: root.selectedSsid === (itemData.ssid || "")
                            width: wifiList.width
                            height: 54
                            radius: 16
                            color: selected ? root.theme.primarySoft : root.theme.surface
                            border.width: 1
                            border.color: selected ? root.theme.primaryStrong : root.theme.borderSoft

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 14
                                anchors.rightMargin: 14
                                spacing: 12

                                Rectangle {
                                    Layout.preferredWidth: 30
                                    Layout.preferredHeight: 30
                                    radius: 15
                                    color: selected ? "#D9E8FF" : root.theme.mutedFill

                                    Text {
                                        anchors.centerIn: parent
                                        text: root.securityLabel(itemData.security || "") === "OPEN" ? "O" : "L"
                                        color: selected ? root.theme.primaryStrong : root.theme.textMuted
                                        font.family: root.theme.displayFont
                                        font.pixelSize: 13
                                        font.weight: root.theme.weightHeavy
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 1

                                    Text {
                                        text: itemData.ssid || "Unnamed network"
                                        color: root.theme.text
                                        font.family: root.theme.displayFont
                                        font.pixelSize: 18
                                        font.weight: root.theme.weightStrong
                                        elide: Text.ElideRight
                                        renderType: Text.NativeRendering
                                    }

                                    Text {
                                        text: root.securityLabel(itemData.security || "") + " | " + root.signalLabel(itemData.signal)
                                        color: root.theme.textMuted
                                        font.family: root.theme.bodyFont
                                        font.pixelSize: 13
                                    }
                                }

                                StatusChip {
                                    theme: root.theme
                                    label: root.signalLabel(itemData.signal)
                                    tone: selected ? "success" : "info"
                                }
                            }

                            MouseArea {
                                anchors.fill: parent
                                onClicked: {
                                    root.selectedSsid = itemData.ssid || ""
                                    root.manualSsidText = ""
                                }
                            }
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: root.cardGap
                    rowSpacing: root.cardGap

                    InputField {
                        id: manualSsidField
                        theme: root.theme
                        Layout.fillWidth: true
                        Layout.preferredHeight: 52
                        leadingText: "ID"
                        placeholderText: "Manual SSID for hidden networks"
                        text: root.manualSsidText
                        onTextChanged: {
                            if (root.manualSsidText !== text) {
                                root.manualSsidText = text
                            }
                            if (text.length > 0) {
                                root.selectedSsid = ""
                            }
                        }
                    }

                    PasswordField {
                        id: passwordField
                        theme: root.theme
                        Layout.fillWidth: true
                        Layout.preferredHeight: 52
                        leadingText: "PW"
                        placeholderText: "Leave blank for open networks"
                        text: root.wifiPasswordText
                        onTextChanged: if (root.wifiPasswordText !== text) root.wifiPasswordText = text
                    }
                }

                PrimaryButton {
                    theme: root.theme
                    tone: "success"
                    text: "CONNECT WI-FI"
                    Layout.fillWidth: true
                    onClicked: root.controller.connectWifi(root.selectedSsid, root.manualSsidText, root.wifiPasswordText)
                }

            }
        }
    }

    Component {
        id: openAiStepComponent

        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                spacing: root.cardGap

                Flow {
                    Layout.fillWidth: true
                    spacing: 8

                    StatusChip {
                        theme: root.theme
                        label: "API Key"
                        value: root.controller.setupApiKeyVerified ? "Verified" : root.controller.setupHasApiKey ? "Saved" : "Missing"
                        tone: root.statusTone(root.controller.setupOpenAiStatus)
                    }

                    StatusChip {
                        theme: root.theme
                        label: "Stored"
                        value: root.controller.setupApiKeyDisplayText
                        tone: root.controller.setupHasApiKey ? "success" : "neutral"
                    }
                }

                PasswordField {
                    id: openAiKeyField
                    theme: root.theme
                    Layout.fillWidth: true
                    Layout.preferredHeight: 52
                    leadingText: "AI"
                    placeholderText: "Paste OPENAI_API_KEY"
                    invalid: root.controller.setupOpenAiStatus === "fail"
                    revealed: root.showApiKey
                    toggleEnabled: false
                    text: root.apiKeyDraft
                    onTextChanged: if (root.apiKeyDraft !== text) root.apiKeyDraft = text
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    SecondaryButton {
                        theme: root.theme
                        tone: "primary"
                        text: root.showApiKey ? "HIDE KEY" : "SHOW KEY"
                        implicitWidth: 132
                        onClicked: {
                            root.showApiKey = !root.showApiKey
                            openAiKeyField.revealed = root.showApiKey
                        }
                    }

                    SecondaryButton {
                        theme: root.theme
                        tone: "primary"
                        text: "PASTE"
                        implicitWidth: 100
                        onClicked: openAiKeyField.paste()
                    }

                    SecondaryButton {
                        theme: root.theme
                        tone: "danger"
                        text: root.controller.setupApiKeyBusy && root.controller.setupHasApiKey
                              ? "CLEARING..."
                              : "CLEAR KEY"
                        implicitWidth: 132
                        enabled: !root.controller.setupApiKeyBusy
                                 && (root.controller.setupHasApiKey || root.apiKeyDraft.trim().length > 0)
                        onClicked: root.clearApiKeyEntry()
                    }

                    Item {
                        Layout.fillWidth: true
                    }
                }

                PrimaryButton {
                    theme: root.theme
                    tone: "success"
                    text: root.controller.setupApiKeyBusy ? "WORKING..." : "SAVE + VERIFY"
                    enabled: !root.controller.setupApiKeyBusy && root.apiKeyDraft.trim().length > 0
                    Layout.fillWidth: true
                    onClicked: {
                        root.controller.verifyApiKey(root.apiKeyDraft)
                        root.apiKeyDraft = ""
                    }
                }

                StatusCard {
                    theme: root.theme
                    padding: 14
                    title: "Verification result"
                    eyebrow: "Protected storage"
                    value: root.controller.setupApiKeyVerified
                           ? "OpenAI verified"
                           : root.controller.setupHasApiKey
                             ? "Saved, waiting for verification"
                             : "Key required"
                    message: root.controller.setupOpenAiMessage.length > 0
                             ? root.controller.setupOpenAiMessage
                             : "The raw key never returns to QML after saving."
                    tone: root.statusTone(root.controller.setupOpenAiStatus)
                    Layout.fillWidth: true
                }

                InfoCard {
                    theme: root.theme
                    padding: 14
                    fillColor: "#FBFCFE"
                    Layout.fillWidth: true

                    ColumnLayout {
                        spacing: 6

                        Text {
                            text: "Secure API Setup"
                            color: root.theme.text
                            font.family: root.theme.displayFont
                            font.pixelSize: 17
                            font.weight: root.theme.weightStrong
                        }

                        Text {
                            text: "VisionDesk stores the key in the protected environment file. QML receives only saved and verified status."
                            color: root.theme.textMuted
                            font.family: root.theme.bodyFont
                            font.pixelSize: 13
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Text {
                            text: "Clear Key removes the stored secret without returning raw or masked key data to the UI."
                            color: root.controller.setupHasApiKey ? root.theme.successStrong : root.theme.warningStrong
                            font.family: root.theme.bodyFont
                            font.pixelSize: 13
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }
            }
        }
    }

    Component {
        id: cameraStepComponent

        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                spacing: root.cardGap

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Flow {
                        Layout.fillWidth: true
                        spacing: 8

                        StatusChip {
                            theme: root.theme
                            label: "Camera"
                            value: root.statusText(root.controller.setupCameraStatus)
                            tone: root.statusTone(root.controller.setupCameraStatus)
                        }

                        StatusChip {
                            theme: root.theme
                            label: "Focus"
                            value: (root.controller.setupCameraAutofocusMode || "continuous").toUpperCase()
                            tone: "warning"
                        }
                    }

                    PrimaryButton {
                        theme: root.theme
                        tone: "primary"
                        text: "RUN CAMERA TEST"
                        implicitWidth: 220
                        onClicked: root.controller.runCameraTest()
                    }
                }

                Text {
                    text: root.controller.setupCameraMessage.length > 0
                          ? root.controller.setupCameraMessage
                          : "Camera ready check"
                    color: root.statusColor(root.controller.setupCameraStatus)
                    font.family: root.theme.bodyFont
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 20
                    color: "#F4F7FB"
                    border.width: 1
                    border.color: root.theme.borderSoft
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

                    ColumnLayout {
                        anchors.centerIn: parent
                        width: parent.width * 0.6
                        spacing: 8
                        visible: !root.controller.cameraPreviewAvailable

                        Rectangle {
                            Layout.alignment: Qt.AlignHCenter
                            width: 60
                            height: 60
                            radius: 30
                            color: root.theme.primarySoft

                            Rectangle {
                                anchors.centerIn: parent
                                width: 26
                                height: 26
                                radius: 13
                                color: root.theme.primaryStrong
                            }
                        }

                        Text {
                            text: root.controller.cameraPreviewTitle
                            color: root.theme.text
                            font.family: root.theme.displayFont
                            font.pixelSize: 18
                            font.weight: root.theme.weightStrong
                            horizontalAlignment: Text.AlignHCenter
                            Layout.fillWidth: true
                        }

                        Text {
                            text: root.controller.cameraPreviewMessage
                            color: root.theme.textMuted
                            font.family: root.theme.bodyFont
                            font.pixelSize: 13
                            wrapMode: Text.WordWrap
                            horizontalAlignment: Text.AlignHCenter
                            Layout.fillWidth: true
                        }
                    }
                }

            }
        }
    }

    Component {
        id: gpioStepComponent

        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                spacing: root.cardGap

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10

                    StatusChip {
                        theme: root.theme
                        label: "GPIO"
                        value: root.statusText(root.controller.setupGpioStatus)
                        tone: root.statusTone(root.controller.setupGpioStatus)
                    }

                    PrimaryButton {
                        theme: root.theme
                        tone: "success"
                        text: root.controller.setupGpioActive ? "TEST RUNNING" : "START TEST"
                        enabled: !root.controller.setupGpioActive
                        implicitWidth: 180
                        onClicked: root.controller.startGpioTest()
                    }

                    SecondaryButton {
                        theme: root.theme
                        tone: "neutral"
                        text: "STOP TEST"
                        enabled: root.controller.setupGpioActive
                        implicitWidth: 144
                        onClicked: root.controller.stopGpioTest()
                    }

                    Item {
                        Layout.fillWidth: true
                    }
                }

                Text {
                    text: "Press each configured hardware button once. Cards turn green as soon as VisionDesk detects the press."
                    color: root.theme.textMuted
                    font.family: root.theme.bodyFont
                    font.pixelSize: 14
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                Text {
                    text: root.controller.setupGpioMessage.length > 0
                          ? root.controller.setupGpioMessage
                          : "Start the GPIO test and press each configured button once."
                    color: root.statusColor(root.controller.setupGpioStatus)
                    font.family: root.theme.bodyFont
                    font.pixelSize: 13
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                GridLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    columns: 2
                    columnSpacing: root.cardGap
                    rowSpacing: root.cardGap

                    Repeater {
                        model: Math.max(root.controller.gpioRequirementsModel.count, 1)

                        delegate: Rectangle {
                            required property int index
                            readonly property bool hasData: index < root.controller.gpioRequirementsModel.count
                            readonly property var itemData: hasData ? root.controller.gpioRequirementsModel.get(index) : null
                            readonly property bool pressed: hasData ? Boolean(itemData.pressed) : false
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.preferredHeight: 84
                            radius: 20
                            color: pressed ? root.theme.successFill : root.theme.surface
                            border.width: 1
                            border.color: pressed ? root.theme.successStrong : root.theme.borderSoft

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 16
                                anchors.rightMargin: 16
                                anchors.topMargin: 16
                                anchors.bottomMargin: 16
                                spacing: 12

                                Rectangle {
                                    Layout.preferredWidth: 36
                                    Layout.preferredHeight: 36
                                    radius: 18
                                    color: pressed ? "#D9F4E3" : root.theme.mutedFill

                                    Rectangle {
                                        anchors.centerIn: parent
                                        width: 10
                                        height: 10
                                        radius: 5
                                        color: pressed ? root.theme.successStrong : root.theme.textMuted
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    spacing: 2

                                    Text {
                                        text: hasData ? (itemData.label || "").replace(/_/g, " ") : "No GPIO requirements"
                                        color: root.theme.text
                                        font.family: root.theme.displayFont
                                        font.pixelSize: 17
                                        font.weight: root.theme.weightStrong
                                        renderType: Text.NativeRendering
                                        elide: Text.ElideRight
                                    }

                                    Text {
                                        text: hasData
                                              ? (pressed ? "Detected" : "Waiting for press")
                                              : "Nothing to verify for this profile."
                                        color: pressed ? root.theme.successStrong : root.theme.textMuted
                                        font.family: root.theme.bodyFont
                                        font.pixelSize: 13
                                        font.weight: root.theme.weightStrong
                                    }
                                }

                                ColumnLayout {
                                    visible: hasData
                                    spacing: 1

                                    Text {
                                        text: "GPIO " + (hasData ? (itemData.pin || "") : "")
                                        color: root.theme.text
                                        font.family: root.theme.displayFont
                                        font.pixelSize: 15
                                        font.weight: root.theme.weightStrong
                                    }

                                    Text {
                                        text: pressed ? "OK" : "PENDING"
                                        color: pressed ? root.theme.successStrong : root.theme.textMuted
                                        font.family: root.theme.bodyFont
                                        font.pixelSize: 12
                                        font.weight: root.theme.weightStrong
                                    }
                                }
                            }
                        }
                    }
                }

            }
        }
    }

    Component {
        id: finishStepComponent

        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                spacing: root.cardGap

                InfoCard {
                    theme: root.theme
                    padding: 16
                    fillColor: "#FBFCFE"
                    Layout.fillWidth: true

                    ColumnLayout {
                        spacing: 10

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 14

                            Rectangle {
                                Layout.preferredWidth: 72
                                Layout.preferredHeight: 72
                                radius: 36
                                color: root.controller.setupReadyToFinish ? root.theme.successFill : root.theme.warningFill

                                Text {
                                    anchors.centerIn: parent
                                    text: root.controller.setupReadyToFinish ? "\u2713" : "!"
                                    color: root.controller.setupReadyToFinish ? root.theme.successStrong : root.theme.warningStrong
                                    font.family: root.theme.displayFont
                                    font.pixelSize: 34
                                    font.weight: root.theme.weightHeavy
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: 4

                                Text {
                                    text: root.controller.setupReadyToFinish ? "VisionDesk is ready." : "Almost there."
                                    color: root.theme.text
                                    font.family: root.theme.displayFont
                                    font.pixelSize: 24
                                    font.weight: root.theme.weightHeavy
                                    Layout.fillWidth: true
                                }

                                Text {
                                    text: root.controller.setupReadyToFinish
                                          ? "All setup gates passed. Launch VisionDesk Home by finishing the wizard."
                                          : "Finish becomes available only after Wi-Fi, API key verification, camera test, and GPIO test all pass."
                                    color: root.theme.textMuted
                                    font.family: root.theme.bodyFont
                                    font.pixelSize: 14
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                }
                            }
                        }

                        PrimaryButton {
                            theme: root.theme
                            tone: "success"
                            text: "LAUNCH VISIONDESK"
                            enabled: root.controller.setupReadyToFinish
                            Layout.fillWidth: true
                            onClicked: root.controller.finishSetup()
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: root.cardGap
                    rowSpacing: root.cardGap

                    StatusCard {
                        theme: root.theme
                        padding: 14
                        title: "Wi-Fi"
                        eyebrow: "Gate"
                        value: root.statusText(root.controller.setupWifiStatus)
                        message: root.controller.setupWifiSsid.length > 0 ? root.controller.setupWifiSsid : "Network required"
                        tone: root.statusTone(root.controller.setupWifiStatus)
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 0
                        Layout.preferredHeight: 88
                    }

                    StatusCard {
                        theme: root.theme
                        padding: 14
                        title: "OpenAI"
                        eyebrow: "Gate"
                        value: root.statusText(root.controller.setupOpenAiStatus)
                        message: root.controller.setupApiKeyVerified ? "Verified successfully" : "API verification required"
                        tone: root.statusTone(root.controller.setupOpenAiStatus)
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 0
                        Layout.preferredHeight: 88
                    }

                    StatusCard {
                        theme: root.theme
                        padding: 14
                        title: "Camera"
                        eyebrow: "Gate"
                        value: root.statusText(root.controller.setupCameraStatus)
                        message: root.controller.setupCameraMessage.length > 0 ? root.controller.setupCameraMessage : "Camera test required"
                        tone: root.statusTone(root.controller.setupCameraStatus)
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 0
                        Layout.preferredHeight: 88
                    }

                    StatusCard {
                        theme: root.theme
                        padding: 14
                        title: "GPIO"
                        eyebrow: "Gate"
                        value: root.statusText(root.controller.setupGpioStatus)
                        message: root.controller.setupGpioMessage.length > 0 ? root.controller.setupGpioMessage : "GPIO test required"
                        tone: root.statusTone(root.controller.setupGpioStatus)
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredWidth: 0
                        Layout.preferredHeight: 88
                    }
                }

            }
        }
    }

    Loader {
        id: bodyComponentLoader
        visible: false
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10

        SetupStepper {
            theme: root.theme
            controller: root.controller
            steps: root.stepOrder
            currentStep: root.controller.setupCurrentStep
            Layout.fillWidth: true
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Rectangle {
                anchors.left: contentCard.left
                anchors.right: contentCard.right
                anchors.top: contentCard.top
                anchors.bottom: contentCard.bottom
                anchors.leftMargin: 4
                anchors.rightMargin: -2
                anchors.topMargin: 8
                anchors.bottomMargin: -6
                radius: root.theme.radiusSetupCard + 2
                color: Qt.rgba(0.06, 0.09, 0.16, 0.08)
            }

            Rectangle {
                id: contentCard
                anchors.fill: parent
                radius: root.theme.radiusSetupCard
                color: root.theme.surface
                border.width: 1
                border.color: root.theme.borderSoft
            }

            ColumnLayout {
                anchors.fill: contentCard
                anchors.margins: 18
                spacing: 10

                SectionTitle {
                    theme: root.theme
                    title: root.stepTitles[root.controller.setupCurrentStep]
                    subtitle: root.stepSubtitles[root.controller.setupCurrentStep]
                    Layout.fillWidth: true
                }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    Loader {
                        anchors.fill: parent
                        sourceComponent: {
                            switch (root.controller.setupCurrentStep) {
                            case "wifi":
                                return wifiStepComponent
                            case "openai":
                                return openAiStepComponent
                            case "camera":
                                return cameraStepComponent
                            case "gpio":
                                return gpioStepComponent
                            case "finish":
                                return finishStepComponent
                            default:
                                return welcomeStepComponent
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            SecondaryButton {
                theme: root.theme
                text: "BACK"
                enabled: root.stepIndex(root.controller.setupCurrentStep) > 0
                implicitWidth: 164
                onClicked: root.controller.goToSetupPreviousStep()
            }

            Item {
                Layout.fillWidth: true
            }

            PrimaryButton {
                theme: root.theme
                tone: "primary"
                text: root.controller.setupCurrentStep === "finish" ? "READY" : "NEXT"
                enabled: root.canAdvance() && root.controller.setupCurrentStep !== "finish"
                implicitWidth: 164
                onClicked: root.controller.goToSetupNextStep()
            }
        }
    }
}
