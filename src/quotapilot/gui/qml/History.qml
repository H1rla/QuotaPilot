import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Tokens.js" as Tokens
import "components"

Item {
    id: page

    readonly property int actualColumnWidth: 80
    readonly property int expectedColumnWidth: 80
    readonly property int stateColumnWidth: 90

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
                spacing: Tokens.space.sm
                Text { Layout.fillWidth: true; text: qsTranslate("Global", "Captured"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                Text { objectName: "historyHeaderActual"; Layout.minimumWidth: page.actualColumnWidth; Layout.preferredWidth: page.actualColumnWidth; Layout.maximumWidth: page.actualColumnWidth; text: qsTranslate("Global", "Actual"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                Text { objectName: "historyHeaderExpected"; Layout.minimumWidth: page.expectedColumnWidth; Layout.preferredWidth: page.expectedColumnWidth; Layout.maximumWidth: page.expectedColumnWidth; text: qsTranslate("Global", "Expected"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                Text { objectName: "historyHeaderState"; Layout.minimumWidth: page.stateColumnWidth; Layout.preferredWidth: page.stateColumnWidth; Layout.maximumWidth: page.stateColumnWidth; text: qsTranslate("Global", "State"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
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
                    spacing: Tokens.space.sm
                    Text { Layout.fillWidth: true; text: modelData.capturedText; color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    Text { objectName: "historyRowActual"; Layout.minimumWidth: page.actualColumnWidth; Layout.preferredWidth: page.actualColumnWidth; Layout.maximumWidth: page.actualColumnWidth; text: qsTranslate("Global", modelData.actualText); color: Tokens.color.textPrimary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    Text { objectName: "historyRowExpected"; Layout.minimumWidth: page.expectedColumnWidth; Layout.preferredWidth: page.expectedColumnWidth; Layout.maximumWidth: page.expectedColumnWidth; text: qsTranslate("Global", modelData.expectedText); color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    StateText { objectName: "historyRowState"; Layout.minimumWidth: page.stateColumnWidth; Layout.preferredWidth: page.stateColumnWidth; Layout.maximumWidth: page.stateColumnWidth; statusText: modelData.statusValue }
                }
            }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
        SectionHeader { text: qsTranslate("Global", "Execution history") }
        Text { text: qsTranslate("Global", "Not recorded · Phase 6 intentionally persists no execution audit or raw task text."); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; wrapMode: Text.Wrap; Layout.fillWidth: true }
    }
}
