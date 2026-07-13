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
            Layout.fillWidth: true
            Layout.minimumWidth: 10
            Layout.preferredWidth: 10
        }

        Repeater {
            model: root.controller.healthMetricsModel.count

            delegate: SetupMetricChip {
                required property int index
                property var itemData: root.controller.healthMetricsModel.get(index)
                readonly property bool hasLongValue: String(itemData.value || "").length >= 8
                theme: root.theme
                label: itemData.label || ""
                value: itemData.value || "--"
                state: itemData.state || "unavailable"
                message: itemData.message || ""
                Layout.alignment: Qt.AlignVCenter
                Layout.preferredWidth: hasLongValue ? 126 : 110
                Layout.minimumWidth: hasLongValue ? 126 : 110
                Layout.maximumWidth: hasLongValue ? 126 : 110
            }
        }
    }
}
