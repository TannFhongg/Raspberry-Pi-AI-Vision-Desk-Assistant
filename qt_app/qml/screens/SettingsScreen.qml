import QtQuick
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller
    property int navigationIndex: 0

    function handleNavigation(action) {
        if (action === "up" || action === "down") {
            root.navigationIndex = root.navigationIndex === 0 ? 1 : 0
            return true
        }
        if (action === "select") {
            if (root.navigationIndex === 0)
                root.controller.openDeviceHealth()
            else
                root.controller.goBack()
            return true
        }
        if (action === "back") {
            root.controller.goBack()
            return true
        }
        return false
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 14

        SectionTitle {
            theme: root.theme
            title: "Settings"
            subtitle: "Device information and maintenance options are kept separate from everyday capture tasks."
            Layout.fillWidth: true
        }

        ContentCard {
            theme: root.theme
            padding: 22
            navigationFocused: root.navigationIndex === 0
            Layout.fillWidth: true
            Layout.preferredHeight: 168

            MouseArea {
                anchors.fill: parent
                onClicked: root.controller.openDeviceHealth()
            }

            RowLayout {
                anchors.fill: parent
                spacing: 18

                Rectangle {
                    Layout.preferredWidth: 64
                    Layout.preferredHeight: 64
                    radius: 20
                    color: root.theme.primarySoft
                    Text { anchors.centerIn: parent; text: "H"; color: root.theme.primaryStrong; font.family: root.theme.displayFont; font.pixelSize: 28; font.weight: root.theme.weightHeavy }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text { text: "Device Health"; color: root.theme.text; font.family: root.theme.displayFont; font.pixelSize: 28; font.weight: root.theme.weightHeavy; Layout.fillWidth: true }
                    Text { text: "View connection, camera, storage, and service checks."; color: root.theme.textMuted; font.family: root.theme.bodyFont; font.pixelSize: 16; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                }

                Text { text: "OPEN"; color: root.theme.primaryStrong; font.family: root.theme.displayFont; font.pixelSize: 16; font.weight: root.theme.weightHeavy }
            }
        }

        ContentCard {
            theme: root.theme
            padding: 20
            navigationFocused: root.navigationIndex === 1
            Layout.fillWidth: true
            Layout.preferredHeight: 118
            MouseArea { anchors.fill: parent; onClicked: root.controller.goBack() }
            ColumnLayout {
                anchors.fill: parent
                Text { text: "Device Actions"; color: root.theme.text; font.family: root.theme.displayFont; font.pixelSize: 22; font.weight: root.theme.weightHeavy }
                Text { text: "Reset and data-removal controls remain available from the Home screen's Device Actions button."; color: root.theme.textMuted; font.family: root.theme.bodyFont; font.pixelSize: 15; wrapMode: Text.WordWrap; Layout.fillWidth: true }
            }
        }

        Item { Layout.fillHeight: true }

        RowLayout {
            Layout.fillWidth: true
            SecondaryButton { theme: root.theme; text: "BACK"; navigationFocused: root.navigationIndex === 1; onClicked: root.controller.goBack() }
            NavigationHint { theme: root.theme; text: "UP/DOWN Choose  ·  SELECT Open  ·  BACK Home"; Layout.fillWidth: true }
            PrimaryButton { theme: root.theme; text: "DEVICE HEALTH"; navigationFocused: root.navigationIndex === 0; onClicked: root.controller.openDeviceHealth() }
        }
    }
}
