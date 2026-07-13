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

    function toneForStatus(status) {
        var normalized = String(status || "").toLowerCase()
        if (normalized.indexOf("error") >= 0 || normalized.indexOf("fail") >= 0)
            return "error"
        if (normalized.indexOf("queue") >= 0 || normalized.indexOf("retry") >= 0)
            return "warning"
        return "success"
    }

    readonly property bool hasEntries: root.controller.historyEntriesModel.count > 0
    readonly property bool showBanner: root.controller.historyState === "recovered"
                                  || (root.controller.historyState === "error" && hasEntries)
                                  || root.controller.historyState === "loading"

    ColumnLayout {
        anchors.fill: parent
        spacing: 12

        RowLayout {
            Layout.fillWidth: true

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2

                Text {
                    text: "Recent results"
                    color: root.theme.text
                    font.family: root.theme.displayFont
                    font.pixelSize: 34
                    font.weight: root.theme.weightHeavy
                    renderType: Text.NativeRendering
                }

                Text {
                    text: "Review saved VisionDesk answers on this device."
                    color: root.theme.textMuted
                    font.family: root.theme.bodyFont
                    font.pixelSize: 15
                    renderType: Text.NativeRendering
                }
            }

            StatusChip {
                theme: root.theme
                label: "Saved"
                value: String(root.controller.historyEntriesModel.count)
                tone: root.hasEntries ? "success" : "info"
            }
        }

        StatusCard {
            visible: root.showBanner
            theme: root.theme
            padding: 14
            title: "History status"
            eyebrow: root.controller.historyState === "loading" ? "Loading" : "Notice"
            value: root.controller.historyState === "loading" ? "Refreshing saved results" : "Saved results available"
            message: root.controller.historyMessage
            tone: root.controller.historyState === "error" ? "error"
                  : root.controller.historyState === "loading" ? "running"
                  : "info"
            Layout.fillWidth: true
            Layout.preferredHeight: 96
        }

        ContentCard {
            theme: root.theme
            padding: 14
            Layout.fillWidth: true
            Layout.preferredHeight: 430
            Layout.maximumHeight: 430

            Item {
                anchors.fill: parent

                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(parent.width * 0.62, 540)
                    visible: !root.hasEntries
                    spacing: 10

                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.preferredWidth: 54
                        Layout.preferredHeight: 54
                        radius: 18
                        color: root.theme.primarySoft

                        Text {
                            anchors.centerIn: parent
                            text: "H"
                            color: root.theme.primaryStrong
                            font.family: root.theme.displayFont
                            font.pixelSize: 25
                            font.weight: root.theme.weightHeavy
                        }
                    }

                    Text {
                        text: root.controller.historyState === "loading"
                              ? "Loading recent results..."
                              : "No saved results yet"
                        color: root.theme.text
                        font.family: root.theme.displayFont
                        font.pixelSize: 28
                        font.weight: root.theme.weightHeavy
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }

                    Text {
                        text: root.controller.historyState === "loading"
                              ? "VisionDesk is reading the local history store."
                              : root.controller.historyMessage
                        color: root.theme.textMuted
                        font.family: root.theme.bodyFont
                        font.pixelSize: 16
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }

                ListView {
                    id: historyList
                    anchors.fill: parent
                    visible: root.hasEntries
                    clip: true
                    spacing: 10
                    model: root.controller.historyEntriesModel.count
                    boundsBehavior: Flickable.StopAtBounds

                    delegate: ContentCard {
                        required property int index
                        readonly property var itemData: root.controller.historyEntriesModel.get(index)
                        theme: root.theme
                        padding: 16
                        width: historyList.width
                        height: 124
                        fillColor: root.theme.surface

                        RowLayout {
                            anchors.fill: parent
                            spacing: 14

                            Rectangle {
                                Layout.preferredWidth: 44
                                Layout.preferredHeight: 44
                                radius: 14
                                color: root.theme.primarySoft

                                Text {
                                    anchors.centerIn: parent
                                    text: (itemData.mode_label || "R").slice(0, 1).toUpperCase()
                                    color: root.theme.primaryStrong
                                    font.family: root.theme.displayFont
                                    font.pixelSize: 20
                                    font.weight: root.theme.weightHeavy
                                }
                            }

                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 3

                                Text {
                                    text: itemData.mode_label || "Saved Result"
                                    color: root.theme.text
                                    font.family: root.theme.displayFont
                                    font.pixelSize: 22
                                    font.weight: root.theme.weightHeavy
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }

                                Text {
                                    text: itemData.summary || ""
                                    color: root.theme.textMuted
                                    font.family: root.theme.bodyFont
                                    font.pixelSize: 15
                                    Layout.fillWidth: true
                                    maximumLineCount: 2
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideRight
                                }

                                Text {
                                    text: [itemData.created_at || "", root.formatDuration(itemData.duration_seconds || "")].filter(function(value) { return value.length > 0 }).join("  |  ")
                                    color: root.theme.textMuted
                                    font.family: root.theme.bodyFont
                                    font.pixelSize: 13
                                    Layout.fillWidth: true
                                    elide: Text.ElideRight
                                }
                            }

                            StatusChip {
                                theme: root.theme
                                label: root.humanize(itemData.status || "Saved")
                                tone: root.toneForStatus(itemData.status || "")
                            }
                        }

                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.controller.openHistoryItem(itemData.id || itemData.entry_id || "")
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            SecondaryButton {
                theme: root.theme
                text: "BACK"
                onClicked: root.controller.goBack()
            }

            Item { Layout.fillWidth: true }

            SecondaryButton {
                theme: root.theme
                tone: "danger"
                text: "CLEAR HISTORY"
                implicitWidth: 190
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
        padding: 24
        closePolicy: Popup.CloseOnEscape
        background: Rectangle {
            radius: root.theme.radiusSetupCard
            border.width: 1
            border.color: root.theme.borderSoft
            color: root.theme.surface
        }

        contentItem: ColumnLayout {
            spacing: 16

            Text {
                text: "Clear saved history?"
                color: root.theme.text
                font.family: root.theme.displayFont
                font.pixelSize: 28
                font.weight: root.theme.weightHeavy
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            Text {
                text: "This removes stored text results only. Wi-Fi setup and your OpenAI key stay untouched."
                color: root.theme.textMuted
                font.family: root.theme.bodyFont
                font.pixelSize: 16
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Item { Layout.fillWidth: true }

                SecondaryButton {
                    theme: root.theme
                    text: "CANCEL"
                    onClicked: clearHistoryDialog.close()
                }

                PrimaryButton {
                    theme: root.theme
                    tone: "danger"
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
