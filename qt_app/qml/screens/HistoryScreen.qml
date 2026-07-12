import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

import "../components"

Item {
    id: root
    required property QtObject theme
    required property var controller

    function humanize(value) {
        return String(value || "").replace(/_/g, " ").toUpperCase()
    }

    function formatDuration(value) {
        if (value === undefined || value === null || value === "")
            return ""
        var seconds = Number(value)
        if (isNaN(seconds))
            return ""
        if (seconds >= 60)
            return Math.floor(seconds / 60) + "m " + Math.round(seconds % 60) + "s"
        if (seconds >= 10)
            return seconds.toFixed(1) + "s"
        return seconds.toFixed(2) + "s"
    }

    readonly property bool hasEntries: root.controller.historyEntriesModel.count > 0
    readonly property bool showBanner: root.controller.historyState === "recovered"
                                  || (root.controller.historyState === "error" && hasEntries)
                                  || root.controller.historyState === "loading"

    ColumnLayout {
        anchors.fill: parent
        spacing: 18

        Text {
            text: "Recent Results"
            color: root.theme.text
            font.family: root.theme.displayFont
            font.pixelSize: 46
            font.weight: root.theme.weightHeavy
            Layout.fillWidth: true
        }

        Rectangle {
            visible: root.showBanner
            Layout.fillWidth: true
            radius: root.theme.radiusCardSm
            border.width: root.theme.borderStrong
            border.color: root.controller.historyState === "error"
                          ? root.theme.error
                          : root.controller.historyState === "recovered"
                            ? root.theme.primary
                            : root.theme.text
            color: root.controller.historyState === "error"
                   ? root.theme.errorFill
                   : root.controller.historyState === "recovered"
                     ? "#edf5ff"
                     : root.theme.mutedFill
            implicitHeight: bannerText.implicitHeight + 26

            Text {
                id: bannerText
                anchors.fill: parent
                anchors.margins: 13
                text: root.controller.historyMessage
                color: root.theme.text
                font.family: root.theme.bodyFont
                font.pixelSize: 20
                font.weight: root.theme.weightRegular
                wrapMode: Text.WordWrap
                verticalAlignment: Text.AlignVCenter
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            radius: root.theme.radiusCard
            border.width: root.theme.borderStrong
            border.color: root.theme.text
            color: root.theme.surface
            clip: true

            Item {
                anchors.fill: parent
                anchors.margins: 20

                ColumnLayout {
                    anchors.fill: parent
                    spacing: 14

                    Text {
                        visible: !root.hasEntries
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: root.controller.historyState === "loading"
                              ? "Loading recent results..."
                              : root.controller.historyMessage
                        color: root.theme.textSecondary
                        font.family: root.theme.displayFont
                        font.pixelSize: 30
                        font.weight: root.theme.weightStrong
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WordWrap
                    }

                    ScrollView {
                        visible: root.hasEntries
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true

                        Column {
                            width: parent.width
                            spacing: 14

                            Repeater {
                                model: root.controller.historyEntriesModel.count

                                delegate: Rectangle {
                                    required property int index
                                    readonly property var itemData: root.controller.historyEntriesModel.get(index)
                                    width: parent ? parent.width : 0
                                    height: summaryText.implicitHeight + metaRow.implicitHeight + 68
                                    radius: root.theme.radiusCardSm
                                    border.width: root.theme.borderStrong
                                    border.color: root.theme.text
                                    color: root.theme.surface

                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: root.controller.openHistoryItem(itemData.id || "")
                                    }

                                    ColumnLayout {
                                        anchors.fill: parent
                                        anchors.margins: 20
                                        spacing: 10

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: 12

                                            Text {
                                                text: itemData.mode_label || "Saved Result"
                                                color: root.theme.text
                                                font.family: root.theme.displayFont
                                                font.pixelSize: 28
                                                font.weight: root.theme.weightStrong
                                                Layout.fillWidth: true
                                                elide: Text.ElideRight
                                            }

                                            Text {
                                                text: root.humanize(itemData.status || "")
                                                color: root.theme.textSecondary
                                                font.family: root.theme.displayFont
                                                font.pixelSize: 16
                                                font.weight: root.theme.weightStrong
                                            }
                                        }

                                        Text {
                                            text: itemData.created_at || ""
                                            color: root.theme.textSecondary
                                            font.family: root.theme.bodyFont
                                            font.pixelSize: 16
                                            font.weight: root.theme.weightRegular
                                            Layout.fillWidth: true
                                            elide: Text.ElideRight
                                        }

                                        Text {
                                            id: summaryText
                                            text: itemData.summary || ""
                                            color: root.theme.text
                                            font.family: root.theme.bodyFont
                                            font.pixelSize: 20
                                            font.weight: root.theme.weightRegular
                                            Layout.fillWidth: true
                                            wrapMode: Text.WordWrap
                                            maximumLineCount: 3
                                            elide: Text.ElideRight
                                        }

                                        RowLayout {
                                            id: metaRow
                                            Layout.fillWidth: true
                                            spacing: 12

                                            Text {
                                                visible: (itemData.model_used || "").length > 0
                                                text: "Model: " + (itemData.model_used || "")
                                                color: root.theme.textSecondary
                                                font.family: root.theme.bodyFont
                                                font.pixelSize: 15
                                                font.weight: root.theme.weightRegular
                                                elide: Text.ElideRight
                                            }

                                            Text {
                                                visible: root.formatDuration(itemData.duration_seconds || "").length > 0
                                                text: "Time: " + root.formatDuration(itemData.duration_seconds || "")
                                                color: root.theme.textSecondary
                                                font.family: root.theme.bodyFont
                                                font.pixelSize: 15
                                                font.weight: root.theme.weightRegular
                                                elide: Text.ElideRight
                                            }

                                            Text {
                                                visible: (itemData.retry_status || "").length > 0
                                                text: "Retry: " + root.humanize(itemData.retry_status || "")
                                                color: root.theme.textSecondary
                                                font.family: root.theme.bodyFont
                                                font.pixelSize: 15
                                                font.weight: root.theme.weightRegular
                                                elide: Text.ElideRight
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 16

            ActionButton {
                theme: root.theme
                text: "BACK"
                onClicked: root.controller.goBack()
            }

            Item {
                Layout.fillWidth: true
            }

            ActionButton {
                theme: root.theme
                destructive: true
                text: "CLEAR HISTORY"
                implicitWidth: 220
                enabled: root.hasEntries && root.controller.historyState !== "loading"
                onClicked: clearHistoryDialog.open()
            }
        }
    }

    Dialog {
        id: clearHistoryDialog
        anchors.centerIn: parent
        modal: true
        focus: true
        width: 500
        padding: 0
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            radius: root.theme.radiusCard
            border.width: root.theme.borderStrong
            border.color: root.theme.text
            color: root.theme.surface
        }

        contentItem: ColumnLayout {
            spacing: 20

            Text {
                text: "Clear saved history?"
                color: root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 30
                font.weight: root.theme.weightStrong
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Text {
                text: "This removes stored text results only. Wi-Fi setup and your OpenAI key stay untouched."
                color: root.theme.textSecondary
                font.family: root.theme.bodyFont
                font.pixelSize: 19
                font.weight: root.theme.weightRegular
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item {
                    Layout.fillWidth: true
                }

                ActionButton {
                    theme: root.theme
                    text: "CANCEL"
                    onClicked: clearHistoryDialog.close()
                }

                ActionButton {
                    theme: root.theme
                    destructive: true
                    text: "CLEAR"
                    onClicked: {
                        clearHistoryDialog.close()
                        root.controller.clearHistory()
                    }
                }
            }
        }
    }
}
