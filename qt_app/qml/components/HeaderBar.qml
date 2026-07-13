import QtQuick
import QtQuick.Controls

Item {
    id: root
    required property QtObject theme
    required property var controller

    readonly property bool setupMode: root.controller.currentScreen === "setup"
    readonly property real activeImplicitWidth: root.setupMode
                                            ? width
                                            : contentRow.implicitWidth
    readonly property real activeImplicitHeight: root.setupMode
                                             ? setupRow.implicitHeight
                                             : contentRow.implicitHeight
    readonly property real contentScale: root.setupMode ? 1.0 : Math.min(
        1.0,
        width / Math.max(1, root.activeImplicitWidth)
    )

    implicitHeight: Math.ceil(root.activeImplicitHeight * contentScale)
    height: implicitHeight
    clip: true

    Row {
        id: contentRow
        visible: !root.setupMode
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

    SetupHeader {
        id: setupRow
        visible: root.setupMode
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        theme: root.theme
        controller: root.controller
    }
}
