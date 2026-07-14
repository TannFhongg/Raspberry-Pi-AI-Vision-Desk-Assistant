import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    property string pendingResetMode: ""
    property string pendingResetTitle: ""
    property string pendingResetDescription: ""
    property bool pendingRemoveWifiProfile: false
    property int navigationIndex: 0

    readonly property int navigationItemCount: root.controller.modeCardsModel.count + 3

    function moveNavigation(delta) {
        if (root.navigationItemCount <= 0)
            return
        root.navigationIndex = (root.navigationIndex + delta + root.navigationItemCount)
                               % root.navigationItemCount
    }

    function handleNavigation(action) {
        if (deviceActionsDialog.visible) {
            if (action === "back")
                deviceActionsDialog.close()
            return true
        }
        if (action === "up") {
            root.moveNavigation(-1)
            return true
        }
        if (action === "down") {
            root.moveNavigation(1)
            return true
        }
        if (action === "select") {
            var modeCount = root.controller.modeCardsModel.count
            if (root.navigationIndex < modeCount) {
                var mode = root.controller.modeCardsModel.get(root.navigationIndex)
                root.controller.selectMode(mode.id || mode.mode_id || "")
            } else if (root.navigationIndex === modeCount) {
                root.controller.openHistory()
            } else if (root.navigationIndex === modeCount + 1) {
                root.openDeviceActionsPreview()
            } else {
                root.controller.openSettings()
            }
            return true
        }
        return action === "back"
    }

    function configureReset(mode) {
        pendingResetMode = mode
        pendingRemoveWifiProfile = false
        if (mode === "configuration") {
            pendingResetTitle = "Reset Configuration"
            pendingResetDescription = "Clear the OpenAI key, reset device overrides, and return to the Setup Wizard."
            return
        }
        if (mode === "factory_reset") {
            pendingResetTitle = "Full Factory Reset"
            pendingResetDescription = "Clear configuration, setup completion, saved history, retry data, and private media while keeping the installed app in place."
            return
        }
        pendingResetTitle = "User-Data Reset"
        pendingResetDescription = "Clear saved history, retry queue, cached previews, and private media while leaving setup and secrets in place."
    }

    function actionStatusColor() {
        if (root.controller.deviceActionsTone === "error")
            return root.theme.error
        if (root.controller.deviceActionsTone === "success")
            return root.theme.success
        if (root.controller.deviceActionsTone === "active")
            return root.theme.primaryStrong
        return root.theme.textSecondary
    }

    function launchSelectedReset() {
        if (pendingResetMode === "configuration") {
            root.controller.runConfigurationReset()
            return
        }
        if (pendingResetMode === "factory_reset") {
            root.controller.runFullFactoryReset(pendingRemoveWifiProfile)
            return
        }
        root.controller.deleteAllData()
    }

    function openDeviceActionsPreview() {
        deviceActionsDialog.open()
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        RowLayout {
            Layout.fillWidth: true

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: "Choose a task"
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 34
                    font.weight: root.theme.weightHeavy
                    renderType: Text.NativeRendering
                }

                Text {
                    text: "Select the assistant mode that best matches what is in front of the camera."
                    color: root.theme.textMuted
                    font.family: root.theme.bodyFont
                    font.pixelSize: 15
                    font.weight: root.theme.weightRegular
                    renderType: Text.NativeRendering
                }
            }

            StatusChip {
                theme: root.theme
                label: "Device"
                value: root.controller.applicationState === "READY" ? "Ready" : root.controller.applicationState
                tone: root.controller.applicationState === "READY" ? "success" : "info"
            }
        }

        ContentCard {
            theme: root.theme
            padding: 18
            Layout.fillWidth: true
            Layout.preferredHeight: 430
            Layout.maximumHeight: 430

            GridLayout {
                anchors.fill: parent
                columns: 3
                columnSpacing: 14
                rowSpacing: 14

                Repeater {
                    model: root.controller.modeCardsModel.count

                    delegate: ModeCard {
                        required property int index
                        property var itemData: root.controller.modeCardsModel.get(index)
                        theme: root.theme
                        modeId: itemData.id || itemData.mode_id || ""
                        title: itemData.name || ""
                        description: itemData.description || ""
                        selected: (itemData.id || itemData.mode_id || "") === root.controller.selectedMode
                        navigationFocused: root.navigationIndex === index
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumWidth: 0
                        Layout.preferredHeight: 142
                        onClicked: root.controller.selectMode(itemData.id || itemData.mode_id || "")
                    }
                }
            }
        }

        Text {
            Layout.fillWidth: true
            visible: (root.controller.deviceActionsStatus || "") !== ""
            text: root.controller.deviceActionsStatus
            color: root.actionStatusColor()
            font.family: root.theme.bodyFont
            font.pixelSize: 15
            font.weight: root.theme.weightStrong
            wrapMode: Text.WordWrap
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            SecondaryButton {
                theme: root.theme
                text: "RECENT RESULTS"
                implicitWidth: 210
                navigationFocused: root.navigationIndex === root.controller.modeCardsModel.count
                onClicked: root.controller.openHistory()
            }

            NavigationHint {
                theme: root.theme
                text: "UP/DOWN Choose  ·  SELECT Open"
                Layout.fillWidth: true
            }

            SecondaryButton {
                theme: root.theme
                tone: "danger"
                text: "DEVICE ACTIONS"
                implicitWidth: 210
                enabled: !root.controller.deviceActionsBusy
                navigationFocused: root.navigationIndex === root.controller.modeCardsModel.count + 1
                onClicked: deviceActionsDialog.open()
            }

            SecondaryButton {
                theme: root.theme
                text: "SETTINGS"
                implicitWidth: 156
                navigationFocused: root.navigationIndex === root.controller.modeCardsModel.count + 2
                onClicked: root.controller.openSettings()
            }
        }
    }

    Dialog {
        id: deviceActionsDialog
        anchors.centerIn: parent
        modal: true
        focus: true
        width: 860
        padding: 24
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            radius: root.theme.radiusSetupCard
            border.width: 1
            border.color: root.theme.borderSoft
            color: root.theme.surface
        }

        contentItem: ColumnLayout {
            spacing: 16

            RowLayout {
                Layout.fillWidth: true
                spacing: 16

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2

                    Text {
                        text: "Device Actions"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 32
                        font.weight: root.theme.weightHeavy
                        renderType: Text.NativeRendering
                    }

                    Text {
                        text: "Choose exactly what to reset. VisionDesk and its installed service remain in place."
                        color: root.theme.textMuted
                        font.family: root.theme.bodyFont
                        font.pixelSize: 15
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }

                StatusChip {
                    theme: root.theme
                    label: "Safety"
                    value: "3 reset modes"
                    tone: "warning"
                }
            }

            GridLayout {
                columns: 3
                columnSpacing: 14
                Layout.fillWidth: true

                ContentCard {
                    theme: root.theme
                    padding: 16
                    fillColor: root.theme.surface
                    borderColor: "#C9DCFF"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredHeight: 248

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        RowLayout {
                            Layout.fillWidth: true

                            Rectangle {
                                Layout.preferredWidth: 42
                                Layout.preferredHeight: 42
                                radius: 14
                                color: root.theme.primarySoft

                                Text {
                                    anchors.centerIn: parent
                                    text: "DATA"
                                    color: root.theme.primaryStrong
                                    font.family: root.theme.displayFont
                                    font.pixelSize: 11
                                    font.weight: root.theme.weightHeavy
                                }
                            }

                            Item { Layout.fillWidth: true }

                            StatusChip {
                                theme: root.theme
                                label: "Keeps setup"
                                tone: "info"
                            }
                        }

                        Text {
                            text: "Clear user data"
                            color: root.theme.text
                            font.family: root.theme.displayFont
                            font.pixelSize: 23
                            font.weight: root.theme.weightHeavy
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            text: "Remove history, retry queue, cached previews, and private media."
                            color: root.theme.textMuted
                            font.family: root.theme.bodyFont
                            font.pixelSize: 14
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }

                        Item { Layout.fillHeight: true }

                        PrimaryButton {
                            theme: root.theme
                            text: "CLEAR DATA"
                            Layout.fillWidth: true
                            enabled: !root.controller.deviceActionsBusy
                            onClicked: {
                                root.configureReset("user_data")
                                deviceActionsDialog.close()
                                confirmResetDialog.open()
                            }
                        }
                    }
                }

                ContentCard {
                    theme: root.theme
                    padding: 16
                    fillColor: root.theme.surface
                    borderColor: "#F1D38C"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredHeight: 248

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        RowLayout {
                            Layout.fillWidth: true

                            Rectangle {
                                Layout.preferredWidth: 42
                                Layout.preferredHeight: 42
                                radius: 14
                                color: root.theme.warningFill

                                Text {
                                    anchors.centerIn: parent
                                    text: "CFG"
                                    color: root.theme.warningStrong
                                    font.family: root.theme.displayFont
                                    font.pixelSize: 11
                                    font.weight: root.theme.weightHeavy
                                }
                            }

                            Item { Layout.fillWidth: true }

                            StatusChip {
                                theme: root.theme
                                label: "Returns to setup"
                                tone: "warning"
                            }
                        }

                        Text {
                            text: "Reset configuration"
                            color: root.theme.text
                            font.family: root.theme.displayFont
                            font.pixelSize: 23
                            font.weight: root.theme.weightHeavy
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            text: "Clear the OpenAI key, setup completion, and device overrides."
                            color: root.theme.textMuted
                            font.family: root.theme.bodyFont
                            font.pixelSize: 14
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }

                        Item { Layout.fillHeight: true }

                        PrimaryButton {
                            theme: root.theme
                            text: "RESET CONFIG"
                            Layout.fillWidth: true
                            enabled: !root.controller.deviceActionsBusy
                            onClicked: {
                                root.configureReset("configuration")
                                deviceActionsDialog.close()
                                confirmResetDialog.open()
                            }
                        }
                    }
                }

                ContentCard {
                    theme: root.theme
                    padding: 16
                    fillColor: root.theme.surface
                    borderColor: "#F0BABA"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredHeight: 248

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 10

                        RowLayout {
                            Layout.fillWidth: true

                            Rectangle {
                                Layout.preferredWidth: 42
                                Layout.preferredHeight: 42
                                radius: 14
                                color: root.theme.errorFill

                                Text {
                                    anchors.centerIn: parent
                                    text: "!"
                                    color: root.theme.errorStrong
                                    font.family: root.theme.displayFont
                                    font.pixelSize: 24
                                    font.weight: root.theme.weightHeavy
                                }
                            }

                            Item { Layout.fillWidth: true }

                            StatusChip {
                                theme: root.theme
                                label: "Most destructive"
                                tone: "error"
                            }
                        }

                        Text {
                            text: "Full factory reset"
                            color: root.theme.text
                            font.family: root.theme.displayFont
                            font.pixelSize: 23
                            font.weight: root.theme.weightHeavy
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }

                        Text {
                            text: "Clear configuration and all private data, then return to Setup."
                            color: root.theme.textMuted
                            font.family: root.theme.bodyFont
                            font.pixelSize: 14
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }

                        Item { Layout.fillHeight: true }

                        PrimaryButton {
                            theme: root.theme
                            tone: "danger"
                            text: "FULL RESET"
                            Layout.fillWidth: true
                            enabled: !root.controller.deviceActionsBusy
                            onClicked: {
                                root.configureReset("factory_reset")
                                deviceActionsDialog.close()
                                fullResetDialog.open()
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 14

                Text {
                    text: "All reset actions require confirmation."
                    color: root.theme.textMuted
                    font.family: root.theme.bodyFont
                    font.pixelSize: 13
                    Layout.fillWidth: true
                }

                SecondaryButton {
                    theme: root.theme
                    text: "CLOSE"
                    onClicked: deviceActionsDialog.close()
                }
            }
        }
    }

    Dialog {
        id: confirmResetDialog
        anchors.centerIn: parent
        modal: true
        focus: true
        width: 600
        padding: 24
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            radius: root.theme.radiusSetupCard
            border.width: 1
            border.color: root.theme.borderSoft
            color: root.theme.surface
        }

        contentItem: ColumnLayout {
            spacing: 16

            RowLayout {
                Layout.fillWidth: true

                Rectangle {
                    Layout.preferredWidth: 42
                    Layout.preferredHeight: 42
                    radius: 14
                    color: root.pendingResetMode === "configuration" ? root.theme.warningFill : root.theme.errorFill

                    Text {
                        anchors.centerIn: parent
                        text: "!"
                        color: root.pendingResetMode === "configuration" ? root.theme.warningStrong : root.theme.errorStrong
                        font.family: root.theme.displayFont
                        font.pixelSize: 24
                        font.weight: root.theme.weightHeavy
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1

                    Text {
                        text: "Confirm action"
                        color: root.theme.textMuted
                        font.family: root.theme.bodyFont
                        font.pixelSize: 13
                        font.weight: root.theme.weightStrong
                    }

                    Text {
                        text: root.pendingResetTitle
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 28
                        font.weight: root.theme.weightHeavy
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Text {
                text: root.pendingResetDescription
                color: root.theme.textSecondary
                font.family: root.theme.bodyFont
                font.pixelSize: 16
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            ContentCard {
                theme: root.theme
                padding: 16
                fillColor: root.pendingResetMode === "configuration" ? root.theme.warningFill : root.theme.errorFill
                borderColor: root.pendingResetMode === "configuration" ? "#F1D38C" : "#F0BABA"
                Layout.fillWidth: true
                Layout.preferredHeight: 94

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 5

                    Text {
                        text: "Affected areas"
                        color: root.pendingResetMode === "configuration" ? root.theme.warningStrong : root.theme.errorStrong
                        font.family: root.theme.bodyFont
                        font.pixelSize: 13
                        font.weight: root.theme.weightStrong
                    }

                    Text {
                        text: root.pendingResetMode === "configuration"
                            ? "/etc/visiondesk/visiondesk.env, device.yaml, and setup state."
                            : "Private media, saved results, retry queue, and cached previews."
                        color: root.theme.text
                        font.family: root.theme.bodyFont
                        font.pixelSize: 15
                        font.weight: root.theme.weightRegular
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item { Layout.fillWidth: true }

                SecondaryButton {
                    theme: root.theme
                    text: "CANCEL"
                    onClicked: confirmResetDialog.close()
                }

                PrimaryButton {
                    theme: root.theme
                    tone: root.pendingResetMode === "configuration" ? "primary" : "danger"
                    text: root.pendingResetMode === "configuration" ? "RESET NOW" : "CLEAR NOW"
                    enabled: !root.controller.deviceActionsBusy
                    onClicked: {
                        confirmResetDialog.close()
                        root.launchSelectedReset()
                    }
                }
            }
        }
    }

    Dialog {
        id: fullResetDialog
        anchors.centerIn: parent
        modal: true
        focus: true
        width: 640
        padding: 24
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            radius: root.theme.radiusSetupCard
            border.width: 1
            border.color: root.theme.borderSoft
            color: root.theme.surface
        }

        contentItem: ColumnLayout {
            spacing: 16

            RowLayout {
                Layout.fillWidth: true

                Rectangle {
                    Layout.preferredWidth: 44
                    Layout.preferredHeight: 44
                    radius: 15
                    color: root.theme.errorFill

                    Text {
                        anchors.centerIn: parent
                        text: "!"
                        color: root.theme.errorStrong
                        font.family: root.theme.displayFont
                        font.pixelSize: 25
                        font.weight: root.theme.weightHeavy
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1

                    Text {
                        text: "Full Factory Reset"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 30
                        font.weight: root.theme.weightHeavy
                    }

                    Text {
                        text: "Strongest recovery path"
                        color: root.theme.errorStrong
                        font.family: root.theme.bodyFont
                        font.pixelSize: 13
                        font.weight: root.theme.weightStrong
                    }
                }
            }

            ContentCard {
                theme: root.theme
                padding: 16
                fillColor: root.theme.errorFill
                borderColor: "#F0BABA"
                Layout.fillWidth: true
                Layout.preferredHeight: 88

                Text {
                    anchors.fill: parent
                    text: "This clears configuration, setup completion, saved history, retry data, and private media. VisionDesk remains installed and then relaunches into Setup."
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                    verticalAlignment: Text.AlignVCenter
                }
            }

            CheckBox {
                id: removeWifiCheckbox
                text: "Also remove the saved Wi-Fi profile after final confirmation"
                checked: false
                Layout.fillWidth: true
                onToggled: root.pendingRemoveWifiProfile = checked

                indicator: Rectangle {
                    implicitWidth: 22
                    implicitHeight: 22
                    x: removeWifiCheckbox.leftPadding
                    y: (removeWifiCheckbox.height - height) / 2
                    radius: 7
                    color: removeWifiCheckbox.checked ? root.theme.primaryStrong : root.theme.surface
                    border.width: 1
                    border.color: removeWifiCheckbox.checked ? root.theme.primaryStrong : root.theme.borderMuted

                    Text {
                        anchors.centerIn: parent
                        visible: removeWifiCheckbox.checked
                        text: "OK"
                        color: root.theme.surface
                        font.family: root.theme.displayFont
                        font.pixelSize: 10
                        font.weight: root.theme.weightHeavy
                    }
                }

                contentItem: Text {
                    text: removeWifiCheckbox.text
                    leftPadding: removeWifiCheckbox.indicator.width + 10
                    color: root.theme.textSecondary
                    font.family: root.theme.bodyFont
                    font.pixelSize: 15
                    wrapMode: Text.WordWrap
                    verticalAlignment: Text.AlignVCenter
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "Safety phrase"
                    color: root.theme.text
                    font.family: root.theme.bodyFont
                    font.pixelSize: 13
                    font.weight: root.theme.weightStrong
                }

                Text {
                    text: "Type ERASE VISIONDESK to unlock the final confirmation."
                    color: root.theme.textMuted
                    font.family: root.theme.bodyFont
                    font.pixelSize: 14
                }

                TextField {
                    id: fullResetPhraseField
                    Layout.fillWidth: true
                    implicitHeight: 50
                    placeholderText: "ERASE VISIONDESK"
                    color: root.theme.text
                    font.family: root.theme.bodyFont
                    font.pixelSize: 18
                    leftPadding: 16
                    rightPadding: 16
                    background: Rectangle {
                        radius: root.theme.radiusControl
                        border.width: 1
                        border.color: fullResetPhraseField.activeFocus ? root.theme.primaryStrong : root.theme.borderMuted
                        color: root.theme.surface
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item { Layout.fillWidth: true }

                SecondaryButton {
                    theme: root.theme
                    text: "CANCEL"
                    onClicked: {
                        fullResetPhraseField.text = ""
                        removeWifiCheckbox.checked = false
                        root.pendingRemoveWifiProfile = false
                        fullResetDialog.close()
                    }
                }

                PrimaryButton {
                    theme: root.theme
                    tone: "danger"
                    text: "CONTINUE"
                    enabled: fullResetPhraseField.text.trim() === "ERASE VISIONDESK" && !root.controller.deviceActionsBusy
                    onClicked: {
                        fullResetDialog.close()
                        holdResetDialog.open()
                    }
                }
            }
        }

    }

    Dialog {
        id: holdResetDialog
        anchors.centerIn: parent
        modal: true
        focus: true
        width: 620
        padding: 24
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            radius: root.theme.radiusSetupCard
            border.width: 1
            border.color: root.theme.borderSoft
            color: root.theme.surface
        }

        contentItem: ColumnLayout {
            spacing: 16

            RowLayout {
                Layout.fillWidth: true

                Rectangle {
                    Layout.preferredWidth: 42
                    Layout.preferredHeight: 42
                    radius: 14
                    color: root.theme.errorFill

                    Text {
                        anchors.centerIn: parent
                        text: "!"
                        color: root.theme.errorStrong
                        font.family: root.theme.displayFont
                        font.pixelSize: 24
                        font.weight: root.theme.weightHeavy
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1

                    Text {
                        text: "Final confirmation"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 29
                        font.weight: root.theme.weightHeavy
                    }

                    Text {
                        text: "Press and hold is required"
                        color: root.theme.errorStrong
                        font.family: root.theme.bodyFont
                        font.pixelSize: 13
                        font.weight: root.theme.weightStrong
                    }
                }
            }

            Text {
                text: root.pendingRemoveWifiProfile
                    ? "Keep holding to erase VisionDesk and remove the saved Wi-Fi profile."
                    : "Keep holding to erase VisionDesk and relaunch into Setup Wizard."
                color: root.theme.textSecondary
                font.family: root.theme.bodyFont
                font.pixelSize: 16
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Rectangle {
                id: holdSurface
                Layout.fillWidth: true
                Layout.preferredHeight: 100
                radius: root.theme.radiusControl
                color: root.controller.deviceActionsBusy ? root.theme.mutedFill : root.theme.errorStrong
                border.width: 1
                border.color: root.controller.deviceActionsBusy ? root.theme.borderMuted : "#C83E3E"

                ColumnLayout {
                    anchors.centerIn: parent
                    spacing: 3

                    Text {
                        text: root.controller.deviceActionsBusy ? "RESETTING..." : "PRESS AND HOLD TO ERASE"
                        color: root.controller.deviceActionsBusy ? root.theme.unavailable : root.theme.surface
                        font.family: root.theme.displayFont
                        font.pixelSize: 23
                        font.weight: root.theme.weightHeavy
                        Layout.alignment: Qt.AlignHCenter
                    }

                    Text {
                        visible: !root.controller.deviceActionsBusy
                        text: "Hold for 1.6 seconds"
                        color: Qt.rgba(1, 1, 1, 0.78)
                        font.family: root.theme.bodyFont
                        font.pixelSize: 13
                        Layout.alignment: Qt.AlignHCenter
                    }
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: !root.controller.deviceActionsBusy
                    pressAndHoldInterval: 1600
                    onPressed: holdSurface.opacity = 0.86
                    onReleased: holdSurface.opacity = 1.0
                    onCanceled: holdSurface.opacity = 1.0
                    onPressAndHold: {
                        holdSurface.opacity = 1.0
                        holdResetDialog.close()
                        root.launchSelectedReset()
                    }
                }
            }

            Text {
                text: root.controller.deviceActionsBusy
                    ? root.controller.deviceActionsStatus
                    : "Release at any time to cancel this final action."
                color: root.actionStatusColor()
                font.family: root.theme.bodyFont
                font.pixelSize: 14
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true

                Item { Layout.fillWidth: true }

                SecondaryButton {
                    theme: root.theme
                    text: "BACK"
                    enabled: !root.controller.deviceActionsBusy
                    onClicked: holdResetDialog.close()
                }
            }
        }

        onClosed: {
            fullResetPhraseField.text = ""
            removeWifiCheckbox.checked = false
            root.pendingRemoveWifiProfile = false
        }
    }
}
