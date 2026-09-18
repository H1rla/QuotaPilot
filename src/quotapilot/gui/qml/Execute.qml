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
        Text { text: qsTranslate("Global", "Execute"); color: Tokens.color.textPrimary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.title; font.weight: Font.DemiBold }
        Text { text: qsTranslate("Global", "Routing and execution remain separate. Review the exact plan before approval."); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; wrapMode: Text.Wrap; Layout.fillWidth: true }
        Text { visible: executeViewModel.busy; text: executeViewModel.hasPlan ? qsTranslate("Global", "Executing plan…") : qsTranslate("Global", "Building execution plan…"); color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.body }
        InlineMessage { visible: executeViewModel.hasError; Layout.fillWidth: true; title: qsTranslate("Global", "Execution unavailable"); detail: executeViewModel.errorMessage }
        EmptyState { visible: !executeViewModel.hasPlan && !executeViewModel.busy && !executeViewModel.hasError; title: qsTranslate("Global", "No execution plan"); detail: qsTranslate("Global", "Analyze a task in Route, then choose Dry Run or Execute.") }
        ColumnLayout {
            visible: executeViewModel.hasPlan
            Layout.fillWidth: true; spacing: Tokens.space.md
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
            SectionHeader { text: qsTranslate("Global", "Execution Plan") }
            GridLayout {
                Layout.fillWidth: true; columns: page.width >= 760 ? 2 : 1
                rowSpacing: Tokens.space.sm; columnSpacing: Tokens.space.xl
                MetricLine { label: qsTranslate("Global", "Model"); value: executeViewModel.plan.model }
                MetricLine { label: qsTranslate("Global", "Effort"); value: executeViewModel.plan.effort; translateValue: true }
                MetricLine { label: qsTranslate("Global", "Working directory"); value: executeViewModel.plan.workingDirectory }
                MetricLine { label: qsTranslate("Global", "Quota pressure"); value: executeViewModel.plan.quotaState }
                MetricLine { label: qsTranslate("Global", "Approval"); value: executeViewModel.plan.approval; translateValue: true }
                MetricLine { label: qsTranslate("Global", "Timeout"); value: executeViewModel.plan.timeout }
                MetricLine { label: qsTranslate("Global", "Maximum attempts"); value: String(executeViewModel.plan.maxAttempts) }
                MetricLine { label: qsTranslate("Global", "Mode"); value: executeViewModel.plan.dryRun ? qsTranslate("Global", "DRY RUN") : qsTranslate("Global", "REAL EXECUTION") }
            }
            SectionHeader { text: qsTranslate("Global", "Escalation path") }
            Text { Layout.fillWidth: true; text: (executeViewModel.plan.escalation || []).join("  →  ") || qsTranslate("Global", "None"); color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.body; wrapMode: Text.Wrap }
            Rectangle {
                Layout.fillWidth: true; implicitHeight: warningText.implicitHeight + Tokens.space.lg * 2
                color: Tokens.color.surface; border.color: Tokens.color.over; border.width: 1; radius: Tokens.radius.control
                Text { id: warningText; anchors.fill: parent; anchors.margins: Tokens.space.lg; text: qsTranslate("Global", "Files in the working directory may be modified. Quota and capabilities are revalidated before each real attempt."); color: Tokens.color.textPrimary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; wrapMode: Text.Wrap }
            }
            RowLayout {
                Layout.fillWidth: true
                FlatButton { text: qsTranslate("Global", "Cancel"); onClicked: { executeViewModel.cancel(); appController.navigate("Route") } }
                Item { Layout.fillWidth: true }
                FlatButton {
                    id: confirmButton
                    primary: true
                    focus: executeViewModel.hasPlan && !executeViewModel.plan.dryRun
                    text: executeViewModel.plan.dryRun ? qsTranslate("Global", "Complete Dry Run") : qsTranslate("Global", "Approve & Execute")
                    enabled: !executeViewModel.busy
                    onClicked: executeViewModel.run()
                }
            }
        }
        ColumnLayout {
            visible: executeViewModel.hasResult
            Layout.fillWidth: true; spacing: Tokens.space.sm
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
            SectionHeader { text: qsTranslate("Global", "Result") }
            StateText { statusText: executeViewModel.result.status }
            MetricLine { label: qsTranslate("Global", "Attempts"); value: String(executeViewModel.result.attempts) }
            MetricLine { label: qsTranslate("Global", "Failure class"); value: executeViewModel.result.failureClass; translateValue: true }
            Text { visible: executeViewModel.result.message.length > 0; text: executeViewModel.result.message; color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; wrapMode: Text.Wrap; Layout.fillWidth: true }
        }
    }
}
