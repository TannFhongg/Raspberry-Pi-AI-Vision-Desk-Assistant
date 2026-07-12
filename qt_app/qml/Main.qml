import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "theme"
import "components"
import "screens"

ApplicationWindow {
    id: window
    width: appController.windowWidth
    height: appController.windowHeight
    visible: true
    color: theme.pageBackground
    title: "VisionDesk Qt"

    Theme {
        id: theme
    }

    Component {
        id: homeScreenComponent
        HomeScreen { theme: theme; controller: appController }
    }

    Component {
        id: setupScreenComponent
        SetupScreen { theme: theme; controller: appController }
    }

    Component {
        id: cameraScreenComponent
        CameraScreen { theme: theme; controller: appController }
    }

    Component {
        id: processingScreenComponent
        ProcessingScreen { theme: theme; controller: appController }
    }

    Component {
        id: resultScreenComponent
        ResultScreen { theme: theme; controller: appController }
    }

    Component {
        id: errorScreenComponent
        ErrorScreen { theme: theme; controller: appController }
    }

    Rectangle {
        anchors.fill: parent
        color: theme.pageBackground

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 0

            HeaderBar {
                theme: theme
                controller: appController
                Layout.fillWidth: true
            }

            Rectangle {
                Layout.fillWidth: true
                height: theme.dividerStrong
                color: theme.primary
                Layout.topMargin: 16
                Layout.bottomMargin: 18
            }

            Loader {
                id: screenLoader
                Layout.fillWidth: true
                Layout.fillHeight: true
                sourceComponent: {
                    switch (appController.currentScreen) {
                    case "setup":
                        return setupScreenComponent
                    case "camera":
                        return cameraScreenComponent
                    case "processing":
                        return processingScreenComponent
                    case "result":
                        return resultScreenComponent
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
