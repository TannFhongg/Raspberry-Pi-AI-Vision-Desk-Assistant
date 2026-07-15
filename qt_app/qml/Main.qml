import QtQuick
import QtQuick.Controls
import QtQuick.Window

import "theme"
import "components"
import "screens"

ApplicationWindow {
    id: window
    width: appController.windowWidth
    height: appController.windowHeight
    visible: true
    color: appTheme.pageBackground
    title: "VisionDesk Qt"
    minimumWidth: 1024
    minimumHeight: 640

    function dispatchNavigation(action) {
        if (screenLoader.item
                && typeof screenLoader.item.handleNavigation === "function"
                && screenLoader.item.handleNavigation(action)) {
            return
        }
        if (action === "back")
            appController.goBack()
    }

    Keys.onPressed: function(event) {
        var action = ""
        if (event.key === Qt.Key_Up)
            action = "up"
        else if (event.key === Qt.Key_Down)
            action = "down"
        else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Space)
            action = "select"
        else if (event.key === Qt.Key_Escape || event.key === Qt.Key_Back)
            action = "back"
        if (action.length > 0) {
            window.dispatchNavigation(action)
            event.accepted = true
        }
    }

    Connections {
        target: appController

        function onNavigationRequested(action) {
            window.dispatchNavigation(action)
        }
    }

    Theme {
        id: appTheme
        bodyFontOverride: appController.bodyFontFamily
        textSize: appController.textSize
        renderingPolicy: appController.textRenderingPolicy
    }

    Component {
        id: homeScreenComponent
        HomeScreen { theme: appTheme; controller: appController }
    }

    Component {
        id: setupScreenComponent
        SetupScreen { theme: appTheme; controller: appController }
    }

    Component {
        id: cameraScreenComponent
        CameraScreen { theme: appTheme; controller: appController }
    }

    Component {
        id: reviewScreenComponent
        ReviewScreen { theme: appTheme; controller: appController }
    }

    Component {
        id: settingsScreenComponent
        SettingsScreen { theme: appTheme; controller: appController }
    }

    Component {
        id: deviceHealthScreenComponent
        DeviceHealthScreen { theme: appTheme; controller: appController }
    }

    Component {
        id: processingScreenComponent
        ProcessingScreen { theme: appTheme; controller: appController }
    }

    Component {
        id: resultScreenComponent
        ResultScreen { theme: appTheme; controller: appController }
    }

    Component {
        id: historyScreenComponent
        HistoryScreen { theme: appTheme; controller: appController }
    }

    Component {
        id: historyDetailScreenComponent
        HistoryDetailScreen { theme: appTheme; controller: appController }
    }

    Component {
        id: errorScreenComponent
        ErrorScreen { theme: appTheme; controller: appController }
    }

    Rectangle {
        anchors.fill: parent
        color: appTheme.pageBackground

        Item {
            id: shell
            anchors.fill: parent
            anchors.margins: appTheme.pageMargin

            AppHeader {
                id: headerBar
                theme: appTheme
                controller: appController
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: appTheme.appHeaderHeight
            }

            Rectangle {
                id: divider
                anchors.top: headerBar.bottom
                anchors.topMargin: appTheme.headerDividerGap
                anchors.left: parent.left
                anchors.right: parent.right
                height: appTheme.dividerStrong
                color: appTheme.primary
            }

            Loader {
                id: screenLoader
                anchors.top: divider.bottom
                anchors.topMargin: appTheme.pageTopGap
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                sourceComponent: {
                    switch (appController.currentScreen) {
                    case "setup":
                        return setupScreenComponent
                    case "camera":
                        return cameraScreenComponent
                    case "review":
                        return reviewScreenComponent
                    case "settings":
                        return settingsScreenComponent
                    case "device_health":
                        return deviceHealthScreenComponent
                    case "processing":
                        return processingScreenComponent
                    case "result":
                        return resultScreenComponent
                    case "history":
                        return historyScreenComponent
                    case "history_detail":
                        return historyDetailScreenComponent
                    case "error":
                        return errorScreenComponent
                    default:
                        return homeScreenComponent
                    }
                }
            }
        }
    }
}
