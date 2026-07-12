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

    function cardWidthFor(index, availableWidth) {
        if (index >= 3) {
            return Math.max(280, (availableWidth - 26) / 2)
        }
        return Math.max(240, (availableWidth - (26 * 2)) / 3)
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

    ColumnLayout {
        anchors.fill: parent
        spacing: 24

        Text {
            text: "What would you like to do?"
            color: root.theme.text
            font.family: root.theme.displayFont
            font.pixelSize: 54
            font.weight: root.theme.weightHeavy
            Layout.fillWidth: true
        }

        Flow {
            id: modeFlow
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 26

            Repeater {
                model: root.controller.modeCardsModel.count

                delegate: ModeCard {
                    required property int index
                    property var itemData: root.controller.modeCardsModel.get(index)
                    theme: root.theme
                    title: itemData.name || ""
                    description: itemData.description || ""
                    selected: (itemData.id || "") === root.controller.selectedMode
                    width: root.cardWidthFor(index, modeFlow.width)
                    height: 170
                    onClicked: root.controller.selectMode(itemData.id || "")
                }
            }
        }

        Text {
            Layout.fillWidth: true
            visible: (root.controller.deviceActionsStatus || "") !== ""
            text: root.controller.deviceActionsStatus
            color: root.actionStatusColor()
            font.family: root.theme.bodyFont
            font.pixelSize: 20
            font.weight: root.theme.weightStrong
            wrapMode: Text.WordWrap
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            ActionButton {
                theme: root.theme
                text: "RECENT RESULTS"
                implicitWidth: 248
                onClicked: root.controller.openHistory()
            }

            Item {
                Layout.fillWidth: true
            }

            ActionButton {
                theme: root.theme
                destructive: true
                text: "DEVICE ACTIONS"
                implicitWidth: 248
                enabled: !root.controller.deviceActionsBusy
                onClicked: deviceActionsDialog.open()
            }
        }
    }

    Dialog {
        id: deviceActionsDialog
        anchors.centerIn: parent
        modal: true
        focus: true
        width: 620
        padding: 0
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            radius: root.theme.radiusCard
            border.width: root.theme.borderStrong
            border.color: root.theme.text
            color: root.theme.surface
        }

        contentItem: ColumnLayout {
            spacing: 18

            Text {
                text: "Device Actions"
                color: root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 34
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
            }

            Text {
                text: "Use these tools carefully. Configuration Reset returns to Setup Wizard. User-Data Reset keeps setup in place. Full Factory Reset clears both."
                color: root.theme.textSecondary
                font.family: root.theme.bodyFont
                font.pixelSize: 19
                font.weight: root.theme.weightRegular
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Rectangle {
                Layout.fillWidth: true
                radius: root.theme.radiusCardSm
                color: root.theme.mutedFill
                border.width: 1
                border.color: "#d2dae3"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 12

                    Text {
                        text: "User-Data Reset"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 28
                        font.weight: root.theme.weightStrong
                    }

                    Text {
                        text: "Clears history, retry queue, cached previews, and private media."
                        color: root.theme.textSecondary
                        font.family: root.theme.bodyFont
                        font.pixelSize: 18
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    ActionButton {
                        theme: root.theme
                        text: "CLEAR USER DATA"
                        enabled: !root.controller.deviceActionsBusy
                        onClicked: {
                            root.configureReset("user_data")
                            deviceActionsDialog.close()
                            confirmResetDialog.open()
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                radius: root.theme.radiusCardSm
                color: root.theme.warningFill
                border.width: 1
                border.color: "#e2c16b"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 12

                    Text {
                        text: "Configuration Reset"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 28
                        font.weight: root.theme.weightStrong
                    }

                    Text {
                        text: "Clears the OpenAI key, setup completion, and device overrides. VisionDesk restarts directly into Setup Wizard."
                        color: root.theme.textSecondary
                        font.family: root.theme.bodyFont
                        font.pixelSize: 18
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    ActionButton {
                        theme: root.theme
                        text: "RESET CONFIGURATION"
                        enabled: !root.controller.deviceActionsBusy
                        onClicked: {
                            root.configureReset("configuration")
                            deviceActionsDialog.close()
                            confirmResetDialog.open()
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                radius: root.theme.radiusCardSm
                color: root.theme.errorFill
                border.width: 1
                border.color: "#d98282"

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 18
                    spacing: 12

                    Text {
                        text: "Full Factory Reset"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 28
                        font.weight: root.theme.weightStrong
                    }

                    Text {
                        text: "Clears configuration plus all user data. This keeps the installed app and service, then relaunches into Setup Wizard."
                        color: root.theme.textSecondary
                        font.family: root.theme.bodyFont
                        font.pixelSize: 18
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    ActionButton {
                        theme: root.theme
                        destructive: true
                        text: "FULL FACTORY RESET"
                        enabled: !root.controller.deviceActionsBusy
                        onClicked: {
                            root.configureReset("factory_reset")
                            deviceActionsDialog.close()
                            fullResetDialog.open()
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 14

                Item {
                    Layout.fillWidth: true
                }

                ActionButton {
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
        width: 560
        padding: 0
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            radius: root.theme.radiusCard
            border.width: root.theme.borderStrong
            border.color: root.theme.text
            color: root.theme.surface
        }

        contentItem: ColumnLayout {
            spacing: 20

            Text {
                text: root.pendingResetTitle
                color: root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 32
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Text {
                text: root.pendingResetDescription
                color: root.theme.textSecondary
                font.family: root.theme.bodyFont
                font.pixelSize: 20
                font.weight: root.theme.weightRegular
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Text {
                text: root.pendingResetMode === "configuration"
                    ? "Affected areas: /etc/visiondesk/visiondesk.env, /etc/visiondesk/device.yaml, and /var/lib/visiondesk/setup_state.json."
                    : "Affected areas: /var/lib/visiondesk/private, /var/lib/visiondesk/result_history.json, /var/lib/visiondesk/latest_result.txt, and retry queue data."
                color: root.theme.text
                font.family: root.theme.bodyFont
                font.pixelSize: 18
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 14

                Item {
                    Layout.fillWidth: true
                }

                ActionButton {
                    theme: root.theme
                    text: "CANCEL"
                    onClicked: confirmResetDialog.close()
                }

                ActionButton {
                    theme: root.theme
                    destructive: true
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
        width: 620
        padding: 0
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            radius: root.theme.radiusCard
            border.width: root.theme.borderStrong
            border.color: root.theme.text
            color: root.theme.surface
        }

        contentItem: ColumnLayout {
            spacing: 20

            Text {
                text: "Full Factory Reset"
                color: root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 34
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
            }

            Text {
                text: "This is the strongest reset path. It clears configuration, setup completion, saved history, retry data, and private media. The installed app stays in place."
                color: root.theme.textSecondary
                font.family: root.theme.bodyFont
                font.pixelSize: 20
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            CheckBox {
                id: removeWifiCheckbox
                text: "Also remove the saved Wi-Fi profile after the final confirmation"
                checked: false
                onToggled: root.pendingRemoveWifiProfile = checked
            }

            Text {
                text: "Type ERASE VISIONDESK to unlock the final safety step."
                color: root.theme.text
                font.family: root.theme.bodyFont
                font.pixelSize: 18
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            TextField {
                id: fullResetPhraseField
                Layout.fillWidth: true
                placeholderText: "ERASE VISIONDESK"
                color: root.theme.text
                font.family: root.theme.bodyFont
                font.pixelSize: 20
                background: Rectangle {
                    radius: root.theme.radiusCardSm
                    border.width: 2
                    border.color: fullResetPhraseField.activeFocus ? root.theme.primaryStrong : "#c7d0da"
                    color: root.theme.surface
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 14

                Item {
                    Layout.fillWidth: true
                }

                ActionButton {
                    theme: root.theme
                    text: "CANCEL"
                    onClicked: {
                        fullResetPhraseField.text = ""
                        removeWifiCheckbox.checked = false
                        root.pendingRemoveWifiProfile = false
                        fullResetDialog.close()
                    }
                }

                ActionButton {
                    theme: root.theme
                    destructive: true
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
        padding: 0
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            radius: root.theme.radiusCard
            border.width: root.theme.borderStrong
            border.color: root.theme.text
            color: root.theme.surface
        }

        contentItem: ColumnLayout {
            spacing: 20

            Text {
                text: "Final Confirmation"
                color: root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 34
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
            }

            Text {
                text: root.pendingRemoveWifiProfile
                    ? "Press and hold to erase VisionDesk and remove the saved Wi-Fi profile."
                    : "Press and hold to erase VisionDesk and relaunch into Setup Wizard."
                color: root.theme.textSecondary
                font.family: root.theme.bodyFont
                font.pixelSize: 20
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 96
                radius: root.theme.radiusPill
                border.width: root.theme.borderStrong
                border.color: root.controller.deviceActionsBusy ? "#bbc4ce" : root.theme.text
                color: root.controller.deviceActionsBusy ? root.theme.mutedFill : root.theme.errorFill

                Text {
                    anchors.centerIn: parent
                    text: root.controller.deviceActionsBusy ? "RESETTING..." : "PRESS AND HOLD TO ERASE"
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 26
                    font.weight: root.theme.weightStrong
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: !root.controller.deviceActionsBusy
                    pressAndHoldInterval: 1600
                    onPressAndHold: {
                        holdResetDialog.close()
                        root.launchSelectedReset()
                    }
                }
            }

            Text {
                text: root.controller.deviceActionsBusy
                    ? root.controller.deviceActionsStatus
                    : "Keep holding until the action starts."
                color: root.actionStatusColor()
                font.family: root.theme.bodyFont
                font.pixelSize: 18
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 14

                Item {
                    Layout.fillWidth: true
                }

                ActionButton {
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
