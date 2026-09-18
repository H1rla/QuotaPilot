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
        spacing: Tokens.space.lg
        Text { text: "Route"; color: Tokens.color.textPrimary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.title; font.weight: Font.DemiBold }
        Text { text: "What are you working on?"; color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body }
        TextArea {
            id: taskInput
            Layout.fillWidth: true; Layout.preferredHeight: 112
            placeholderText: "Describe the task, scope, and verification constraints."
            color: Tokens.color.textPrimary; placeholderTextColor: Tokens.color.textMuted
            font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body
            wrapMode: TextEdit.Wrap
            background: Rectangle { color: Tokens.color.surface; border.width: taskInput.activeFocus ? 2 : 1; border.color: taskInput.activeFocus ? Tokens.color.accent : Tokens.color.border; radius: Tokens.radius.contained }
        }
        RowLayout {
            Layout.fillWidth: true
            FlatButton { text: advanced.visible ? "Hide advanced" : "Advanced"; onClicked: advanced.visible = !advanced.visible }
            Item { Layout.fillWidth: true }
            FlatButton {
                primary: true; text: routeViewModel.busy ? "Analyzing…" : "Analyze"; enabled: !routeViewModel.busy
                onClicked: advanced.visible
                           ? routeViewModel.analyzeWithOverrides(taskInput.text, taskClass.currentText, complexity.value, ambiguity.value, failure.value, verify.value, context.value, latency.value)
                           : routeViewModel.analyze(taskInput.text)
            }
        }
        GridLayout {
            id: advanced
            visible: false
            Layout.fillWidth: true
            columns: page.width >= 760 ? 2 : 1
            rowSpacing: Tokens.space.sm; columnSpacing: Tokens.space.xl
            property var entries: [
                ["Complexity", complexity], ["Ambiguity", ambiguity], ["Failure cost", failure],
                ["Verifiability", verify], ["Context demand", context], ["Latency sensitivity", latency]
            ]
            Repeater {
                model: advanced.entries
                delegate: RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    Text { text: modelData[0]; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption; Layout.preferredWidth: 112 }
                    Slider { id: profileSlider; Layout.fillWidth: true; from: 0; to: 1; value: 0.5; Component.onCompleted: modelData[1].value = Qt.binding(function() { return value }) }
                    Text { text: profileSlider.value.toFixed(2); color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { text: "Task class"; color: Tokens.color.textMuted; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.caption; Layout.preferredWidth: 112 }
                ComboBox { id: taskClass; Layout.fillWidth: true; model: ["mechanical", "local_implementation", "debugging", "repository_change", "architecture", "research", "review", "unknown"]; currentIndex: 7 }
            }
            QtObject { id: complexity; property real value: 0.5 }
            QtObject { id: ambiguity; property real value: 0.5 }
            QtObject { id: failure; property real value: 0.5 }
            QtObject { id: verify; property real value: 0.5 }
            QtObject { id: context; property real value: 0.5 }
            QtObject { id: latency; property real value: 0.5 }
        }
        InlineMessage { visible: routeViewModel.hasError; Layout.fillWidth: true; title: "Routing unavailable"; detail: routeViewModel.errorMessage }
        ColumnLayout {
            visible: routeViewModel.hasResult
            Layout.fillWidth: true; spacing: Tokens.space.md
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
            SectionHeader { text: "Task profile" }
            GridLayout {
                Layout.fillWidth: true; columns: page.width >= 760 ? 4 : 2
                MetricLine { label: "Complexity"; value: routeViewModel.result.profile.complexity.toFixed(2) }
                MetricLine { label: "Ambiguity"; value: routeViewModel.result.profile.ambiguity.toFixed(2) }
                MetricLine { label: "Failure cost"; value: routeViewModel.result.profile.failureCost.toFixed(2) }
                MetricLine { label: "Verifiability"; value: routeViewModel.result.profile.verifiability.toFixed(2) }
            }
            SectionHeader { text: "Recommended" }
            Text { text: routeViewModel.result.model + " · " + routeViewModel.result.effort; color: Tokens.color.textPrimary; font.family: Tokens.font.mono; font.pixelSize: 22; font.weight: Font.DemiBold }
            Repeater { model: routeViewModel.result.explanation || []; delegate: Text { required property string modelData; text: "✓  " + modelData; color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; wrapMode: Text.Wrap; Layout.fillWidth: true } }
            SectionHeader { text: "Escalation" }
            Text { text: (routeViewModel.result.escalation || []).map(function(item) { return item.model + " · " + item.effort }).join("  →  ") || "None"; color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.body; wrapMode: Text.Wrap; Layout.fillWidth: true }
            RowLayout {
                Item { Layout.fillWidth: true }
                FlatButton { text: "Dry Run"; onClicked: { executeViewModel.prepare(taskInput.text, appController.workingDirectory, true); appController.navigate("Execute") } }
                FlatButton { primary: true; text: "Execute"; onClicked: { executeViewModel.prepare(taskInput.text, appController.workingDirectory, false); appController.navigate("Execute") } }
            }
        }
    }
}
