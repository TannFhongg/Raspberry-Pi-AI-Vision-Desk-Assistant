import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller
    property int navigationIndex: 0

    function handleNavigation(action) {
        if (action === "up") {
            root.navigationIndex = (root.navigationIndex + 4) % 5
            return true
        }
        if (action === "down") {
            root.navigationIndex = (root.navigationIndex + 1) % 5
            return true
        }
        if (action === "select") {
            if (root.navigationIndex === 0) root.controller.openDeviceHealth()
            else if (root.navigationIndex === 1) root.controller.setTextSize("standard")
            else if (root.navigationIndex === 2) root.controller.setTextSize("large")
            else if (root.navigationIndex === 3) root.controller.setTextSize("extra_large")
            else root.controller.goBack()
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
        spacing: root.theme.pageSpacing

        SectionTitle {
            theme: root.theme
            title: "Settings"
            subtitle: "Display readability, device information, and maintenance options."
            Layout.fillWidth: true
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

            ColumnLayout {
                width: parent.width
                spacing: root.theme.cardSpacing

                ContentCard {
                    theme: root.theme
                    padding: 20
                    navigationFocused: root.navigationIndex === 0
                    Layout.fillWidth: true
                    Layout.preferredHeight: 146

                    MouseArea { anchors.fill: parent; onClicked: root.controller.openDeviceHealth() }

                    RowLayout {
                        anchors.fill: parent
                        spacing: 18
                        Rectangle {
                            Layout.preferredWidth: 64
                            Layout.preferredHeight: 64
                            radius: 20
                            color: root.theme.primarySoft
                            AppText { anchors.centerIn: parent; theme: root.theme; role: "sectionTitle"; decorative: true; text: "H"; color: root.theme.primaryStrong }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            AppText { theme: root.theme; role: "sectionTitle"; decorative: true; text: "Device Health"; Layout.fillWidth: true }
                            BodyText { theme: root.theme; role: "secondaryBody"; text: "View connection, camera, display, storage, and service checks."; color: root.theme.textMuted; Layout.fillWidth: true }
                        }
                        StatusText { theme: root.theme; text: "Open"; color: root.theme.primaryStrong }
                    }
                }

                ContentCard {
                    theme: root.theme
                    padding: 20
                    Layout.fillWidth: true
                    Layout.preferredHeight: 184

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: 8
                        AppText { theme: root.theme; role: "cardTitle"; text: "Text size" }
                        BodyText {
                            theme: root.theme
                            role: "secondaryBody"
                            text: "Change typography without scaling controls, camera images, or the whole interface."
                            color: root.theme.textMuted
                            Layout.fillWidth: true
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            SecondaryButton { theme: root.theme; text: "Standard"; tone: root.controller.textSize === "standard" ? "primary" : "neutral"; navigationFocused: root.navigationIndex === 1; Layout.fillWidth: true; onClicked: root.controller.setTextSize("standard") }
                            SecondaryButton { theme: root.theme; text: "Large"; tone: root.controller.textSize === "large" ? "primary" : "neutral"; navigationFocused: root.navigationIndex === 2; Layout.fillWidth: true; onClicked: root.controller.setTextSize("large") }
                            SecondaryButton { theme: root.theme; text: "Extra Large"; tone: root.controller.textSize === "extra_large" ? "primary" : "neutral"; navigationFocused: root.navigationIndex === 3; Layout.fillWidth: true; onClicked: root.controller.setTextSize("extra_large") }
                        }
                    }
                }

                ContentCard {
                    theme: root.theme
                    padding: 18
                    Layout.fillWidth: true
                    Layout.preferredHeight: 112
                    ColumnLayout {
                        anchors.fill: parent
                        AppText { theme: root.theme; role: "cardTitle"; text: "Device Actions" }
                        BodyText { theme: root.theme; role: "secondaryBody"; text: "Reset and data-removal controls remain available from Home under Device Actions."; color: root.theme.textMuted; Layout.fillWidth: true }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: root.theme.footerHeight
            SecondaryButton { theme: root.theme; text: "Back"; navigationFocused: root.navigationIndex === 4; onClicked: root.controller.goBack() }
            NavigationHint { theme: root.theme; text: "UP/DOWN Choose  ·  SELECT Open  ·  BACK Home"; Layout.fillWidth: true }
            PrimaryButton { theme: root.theme; text: "Device Health"; navigationFocused: root.navigationIndex === 0; onClicked: root.controller.openDeviceHealth() }
        }
    }
}
