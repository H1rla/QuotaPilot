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
        Text { text: "Models"; color: Tokens.color.textPrimary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.title; font.weight: Font.DemiBold }
        InlineMessage { visible: modelsViewModel.hasError; Layout.fillWidth: true; title: "Models unavailable"; detail: modelsViewModel.errorMessage }
        EmptyState { visible: modelsViewModel.empty && !modelsViewModel.busy; title: "No model data"; detail: "Capture provider state, then verify capability profiles." }
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
                        Text { Layout.fillWidth: true; text: "Model"; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                        Text { width: 64; text: "Route"; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                        Text { width: 55; text: "Power"; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                        Text { width: 55; text: "Cost"; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                        Text { width: 55; text: "Latency"; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                        Text { width: 72; text: "Fresh"; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
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
                        color: ListView.isCurrentItem ? Tokens.color.accentSubtle : "transparent"
                        border.width: activeFocus ? 1 : 0; border.color: Tokens.color.accent
                        RowLayout {
                            anchors.fill: parent; anchors.leftMargin: Tokens.space.md; anchors.rightMargin: Tokens.space.md
                            Text { Layout.fillWidth: true; text: modelId; elide: Text.ElideRight; color: Tokens.color.textPrimary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.body }
                            Text { width: 64; text: routableText; color: routableText === "Yes" ? Tokens.color.textPrimary : Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                            Text { width: 55; text: power; color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                            Text { width: 55; text: cost; color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                            Text { width: 55; text: latency; color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                            StateText { width: 72; statusText: freshness }
                        }
                        TapHandler { onTapped: { list.currentIndex = index; modelsViewModel.select(index) } }
                    }
                }
            }
            Rectangle {
                visible: page.width >= 820 || appController.detailsVisible
                Layout.preferredWidth: 285; Layout.fillHeight: true
                color: Tokens.color.surface
                border.color: Tokens.color.border
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: Tokens.space.lg; spacing: Tokens.space.sm
                    SectionHeader { text: modelsViewModel.selected.modelId || "Model detail" }
                    MetricLine { label: "Exact ID"; value: modelsViewModel.selected.modelId || "Unknown" }
                    MetricLine { label: "Source"; value: modelsViewModel.selected.source || "Unknown" }
                    MetricLine { label: "Confidence"; value: modelsViewModel.selected.confidence || "Unknown" }
                    MetricLine { label: "Verified"; value: modelsViewModel.selected.verified || "Unknown" }
                    MetricLine { label: "Efforts"; value: modelsViewModel.selected.effort || "Unknown" }
                    StateText { statusText: modelsViewModel.selected.freshness || "UNKNOWN" }
                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
                    Text { text: "Evidence / provenance"; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption }
                    Text { Layout.fillWidth: true; text: (modelsViewModel.selected.evidence || []).join("\n"); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption; wrapMode: Text.Wrap }
                    Item { Layout.fillHeight: true }
                }
            }
        }
    }
}
