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
        if (action === "up" || action === "down") {
            root.navigationIndex = root.navigationIndex === 0 ? 1 : 0
            return true
        }
        if (action === "select") {
            if (root.navigationIndex === 0)
                root.controller.refreshDeviceHealth()
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
        spacing: root.theme.pageSpacing

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                HeadingText { theme: root.theme; text: "Device Health" }
                AppText { theme: root.theme; role: "secondaryBody"; text: "Plain-language checks with non-sensitive display details below."; color: root.theme.textMuted }
            }
            AppStatusBadge { theme: root.theme; text: root.controller.globalStatusText; tone: root.controller.globalStatusTone }
        }

        ContentCard {
            theme: root.theme
            padding: 14
            Layout.fillWidth: true
            Layout.fillHeight: true
            clipContent: true

            ScrollView {
                id: healthScroll
                anchors.fill: parent
                clip: true
                ScrollBar.vertical.policy: ScrollBar.AsNeeded

                GridLayout {
                    width: healthScroll.availableWidth
                    columns: 3
                    columnSpacing: 12
                    rowSpacing: 12

                    Repeater {
                        model: root.controller.deviceHealthModel.count
                        delegate: StatusCard {
                            required property int index
                            property var itemData: root.controller.deviceHealthModel.get(index)
                            theme: root.theme
                            padding: 14
                            title: itemData.title || "Device check"
                            eyebrow: itemData.section || "Device Health"
                            value: itemData.value || "Unavailable"
                            message: itemData.message || ""
                            tone: itemData.tone || "info"
                            Layout.fillWidth: true
                            Layout.preferredHeight: 146
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: root.theme.footerHeight
            SecondaryButton { theme: root.theme; text: "Back"; navigationFocused: root.navigationIndex === 1; onClicked: root.controller.goBack() }
            NavigationHint { theme: root.theme; text: "UP/DOWN Choose  ·  SELECT Confirm  ·  BACK Settings"; Layout.fillWidth: true }
            PrimaryButton { theme: root.theme; text: "Refresh"; navigationFocused: root.navigationIndex === 0; onClicked: root.controller.refreshDeviceHealth() }
        }
    }
}
