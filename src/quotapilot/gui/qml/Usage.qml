import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Tokens.js" as Tokens
import "components"

ScrollView {
    id: page
    clip: true
    contentWidth: availableWidth
    ColumnLayout {
        width: page.availableWidth - Tokens.space.xl * 2
        x: Tokens.space.xl
        y: Tokens.space.xl
        spacing: Tokens.space.xl
        Text { text: qsTranslate("Global", "Usage"); color: Tokens.color.textPrimary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.title; font.weight: Font.DemiBold }
        Text { text: qsTranslate("Global", "Persisted snapshots only · missing points are not inferred"); color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
        InlineMessage { visible: usageViewModel.hasError; Layout.fillWidth: true; title: qsTranslate("Global", "Usage unavailable"); detail: usageViewModel.errorMessage }
        EmptyState { visible: usageViewModel.empty && !usageViewModel.busy; title: qsTranslate("Global", "No usage history"); detail: qsTranslate("Global", "Capture quota state to begin a local history.") }
        UsageChart { visible: !usageViewModel.empty; Layout.fillWidth: true; Layout.preferredHeight: 260; points: usageViewModel.points }
        Repeater {
            model: usageViewModel.summary
            delegate: ColumnLayout {
                required property var modelData
                Layout.fillWidth: true
                spacing: Tokens.space.sm
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
                SectionHeader { text: qsTranslate("Global", modelData.name) }
                RowLayout {
                    Layout.fillWidth: true
                    MetricLine { Layout.fillWidth: true; label: qsTranslate("Global", "Actual"); value: modelData.actualText; translateValue: true }
                    MetricLine { Layout.fillWidth: true; label: qsTranslate("Global", "Expected"); value: modelData.expectedText; translateValue: true }
                    MetricLine { Layout.fillWidth: true; label: qsTranslate("Global", "Delta"); value: modelData.deltaText; translateValue: true }
                    StateText { statusText: modelData.state }
                }
                MetricLine { label: qsTranslate("Global", "Reset"); value: modelData.reset; translateValue: true }
            }
        }
    }
}
