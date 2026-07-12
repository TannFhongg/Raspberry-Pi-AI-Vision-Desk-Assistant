import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    property string selectedSsid: ""

    ScrollView {
        anchors.fill: parent
        clip: true

        ColumnLayout {
            width: parent.width
            spacing: 22

            Text {
                text: "Device Setup"
                color: root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 46
                font.weight: root.theme.weightHeavy
                Layout.fillWidth: true
            }

            Text {
                text: "Connect Wi-Fi, verify the OpenAI key, test camera/GPIO, then finish setup."
                color: root.theme.textSecondary
                font.family: root.theme.displayFont
                font.pixelSize: 26
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            GridLayout {
                columns: 2
                columnSpacing: 26
                rowSpacing: 22
                Layout.fillWidth: true

                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: root.theme.radiusCard
                    border.width: root.theme.borderStrong
                    border.color: root.theme.text
                    color: root.theme.surface

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 12

                        Text {
                            text: "1/ WIFI"
                            color: root.theme.text
                            font.family: root.theme.displayFont
                            font.pixelSize: 30
                            font.weight: root.theme.weightStrong
                        }

                        StatusPill {
                            theme: root.theme
                            label: "status"
                            value: root.controller.setupWifiStatus.toUpperCase()
                            tone: root.controller.setupWifiStatus
                            Layout.fillWidth: true
                        }

                        Text {
                            text: root.controller.setupWifiMessage
                            color: root.theme.textSecondary
                            font.family: root.theme.bodyFont
                            font.pixelSize: 18
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        ActionButton {
                            theme: root.theme
                            text: "Scan Wi-Fi"
                            onClicked: root.controller.scanWifi()
                        }

                        ListView {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 150
                            clip: true
                            model: root.controller.wifiNetworksModel
                            spacing: 8

                            delegate: Rectangle {
                                width: ListView.view.width
                                height: 46
                                radius: 18
                                border.width: 2
                                border.color: root.selectedSsid === model.ssid ? root.theme.primary : "#bbc4ce"
                                color: root.selectedSsid === model.ssid ? "#eef7ff" : root.theme.mutedFill

                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: root.selectedSsid = model.ssid
                                }

                                Text {
                                    anchors.centerIn: parent
                                    text: model.ssid + " • " + model.security
                                    color: root.theme.text
                                    font.family: root.theme.displayFont
                                    font.pixelSize: 20
                                    font.weight: root.theme.weightStrong
                                }
                            }
                        }

                        TextField {
                            id: manualSsidField
                            placeholderText: "Manual hidden SSID"
                            font.pixelSize: 18
                            Layout.fillWidth: true
                        }

                        TextField {
                            id: passwordField
                            placeholderText: "Wi-Fi password"
                            echoMode: TextInput.Password
                            font.pixelSize: 18
                            Layout.fillWidth: true
                        }

                        ActionButton {
                            theme: root.theme
                            primary: true
                            text: "Connect Wi-Fi"
                            onClicked: {
                                root.controller.connectWifi(root.selectedSsid, manualSsidField.text, passwordField.text)
                                passwordField.text = ""
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

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 12

                        Text {
                            text: "2/ OPENAI KEY"
                            color: root.theme.text
                            font.family: root.theme.displayFont
                            font.pixelSize: 30
                            font.weight: root.theme.weightStrong
                        }

                        StatusPill {
                            theme: root.theme
                            label: "status"
                            value: root.controller.setupOpenAiStatus.toUpperCase()
                            tone: root.controller.setupOpenAiStatus
                            Layout.fillWidth: true
                        }

                        Text {
                            text: root.controller.setupOpenAiMessage
                            color: root.theme.textSecondary
                            font.family: root.theme.bodyFont
                            font.pixelSize: 18
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Text {
                            visible: root.controller.setupMaskedOpenAiKey.length > 0
                            text: "Saved key: " + root.controller.setupMaskedOpenAiKey
                            color: "#16713e"
                            font.family: root.theme.displayFont
                            font.pixelSize: 18
                            font.weight: root.theme.weightStrong
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                        }

                        TextField {
                            id: openAiKeyField
                            placeholderText: "OPENAI_API_KEY"
                            echoMode: TextInput.Password
                            font.pixelSize: 18
                            Layout.fillWidth: true
                        }

                        ActionButton {
                            theme: root.theme
                            primary: true
                            text: "Save + Verify"
                            onClicked: {
                                root.controller.verifyApiKey(openAiKeyField.text)
                                openAiKeyField.text = ""
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: root.theme.radiusCard
                    border.width: root.theme.borderStrong
                    border.color: root.theme.text
                    color: root.theme.surface

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 12

                        Text {
                            text: "3/ CAMERA"
                            color: root.theme.text
                            font.family: root.theme.displayFont
                            font.pixelSize: 30
                            font.weight: root.theme.weightStrong
                        }

                        StatusPill {
                            theme: root.theme
                            label: "status"
                            value: root.controller.setupCameraStatus.toUpperCase()
                            tone: root.controller.setupCameraStatus
                            Layout.fillWidth: true
                        }

                        Text {
                            text: root.controller.setupCameraMessage
                            color: root.theme.textSecondary
                            font.family: root.theme.bodyFont
                            font.pixelSize: 18
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        ActionButton {
                            theme: root.theme
                            primary: true
                            text: "Run Camera Test"
                            onClicked: root.controller.runCameraTest()
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    radius: root.theme.radiusCard
                    border.width: root.theme.borderStrong
                    border.color: root.theme.text
                    color: root.theme.surface

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 20
                        spacing: 12

                        Text {
                            text: "4/ GPIO"
                            color: root.theme.text
                            font.family: root.theme.displayFont
                            font.pixelSize: 30
                            font.weight: root.theme.weightStrong
                        }

                        StatusPill {
                            theme: root.theme
                            label: "status"
                            value: root.controller.setupGpioStatus.toUpperCase()
                            tone: root.controller.setupGpioStatus
                            Layout.fillWidth: true
                        }

                        Text {
                            text: root.controller.setupGpioMessage
                            color: root.theme.textSecondary
                            font.family: root.theme.bodyFont
                            font.pixelSize: 18
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }

                        Repeater {
                            model: root.controller.gpioRequirementsModel

                            delegate: Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 42
                                radius: 16
                                border.width: 2
                                border.color: model.pressed ? "#2d9b5d" : "#bbc4ce"
                                color: model.pressed ? root.theme.successFill : root.theme.mutedFill

                                Text {
                                    anchors.centerIn: parent
                                    text: model.label + " • GPIO " + model.pin
                                    color: root.theme.text
                                    font.family: root.theme.displayFont
                                    font.pixelSize: 18
                                    font.weight: root.theme.weightStrong
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            ActionButton {
                                theme: root.theme
                                text: "Start GPIO Test"
                                enabled: !root.controller.setupGpioActive
                                onClicked: root.controller.startGpioTest()
                            }

                            ActionButton {
                                theme: root.theme
                                primary: true
                                text: "Stop GPIO Test"
                                enabled: root.controller.setupGpioActive
                                onClicked: root.controller.stopGpioTest()
                            }
                        }
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                radius: root.theme.radiusCard
                border.width: root.theme.borderStrong
                border.color: root.controller.setupReadyToFinish ? root.theme.success : root.theme.text
                color: root.theme.surface

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 24
                    spacing: 10

                    Text {
                        text: "5/ FINISH"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 30
                        font.weight: root.theme.weightStrong
                    }

                    Text {
                        text: root.controller.setupWarningsText.length > 0
                              ? root.controller.setupWarningsText
                              : "Finish setup and restart the service when ready."
                        color: root.controller.setupWarningsText.length > 0 ? "#ac2b2b" : "#16713e"
                        font.family: root.theme.displayFont
                        font.pixelSize: 20
                        font.weight: root.theme.weightStrong
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    Text {
                        visible: root.controller.setupFinishMessage.length > 0
                        text: root.controller.setupFinishMessage
                        color: "#ac2b2b"
                        font.family: root.theme.displayFont
                        font.pixelSize: 18
                        font.weight: root.theme.weightStrong
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }

                    ActionButton {
                        theme: root.theme
                        primary: true
                        text: "FINISH SETUP AND RESTART"
                        enabled: root.controller.setupReadyToFinish
                        Layout.alignment: Qt.AlignHCenter
                        implicitWidth: 420
                        onClicked: root.controller.finishSetup()
                    }
                }
            }
        }
    }
}
