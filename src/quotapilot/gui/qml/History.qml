import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Tokens.js" as Tokens
import "components"

Item {
    ColumnLayout {
        anchors.fill: parent; anchors.margins: Tokens.space.xl; spacing: Tokens.space.lg
        Text { text: qsTranslate("Global", "History"); color: Tokens.color.textPrimary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.title; font.weight: Font.DemiBold }
        SectionHeader { text: qsTranslate("Global", "Usage history") }
        InlineMessage { visible: historyViewModel.hasError; Layout.fillWidth: true; title: qsTranslate("Global", "History unavailable"); detail: historyViewModel.errorMessage }
        EmptyState { visible: historyViewModel.empty && !historyViewModel.busy; title: qsTranslate("Global", "No persisted snapshots"); detail: qsTranslate("Global", "History contains only captured observations; missing intervals remain absent.") }
        Rectangle {
            visible: !historyViewModel.empty
            Layout.fillWidth: true; implicitHeight: 32; color: Tokens.color.surface
            RowLayout {
                anchors.fill: parent; anchors.leftMargin: Tokens.space.md; anchors.rightMargin: Tokens.space.md
                Text { Layout.fillWidth: true; text: qsTranslate("Global", "Captured"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                Text { width: 80; text: qsTranslate("Global", "Actual"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                Text { width: 80; text: qsTranslate("Global", "Expected"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                Text { width: 90; text: qsTranslate("Global", "State"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
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
                    Text { Layout.preferredWidth: 80; text: qsTranslate("Global", modelData.actualText); color: Tokens.color.textPrimary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    Text { Layout.preferredWidth: 80; text: qsTranslate("Global", modelData.expectedText); color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    StateText { Layout.preferredWidth: 90; statusText: modelData.statusValue }
                }
            }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
        SectionHeader { text: qsTranslate("Global", "Execution history") }
        Text { text: qsTranslate("Global", "Not recorded · Phase 6 intentionally persists no execution audit or raw task text."); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; wrapMode: Text.Wrap; Layout.fillWidth: true }
    }
}
