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
    }
}
