import QtQuick
import QtQuick.Controls

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    property string selectedSsid: ""

    readonly property color wifiMessageColor: root.statusColor(
        root.controller.setupWifiScanStatus === "fail"
        ? "fail"
        : root.controller.setupWifiStatus
    )
    readonly property color openAiMessageColor: root.statusColor(root.controller.setupOpenAiStatus)
    readonly property color finishMessageColor: root.controller.setupReadyToFinish
                                             ? root.theme.success
                                             : root.theme.error

    function statusColor(status) {
        const normalized = (status || "").toLowerCase()
        if (normalized === "pass" || normalized === "healthy") {
            return root.theme.success
        }
        if (normalized === "fail" || normalized === "error") {
            return root.theme.error
        }
        if (normalized === "running" || normalized === "warning" || normalized === "connecting") {
            return root.theme.warning
        }
        return root.theme.textSecondary
    }

    function finishNoteText() {
        if ((root.controller.setupFinishMessage || "").length > 0) {
            return root.controller.setupFinishMessage
        }
        if ((root.controller.setupWarningsText || "").length > 0) {
            return root.controller.setupWarningsText
        }
        if (root.controller.setupReadyToFinish) {
            return "Wi-Fi connected and OpenAI key verified. Restart to enter Home."
        }
        return "Connect Wi-Fi and verify the OpenAI key before finishing setup."
    }

    Component.onCompleted: {
        if (root.controller.wifiNetworksModel.count === 0
                && root.controller.setupWifiStatus === "idle"
                && root.controller.setupWifiMessage.length === 0) {
            root.controller.scanWifi()
        }
    }

    Item {
        anchors.fill: parent

        Column {
            id: contentColumn
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: footerDivider.top
            anchors.bottomMargin: 26
            spacing: 30

            Row {
                id: setupRow
                width: parent.width
                spacing: 84

                Column {
                    width: (setupRow.width - setupRow.spacing) / 2
                    spacing: 16

                    Text {
                        text: "1/ WIFI"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 30
                        font.weight: root.theme.weightHeavy
                        renderType: Text.NativeRendering
                    }

                    Text {
                        width: parent.width
                        text: "Scan nearby SSIDs or enter one manually for hidden networks."
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 20
                        font.weight: root.theme.weightStrong
                        wrapMode: Text.WordWrap
                        renderType: Text.NativeRendering
                    }

                    Row {
                        spacing: 14

                        Item {
                            width: scanWifiLabel.implicitWidth
                            height: 48

                            Text {
                                id: scanWifiLabel
                                anchors.verticalCenter: parent.verticalCenter
                                text: "SCAN WIFI"
                                color: root.theme.text
                                font.family: root.theme.displayFont
                                font.pixelSize: 18
                                font.weight: root.theme.weightHeavy
                                renderType: Text.NativeRendering
                            }
                        }

                        ActionButton {
                            theme: root.theme
                            text: "Rescan"
                            implicitWidth: 126
                            implicitHeight: 48
                            onClicked: root.controller.scanWifi()
                        }
                    }

                    ComboBox {
                        id: scanWifiCombo
                        width: parent.width
                        height: 54
                        model: root.controller.wifiNetworksModel.count
                        currentIndex: -1
                        enabled: model > 0
                        font.family: root.theme.displayFont
                        font.pixelSize: 20
                        font.weight: root.theme.weightStrong
                        leftPadding: 22
                        rightPadding: 52
                        topPadding: 0
                        bottomPadding: 0
                        displayText: root.selectedSsid.length > 0
                                     ? root.selectedSsid
                                     : "Select a scanned SSID"

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

                    Text {
                        text: "MANUAL SSID"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 18
                        font.weight: root.theme.weightHeavy
                        renderType: Text.NativeRendering
                    }

                    SetupInputField {
                        id: manualSsidField
                        theme: root.theme
                        width: parent.width
                        placeholderText: "Use for hidden networks"
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
                        width: parent.width
                        secret: true
                        placeholderText: "Leave blank for open networks"
                    }

                    ActionButton {
                        theme: root.theme
                        primary: true
                        text: "Connect WIFI"
                        implicitWidth: 160
                        onClicked: {
                            root.controller.connectWifi(root.selectedSsid, manualSsidField.text, passwordField.text)
                            passwordField.text = ""
                        }
                    }

                    Text {
                        visible: root.controller.setupWifiMessage.length > 0
                        width: parent.width
                        text: root.controller.setupWifiMessage
                        color: root.wifiMessageColor
                        font.family: root.theme.bodyFont
                        font.pixelSize: 16
                        font.weight: root.theme.weightRegular
                        wrapMode: Text.WordWrap
                    }
                }

                Column {
                    width: (setupRow.width - setupRow.spacing) / 2
                    spacing: 16

                    Text {
                        text: "2/ OPENAI KEY"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 30
                        font.weight: root.theme.weightHeavy
                        renderType: Text.NativeRendering
                    }

                    Text {
                        width: parent.width
                        text: "Save the key into the local '.env' file."
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 20
                        font.weight: root.theme.weightStrong
                        wrapMode: Text.WordWrap
                        renderType: Text.NativeRendering
                    }

                    Text {
                        text: "OPENAI_API_KEY"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 18
                        font.weight: root.theme.weightHeavy
                        renderType: Text.NativeRendering
                    }

                    SetupInputField {
                        id: openAiKeyField
                        theme: root.theme
                        width: parent.width
                        secret: true
                        placeholderText: "Paste your key here"
                    }

                    Text {
                        visible: root.controller.setupMaskedOpenAiKey.length > 0
                        width: parent.width
                        text: "Saved key: " + root.controller.setupMaskedOpenAiKey
                        color: root.theme.success
                        font.family: root.theme.bodyFont
                        font.pixelSize: 16
                        font.weight: root.theme.weightRegular
                        wrapMode: Text.WordWrap
                    }

                    ActionButton {
                        theme: root.theme
                        primary: true
                        text: "Save and verify the key"
                        implicitWidth: 286
                        onClicked: {
                            root.controller.verifyApiKey(openAiKeyField.text)
                            openAiKeyField.text = ""
                        }
                    }

                    Text {
                        visible: root.controller.setupOpenAiMessage.length > 0
                        width: parent.width
                        text: root.controller.setupOpenAiMessage
                        color: root.openAiMessageColor
                        font.family: root.theme.bodyFont
                        font.pixelSize: 16
                        font.weight: root.theme.weightRegular
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Item {
                width: parent.width
                height: finishColumn.implicitHeight

                Column {
                    id: finishColumn
                    anchors.horizontalCenter: parent.horizontalCenter
                    spacing: 14

                    ActionButton {
                        theme: root.theme
                        primary: true
                        text: "FINISH SETUP AND RESTART"
                        enabled: root.controller.setupReadyToFinish
                        implicitWidth: 578
                        onClicked: root.controller.finishSetup()
                    }

                    Text {
                        width: 720
                        horizontalAlignment: Text.AlignHCenter
                        text: root.finishNoteText()
                        color: root.finishMessageColor
                        font.family: root.theme.bodyFont
                        font.pixelSize: 16
                        font.weight: root.theme.weightRegular
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }

        Rectangle {
            id: footerDivider
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: root.theme.dividerStrong
            color: root.theme.primary
        }
    }
}
