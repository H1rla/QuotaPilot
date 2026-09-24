import QtQuick
import QtQuick.Layouts
import "Tokens.js" as Tokens
import "components"

PageScrollView {
    id: page
    contentSpacing: Tokens.space.xl
        Text { text: qsTranslate("Global", "Usage"); color: Tokens.color.textPrimary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.title; font.weight: Font.DemiBold }
        Text { text: qsTranslate("Global", "Projected end of each day from observed usage pace"); color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
        InlineMessage { visible: usageViewModel.hasError; Layout.fillWidth: true; title: qsTranslate("Global", "Usage unavailable"); detail: usageViewModel.errorMessage }
        EmptyState { visible: usageViewModel.empty && !usageViewModel.busy; title: qsTranslate("Global", "No usage history"); detail: qsTranslate("Global", "Capture quota state to begin a local history.") }
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
        ForecastStrip { Layout.fillWidth: true; points: usageViewModel.points; unavailableReason: usageViewModel.forecastReason; stale: usageViewModel.forecastStale; detailsVisible: appController.detailsVisible }
}
