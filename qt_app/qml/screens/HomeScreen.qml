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
        spacing: 24

        Text {
            text: "What would you like to do?"
            color: root.theme.text
            font.family: root.theme.displayFont
            font.pixelSize: 54
            font.weight: root.theme.weightHeavy
            Layout.fillWidth: true
        }

        GridLayout {
            columns: 6
            columnSpacing: 26
            rowSpacing: 28
            Layout.fillWidth: true
            Layout.fillHeight: true

            Repeater {
                model: root.controller.modeCardsModel

                delegate: ModeCard {
                    theme: root.theme
                    title: model.name
                    description: model.description
                    selected: model.id === root.controller.selectedMode
                    Layout.columnSpan: index >= 3 ? 3 : 2
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    onClicked: root.controller.selectMode(model.id)
                }
            }
        }
    }
}

