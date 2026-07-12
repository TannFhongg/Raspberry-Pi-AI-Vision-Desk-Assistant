import QtQuick
import QtQuick.Layouts
import QtQuick.Controls

RowLayout {
    id: root
    required property QtObject theme
    required property var controller
    spacing: 24

    BrandLogo {
        theme: root.theme
        Layout.alignment: Qt.AlignVCenter
    }

    Item {
        Layout.fillWidth: true
    }

    Repeater {
        model: root.controller.healthMetricsModel

        delegate: HealthPill {
            theme: root.theme
            label: model.label
            value: model.value
            state: model.state
            message: model.message
            valueSize: model.value_size
            Layout.alignment: Qt.AlignVCenter
        }
    }

    ClockCard {
        theme: root.theme
        Layout.alignment: Qt.AlignVCenter
    }
}

