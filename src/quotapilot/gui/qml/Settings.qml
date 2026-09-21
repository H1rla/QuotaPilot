import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Tokens.js" as Tokens
import "components"

PageScrollView {
    id: page
    contentSpacing: Tokens.space.lg
    property string query: search.text.toLowerCase()
        Text { text: qsTranslate("Global", "Settings"); color: Tokens.color.textPrimary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.title; font.weight: Font.DemiBold }
        TextField {
            id: search; Layout.fillWidth: true; placeholderText: qsTranslate("Global", "Search settings")
            color: Tokens.color.textPrimary; placeholderTextColor: Tokens.color.textMuted
            font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body
            background: Rectangle { color: Tokens.color.surface; border.width: search.activeFocus ? 2 : 1; border.color: search.activeFocus ? Tokens.color.accent : Tokens.color.border; radius: Tokens.radius.control }
        }
        InlineMessage { visible: settingsViewModel.hasError; Layout.fillWidth: true; title: qsTranslate("Global", "Invalid settings"); detail: settingsViewModel.errorMessage }
        Text { visible: settingsViewModel.savedMessage.length > 0; text: qsTranslate("Global", settingsViewModel.savedMessage); color: Tokens.color.accent; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }

        ColumnLayout {
            visible: appController.detailsVisible
                     || (page.query.length > 0
                         && "general provider database".indexOf(page.query) >= 0)
            Layout.fillWidth: true; spacing: Tokens.space.sm
            SectionHeader { text: qsTranslate("Global", "General") }
            MetricLine { label: qsTranslate("Global", "Provider"); value: settingsViewModel.data.provider }
            MetricLine { label: qsTranslate("Global", "Database"); value: settingsViewModel.data.databasePath }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
        }
        ColumnLayout {
            visible: page.query.length === 0 || "budget reserve timezone stale weekday".indexOf(page.query) >= 0
            Layout.fillWidth: true; spacing: Tokens.space.sm
            SectionHeader { text: qsTranslate("Global", "Budget") }
            RowLayout { Layout.fillWidth: true; Text { text: qsTranslate("Global", "Reserve fraction"); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: reserve; Layout.fillWidth: true; text: settingsViewModel.data.reserveFraction } }
            RowLayout { Layout.fillWidth: true; Text { text: qsTranslate("Global", "Timezone"); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: timezone; Layout.fillWidth: true; text: settingsViewModel.data.timezone } }
            RowLayout { Layout.fillWidth: true; Text { text: qsTranslate("Global", "Stale threshold (s)"); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: stale; Layout.fillWidth: true; text: settingsViewModel.data.staleAfterSeconds } }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
        }
        ColumnLayout {
            visible: page.query.length === 0 || "routing pressure policy latency".indexOf(page.query) >= 0
            Layout.fillWidth: true; spacing: Tokens.space.sm
            SectionHeader { text: qsTranslate("Global", "Routing") }
            RowLayout { Layout.fillWidth: true; Text { text: qsTranslate("Global", "Unknown quota pressure"); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: unknownPressure; Layout.fillWidth: true; text: settingsViewModel.data.unknownQuotaPressure } }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
        }
        ColumnLayout {
            visible: page.query.length === 0 || "execution approval timeout attempts retry".indexOf(page.query) >= 0
            Layout.fillWidth: true; spacing: Tokens.space.sm
            SectionHeader { text: qsTranslate("Global", "Execution") }
            RowLayout { Layout.fillWidth: true; Text { text: qsTranslate("Global", "Approval mode"); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } ComboBox { id: mode; Layout.fillWidth: true; model: ["always_confirm", "confirm_on_escalation", "auto_for_low_risk", "never_execute"]; Component.onCompleted: currentIndex = Math.max(0, model.indexOf(settingsViewModel.data.executionMode)) } }
            RowLayout { Layout.fillWidth: true; Text { text: qsTranslate("Global", "Timeout (s)"); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: timeout; Layout.fillWidth: true; text: settingsViewModel.data.timeoutSeconds } }
            RowLayout { Layout.fillWidth: true; Text { text: qsTranslate("Global", "Maximum attempts"); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: attempts; Layout.fillWidth: true; text: settingsViewModel.data.maxAttempts } }
            RowLayout { Layout.fillWidth: true; Text { text: qsTranslate("Global", "Same-step retries"); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 } TextField { id: retries; Layout.fillWidth: true; text: settingsViewModel.data.maxSameStepRetries } }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
        }
        ColumnLayout {
            visible: appController.detailsVisible
                     || (page.query.length > 0
                         && "models profiles profile location".indexOf(page.query) >= 0)
            Layout.fillWidth: true; spacing: Tokens.space.sm
            SectionHeader { text: qsTranslate("Global", "Models & Profiles") }
            MetricLine { label: qsTranslate("Global", "Profile location"); value: settingsViewModel.data.profileDirectory }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
        }
        ColumnLayout {
            visible: appController.detailsVisible
                     || (page.query.length > 0
                         && "integration codex authentication credentials".indexOf(page.query) >= 0)
            Layout.fillWidth: true; spacing: Tokens.space.sm
            SectionHeader { text: qsTranslate("Global", "Integration") }
            Text { text: qsTranslate("Global", "Codex CLI authentication remains managed by Codex. QuotaPilot stores no credentials."); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; wrapMode: Text.Wrap; Layout.fillWidth: true }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
        }
        ColumnLayout {
            visible: page.query.length === 0
                     || "appearance dark theme language".indexOf(page.query) >= 0
            Layout.fillWidth: true; spacing: Tokens.space.sm
            SectionHeader { text: qsTranslate("Global", "Appearance") }
            MetricLine { label: qsTranslate("Global", "Theme"); value: qsTranslate("Global", "Dark") }
            RowLayout {
                Layout.fillWidth: true
                Text { text: qsTranslate("Global", "Language"); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.preferredWidth: 180 }
                ComboBox {
                    id: language
                    Layout.fillWidth: true
                    model: [qsTranslate("Global", "System"), qsTranslate("Global", "English"), qsTranslate("Global", "日本語")]
                    Component.onCompleted: currentIndex = Math.max(0, ["system", "en", "ja"].indexOf(settingsViewModel.data.language))
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Text { text: settingsViewModel.data.configPath; color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption; elide: Text.ElideMiddle; Layout.fillWidth: true }
            FlatButton {
                primary: true; text: settingsViewModel.busy ? qsTranslate("Global", "Saving…") : qsTranslate("Global", "Save"); enabled: !settingsViewModel.busy
                onClicked: settingsViewModel.save(reserve.text, timezone.text, stale.text, unknownPressure.text, mode.currentText, timeout.text, attempts.text, retries.text, ["system", "en", "ja"][language.currentIndex])
            }
        }
}
