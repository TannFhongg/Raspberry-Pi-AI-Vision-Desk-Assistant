import QtQuick
import QtQuick.Controls

Item {
    id: root
    required property QtObject theme
    required property var controller

    readonly property real contentScale: Math.min(
        1.0,
        width / Math.max(1, contentRow.implicitWidth)
    )

    implicitHeight: Math.ceil(contentRow.implicitHeight * contentScale)
    height: implicitHeight
    clip: true

    Row {
        id: contentRow
        spacing: 24
        scale: root.contentScale
        transformOrigin: Item.TopLeft
        x: 0
        y: Math.max(0, Math.round((root.height - (height * scale)) / 2))

        BrandLogo {
            theme: root.theme
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
            }
        }

        ClockCard {
            theme: root.theme
        }
    }
}
