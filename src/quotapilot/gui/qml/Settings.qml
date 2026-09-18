import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Tokens.js" as Tokens
import "components"

ScrollView {
    id: page
    clip: true
    contentWidth: availableWidth
    property string query: search.text.toLowerCase()
    ColumnLayout {
        width: page.availableWidth - Tokens.space.xl * 2
        x: Tokens.space.xl
        y: Tokens.space.xl
        spacing: Tokens.space.lg
        Text { text: "Settings"; color: Tokens.color.textPrimary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.title; font.weight: Font.DemiBold }
        TextField {
            id: search; Layout.fillWidth: true; placeholderText: "Search settings"
            color: Tokens.color.textPrimary; placeholderTextColor: Tokens.color.textMuted
            font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body
            background: Rectangle { color: Tokens.color.surface; border.width: search.activeFocus ? 2 : 1; border.color: search.activeFocus ? Tokens.color.accent : Tokens.color.border; radius: Tokens.radius.control }
        }
        InlineMessage { visible: settingsViewModel.hasError; Layout.fillWidth: true; title: "Invalid settings"; detail: settingsViewModel.errorMessage }
        Text { visible: settingsViewModel.savedMessage.length > 0; text: settingsViewModel.savedMessage; color: Tokens.color.accent; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }

        ColumnLayout {
            visible: page.query.length === 0 || "general provider database".indexOf(page.query) >= 0
            Layout.fillWidth: true; spacing: Tokens.space.sm
            SectionHeader { text: "General" }
            MetricLine { label: "Provider"; value: settingsViewModel.data.provider }
            MetricLine { label: "Database"; value: settingsViewModel.data.databasePath }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
        }
        ColumnLayout {
            visible: page.query.length === 0 || "budget reserve timezone stale weekday".indexOf(page.query) >= 0
            Layout.fillWidth: true; spacing: Tokens.space.sm
            SectionHeader { text: "Budget" }
            RowLayout { Layout.fillWidth: true; Text { text: "Reserve fraction"; color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: reserve; Layout.fillWidth: true; text: settingsViewModel.data.reserveFraction } }
            RowLayout { Layout.fillWidth: true; Text { text: "Timezone"; color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: timezone; Layout.fillWidth: true; text: settingsViewModel.data.timezone } }
            RowLayout { Layout.fillWidth: true; Text { text: "Stale threshold (s)"; color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: stale; Layout.fillWidth: true; text: settingsViewModel.data.staleAfterSeconds } }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
        }
        ColumnLayout {
            visible: page.query.length === 0 || "routing pressure policy latency".indexOf(page.query) >= 0
            Layout.fillWidth: true; spacing: Tokens.space.sm
            SectionHeader { text: "Routing" }
            RowLayout { Layout.fillWidth: true; Text { text: "Unknown quota pressure"; color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: unknownPressure; Layout.fillWidth: true; text: settingsViewModel.data.unknownQuotaPressure } }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
        }
        ColumnLayout {
            visible: page.query.length === 0 || "execution approval timeout attempts retry".indexOf(page.query) >= 0
            Layout.fillWidth: true; spacing: Tokens.space.sm
            SectionHeader { text: "Execution" }
            RowLayout { Layout.fillWidth: true; Text { text: "Approval mode"; color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } ComboBox { id: mode; Layout.fillWidth: true; model: ["always_confirm", "confirm_on_escalation", "auto_for_low_risk", "never_execute"]; Component.onCompleted: currentIndex = Math.max(0, model.indexOf(settingsViewModel.data.executionMode)) } }
            RowLayout { Layout.fillWidth: true; Text { text: "Timeout (s)"; color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: timeout; Layout.fillWidth: true; text: settingsViewModel.data.timeoutSeconds } }
            RowLayout { Layout.fillWidth: true; Text { text: "Maximum attempts"; color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: attempts; Layout.fillWidth: true; text: settingsViewModel.data.maxAttempts } }
            RowLayout { Layout.fillWidth: true; Text { text: "Same-step retries"; color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: retries; Layout.fillWidth: true; text: settingsViewModel.data.maxSameStepRetries } }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
        }
        ColumnLayout {
            visible: page.query.length === 0 || "models profiles integration appearance dark".indexOf(page.query) >= 0
            Layout.fillWidth: true; spacing: Tokens.space.sm
            SectionHeader { text: "Models & Profiles" }
            MetricLine { label: "Profile location"; value: settingsViewModel.data.profileDirectory }
            SectionHeader { text: "Integration" }
            Text { text: "Codex CLI authentication remains managed by Codex. QuotaPilot stores no credentials."; color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; wrapMode: Text.Wrap; Layout.fillWidth: true }
            SectionHeader { text: "Appearance" }
            MetricLine { label: "Theme"; value: "Dark" }
        }
        RowLayout {
            Layout.fillWidth: true
            Text { text: settingsViewModel.data.configPath; color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption; elide: Text.ElideMiddle; Layout.fillWidth: true }
            FlatButton {
                primary: true; text: settingsViewModel.busy ? "Saving…" : "Save"; enabled: !settingsViewModel.busy
                onClicked: settingsViewModel.save(reserve.text, timezone.text, stale.text, unknownPressure.text, mode.currentText, timeout.text, attempts.text, retries.text)
            }
        }
    }
}
