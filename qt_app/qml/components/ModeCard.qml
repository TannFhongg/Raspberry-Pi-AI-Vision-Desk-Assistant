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

    implicitHeight: 154
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

            AppText {
                theme: root.theme
                role: "cardTitle"
                decorative: true
                forceQtRendering: true
                anchors.centerIn: parent
                text: root.iconText()
                color: root.selected ? root.theme.surface : root.theme.primaryStrong
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 5

            AppText {
                theme: root.theme
                role: "cardTitle"
                forceQtRendering: true
                text: root.title
                color: root.selected ? root.theme.surface : root.theme.text
                Layout.fillWidth: true
                elide: Text.ElideRight
            }

            AppText {
                theme: root.theme
                role: "secondaryBody"
                forceQtRendering: true
                text: root.description
                color: root.selected ? Qt.rgba(1, 1, 1, 0.84) : root.theme.textMuted
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
                maximumLineCount: 2
                elide: Text.ElideRight
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
