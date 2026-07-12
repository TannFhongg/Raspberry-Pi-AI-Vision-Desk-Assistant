import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    ColumnLayout {
        anchors.fill: parent
        spacing: 18

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: root.theme.radiusCard
            border.width: root.theme.borderStrong
            border.color: "#d14343"
            color: root.theme.errorCardFill

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 42
                spacing: 18

                Text {
                    text: "Capture Error"
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 28
                    font.weight: root.theme.weightStrong
                }

                Text {
                    text: root.controller.errorTitle
                    color: "#ac2b2b"
                    font.family: root.theme.displayFont
                    font.pixelSize: 66
                    font.weight: root.theme.weightHeavy
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }

                Text {
                    text: root.controller.errorDetail
                    color: "#2f3740"
                    font.family: root.theme.displayFont
                    font.pixelSize: 28
                    font.weight: root.theme.weightStrong
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }

                Item { Layout.fillHeight: true }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            Item { Layout.fillWidth: true }

            ActionButton {
                theme: root.theme
                text: "HOME"
                onClicked: root.controller.clearResult()
            }

            ActionButton {
                theme: root.theme
                primary: true
                text: "CAPTURE AGAIN"
                onClicked: root.controller.retry()
            }
        }
    }
}

