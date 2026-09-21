import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Tokens.js" as Tokens
import "components"

Item {
    id: page
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Tokens.space.xl
        spacing: Tokens.space.lg
        Text { text: qsTranslate("Global", "Models"); color: Tokens.color.textPrimary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.title; font.weight: Font.DemiBold }
        InlineMessage { visible: modelsViewModel.hasError; Layout.fillWidth: true; title: qsTranslate("Global", "Models unavailable"); detail: modelsViewModel.errorMessage }
        EmptyState { visible: modelsViewModel.empty && !modelsViewModel.busy; title: qsTranslate("Global", "No model data"); detail: qsTranslate("Global", "Capture provider state, then verify capability profiles.") }
        RowLayout {
            visible: !modelsViewModel.empty
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Tokens.space.xl
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 34; color: Tokens.color.surface
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: Tokens.space.md; anchors.rightMargin: Tokens.space.md
                        Text { Layout.fillWidth: true; text: qsTranslate("Global", "Model"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                        Text { width: 64; text: qsTranslate("Global", "Route"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                        Text { width: 55; text: qsTranslate("Global", "Power"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                        Text { width: 55; text: qsTranslate("Global", "Cost"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                        Text { width: 55; text: qsTranslate("Global", "Latency"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                        Text { width: 72; text: qsTranslate("Global", "Fresh"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                    }
                }
                ListView {
                    id: list
                    Layout.fillWidth: true; Layout.fillHeight: true
                    model: modelsViewModel.rows
                    clip: true
                    currentIndex: 0
                    delegate: Rectangle {
                        required property int index
                        required property string modelId
                        required property string routableText
                        required property string power
                        required property string cost
                        required property string latency
                        required property string freshness
                        width: ListView.view.width; height: 40
                        color: ListView.isCurrentItem || modelHover.hovered
                               ? Tokens.color.accentSubtle : "transparent"
                        border.width: activeFocus ? 1 : 0; border.color: Tokens.color.accent
                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: Tokens.space.md; anchors.rightMargin: Tokens.space.md
                            Text { Layout.fillWidth: true; text: modelId; elide: Text.ElideRight; color: Tokens.color.textPrimary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.body }
                            Text { width: 64; text: qsTranslate("Global", routableText); color: routableText === "Yes" ? Tokens.color.textPrimary : Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                            Text { width: 55; text: power; color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                            Text { width: 55; text: cost; color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                            Text { width: 55; text: latency; color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                            StateText { width: 72; statusText: freshness }
                        }
                        HoverHandler { id: modelHover }
                        TapHandler { onTapped: { list.currentIndex = index; modelsViewModel.select(index) } }
                    }
                }
            }
            Rectangle {
                visible: appController.detailsVisible
                Layout.preferredWidth: 285; Layout.fillHeight: true
                color: Tokens.color.surface
                border.color: Tokens.color.border
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: Tokens.space.lg; spacing: Tokens.space.sm
                    SectionHeader { text: modelsViewModel.selected.modelId || qsTranslate("Global", "Model detail") }
                    MetricLine { label: qsTranslate("Global", "Exact ID"); value: modelsViewModel.selected.modelId || qsTranslate("Global", "Unknown") }
                    MetricLine { label: qsTranslate("Global", "Source"); value: modelsViewModel.selected.source || qsTranslate("Global", "Unknown"); translateValue: true }
                    MetricLine { label: qsTranslate("Global", "Confidence"); value: modelsViewModel.selected.confidence || qsTranslate("Global", "Unknown"); translateValue: true }
                    MetricLine { label: qsTranslate("Global", "Verified"); value: modelsViewModel.selected.verified || qsTranslate("Global", "Unknown"); translateValue: true }
                    MetricLine { label: qsTranslate("Global", "Efforts"); value: modelsViewModel.selected.effort || qsTranslate("Global", "Unknown"); translateValue: true }
                    StateText { statusText: modelsViewModel.selected.freshness || "UNKNOWN" }
                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
                    Text { text: qsTranslate("Global", "Evidence / provenance"); color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                    Text { Layout.fillWidth: true; text: (modelsViewModel.selected.evidence || []).join("\n"); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption; wrapMode: Text.Wrap }
                    Item { Layout.fillHeight: true }
                }
            }
        }
    }
}
