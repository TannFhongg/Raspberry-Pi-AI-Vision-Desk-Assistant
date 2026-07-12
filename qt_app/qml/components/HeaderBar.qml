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
        model: root.controller.healthMetricsModel.count

        delegate: HealthPill {
            required property int index
            property var itemData: root.controller.healthMetricsModel.get(index)
            theme: root.theme
            label: itemData.label || ""
            value: itemData.value || ""
            state: itemData.state || "unavailable"
            message: itemData.message || ""
            valueSize: itemData.value_size || "normal"
            Layout.alignment: Qt.AlignVCenter
        }
    }

    ClockCard {
        theme: root.theme
        Layout.alignment: Qt.AlignVCenter
    }
}
