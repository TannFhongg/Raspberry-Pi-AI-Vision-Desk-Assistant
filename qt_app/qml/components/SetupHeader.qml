import QtQuick
import QtQuick.Layouts

Item {
    id: root
    required property QtObject theme
    required property var controller

    implicitHeight: headerRow.implicitHeight

    RowLayout {
        id: headerRow
        anchors.fill: parent
        spacing: 14

        BrandLogo {
            theme: root.theme
            compact: true
            Layout.alignment: Qt.AlignVCenter
            Layout.preferredWidth: 250
            Layout.minimumWidth: 0
            Layout.maximumWidth: 250
        }

        Item {
            Layout.preferredWidth: 10
        }

        Repeater {
            model: root.controller.healthMetricsModel.count

            delegate: SetupMetricChip {
                required property int index
                property var itemData: root.controller.healthMetricsModel.get(index)
                theme: root.theme
                label: itemData.label || ""
                value: itemData.value || "--"
                state: itemData.state || "unavailable"
                message: itemData.message || ""
                Layout.alignment: Qt.AlignVCenter
                Layout.preferredWidth: 110
                Layout.minimumWidth: 110
                Layout.maximumWidth: 110
            }
        }
    }
}
