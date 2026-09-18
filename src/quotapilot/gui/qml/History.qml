import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Tokens.js" as Tokens
import "components"

Item {
    ColumnLayout {
        anchors.fill: parent; anchors.margins: Tokens.space.xl; spacing: Tokens.space.lg
        Text { text: "History"; color: Tokens.color.textPrimary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.title; font.weight: Font.DemiBold }
        SectionHeader { text: "Usage history" }
        InlineMessage { visible: historyViewModel.hasError; Layout.fillWidth: true; title: "History unavailable"; detail: historyViewModel.errorMessage }
        EmptyState { visible: historyViewModel.empty && !historyViewModel.busy; title: "No persisted snapshots"; detail: "History contains only captured observations; missing intervals remain absent." }
        Rectangle {
            visible: !historyViewModel.empty
            Layout.fillWidth: true; implicitHeight: 32; color: Tokens.color.surface
            RowLayout {
                anchors.fill: parent; anchors.leftMargin: Tokens.space.md; anchors.rightMargin: Tokens.space.md
                Text { Layout.fillWidth: true; text: "Captured"; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                Text { width: 80; text: "Actual"; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                Text { width: 80; text: "Expected"; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                Text { width: 90; text: "State"; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
            }
        }
        ListView {
            visible: !historyViewModel.empty
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            model: historyViewModel.items
            delegate: Rectangle {
                required property int index
                required property var modelData
                width: ListView.view.width; height: 38; color: index % 2 ? Tokens.color.surface : "transparent"
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: Tokens.space.md; anchors.rightMargin: Tokens.space.md
                    Text { Layout.fillWidth: true; text: modelData.capturedText; color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    Text { Layout.preferredWidth: 80; text: modelData.actualText; color: Tokens.color.textPrimary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    Text { Layout.preferredWidth: 80; text: modelData.expectedText; color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    StateText { Layout.preferredWidth: 90; statusText: modelData.statusValue }
                }
            }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
        SectionHeader { text: "Execution history" }
        Text { text: "Not recorded · Phase 6 intentionally persists no execution audit or raw task text."; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; wrapMode: Text.Wrap; Layout.fillWidth: true }
    }
}
