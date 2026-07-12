import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    function cardWidthFor(index, availableWidth) {
        if (index >= 3) {
            return Math.max(280, (availableWidth - 26) / 2)
        }
        return Math.max(240, (availableWidth - (26 * 2)) / 3)
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
                text: "DELETE ALL DATA"
                implicitWidth: 248
                onClicked: deleteAllDataDialog.open()
            }
        }
    }

    Dialog {
        id: deleteAllDataDialog
        anchors.centerIn: parent
        modal: true
        focus: true
        width: 520
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
                text: "Delete all local data?"
                color: root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 32
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Text {
                text: "This removes saved history, queued retry items, and temporary private media. Device config and the OpenAI key stay in place."
                color: root.theme.textSecondary
                font.family: root.theme.bodyFont
                font.pixelSize: 20
                font.weight: root.theme.weightRegular
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
                    onClicked: deleteAllDataDialog.close()
                }

                ActionButton {
                    theme: root.theme
                    destructive: true
                    text: "DELETE"
                    onClicked: {
                        deleteAllDataDialog.close()
                        root.controller.deleteAllData()
                    }
                }
            }
        }
    }
}
