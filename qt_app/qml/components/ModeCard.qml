import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Button {
    id: root
    required property QtObject theme
    required property string title
    required property string description
    property string modeId: ""
    property bool selected: false
    property bool navigationFocused: false

    implicitHeight: 148
    hoverEnabled: true
    scale: down ? 0.985 : 1.0

    function iconText() {
        switch (root.modeId) {
        case "read_text": return "T"
        case "summarize_document": return "S"
        case "analyze_image": return "I"
        case "professional_assistant": return "P"
        case "solve_problem": return "?"
        default: return "V"
        }
    }

    Behavior on scale {
        NumberAnimation { duration: root.theme.animationShort }
    }

    contentItem: RowLayout {
        anchors.fill: parent
        anchors.margins: 18
        spacing: 14

        Rectangle {
            Layout.preferredWidth: 48
            Layout.preferredHeight: 48
            radius: 16
            color: root.selected ? Qt.rgba(1, 1, 1, 0.18) : root.theme.primarySoft

            Text {
                anchors.centerIn: parent
                text: root.iconText()
                color: root.selected ? root.theme.surface : root.theme.primaryStrong
                font.family: root.theme.displayFont
                font.pixelSize: 24
                font.weight: root.theme.weightHeavy
                renderType: Text.NativeRendering
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 5

            Text {
                text: root.title
                color: root.selected ? root.theme.surface : root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 24
                font.weight: root.theme.weightHeavy
                Layout.fillWidth: true
                elide: Text.ElideRight
                renderType: Text.NativeRendering
            }

            Text {
                text: root.description
                color: root.selected ? Qt.rgba(1, 1, 1, 0.84) : root.theme.textMuted
                font.family: root.theme.bodyFont
                font.pixelSize: 15
                font.weight: root.theme.weightRegular
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                maximumLineCount: 2
                elide: Text.ElideRight
                renderType: Text.NativeRendering
            }
        }
    }

    background: Item {
        Rectangle {
            anchors.fill: parent
            anchors.leftMargin: 3
            anchors.topMargin: 5
            radius: root.theme.radiusSetupCard + 2
            color: Qt.rgba(
                root.theme.cardShadow.r,
                root.theme.cardShadow.g,
                root.theme.cardShadow.b,
                root.selected ? 0.14 : root.theme.cardShadowOpacity
            )
        }

        Rectangle {
            anchors.fill: parent
            radius: root.theme.radiusSetupCard
            border.width: root.navigationFocused ? 3 : 1
            border.color: root.navigationFocused || root.selected
                          ? root.theme.primaryStrong
                          : root.theme.borderSoft
            color: root.selected ? root.theme.primaryStrong : root.theme.surface

            Behavior on color {
                ColorAnimation { duration: root.theme.animationShort }
            }
        }
    }
}
