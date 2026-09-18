import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Tokens.js" as Tokens

ApplicationWindow {
    id: window
    visible: !appController.smokeMode
    width: 1100; height: 720
    minimumWidth: 900; minimumHeight: 600
    title: "QuotaPilot"
    color: Tokens.color.window
    palette.window: Tokens.color.window
    palette.windowText: Tokens.color.textPrimary
    palette.base: Tokens.color.surface
    palette.text: Tokens.color.textPrimary
    palette.button: Tokens.color.surface
    palette.buttonText: Tokens.color.textPrimary
    palette.highlight: Tokens.color.accentSubtle
    palette.highlightedText: Tokens.color.accent

    // Keeps ViewModel-provided source strings in the Qt translation catalog.
    function translationCatalog() {
        return [
            qsTranslate("Global", "Connected"),
            qsTranslate("Global", "Unavailable"),
            qsTranslate("Global", "Not authenticated"),
            qsTranslate("Global", "Unknown"),
            qsTranslate("Global", "Using persisted data"),
            qsTranslate("Global", "Using persisted data · STALE"),
            qsTranslate("Global", "Stale"),
            qsTranslate("Global", "Fresh"),
            qsTranslate("Global", "Codex CLI"),
            qsTranslate("Global", "Provider status has not been checked."),
            qsTranslate("Global", "Codex CLI authentication is required. Run `codex login`, then refresh."),
            qsTranslate("Global", "Run `quotapilot doctor` to inspect Codex CLI availability."),
            qsTranslate("Global", "Authentication is managed by Codex CLI."),
            qsTranslate("Global", "Provider status could not be determined."),
            qsTranslate("Global", "Snapshot %1 ago"),
            qsTranslate("Global", "Task difficulty is %1; required model power is %2."),
            qsTranslate("Global", "Risk inputs are failure_cost=%1, ambiguity=%2, and verifiability=%3."),
            qsTranslate("Global", "Quota pressure %1 (%2) contributed a %3 cost penalty."),
            qsTranslate("Global", "%1 meets the capability floor %2 and has the highest policy utility."),
            qsTranslate("Global", "Weaker eligible models scored lower after capability-fit and policy penalties."),
            qsTranslate("Global", "No weaker model was both selectable and above the capability floor."),
            qsTranslate("Global", "Stronger eligible models offered less utility after over-capability, quota, and latency penalties."),
            qsTranslate("Global", "No stronger routable model was available."),
            qsTranslate("Global", "No effort was selected because no explicit ordered effort catalog was available."),
            qsTranslate("Global", "Effort %1 was selected after a quota-saving reduction allowed by low task risk and high verifiability."),
            qsTranslate("Global", "Effort %1 was selected from the model's explicit ordered effort catalog."),
            qsTranslate("Global", "The advisory escalation path contains %1 step(s) and performs no execution."),
            qsTranslate("Global", "Yes"),
            qsTranslate("Global", "No"),
            qsTranslate("Global", "Required"),
            qsTranslate("Global", "Not required"),
            qsTranslate("Global", "UNKNOWN"),
            qsTranslate("Global", "STALE"),
            qsTranslate("Global", "FRESH"),
            qsTranslate("Global", "OVER"),
            qsTranslate("Global", "CRITICAL"),
            qsTranslate("Global", "UNDER"),
            qsTranslate("Global", "VERY_UNDER"),
            qsTranslate("Global", "ON_TRACK"),
            qsTranslate("Global", "Open Overview"),
            qsTranslate("Global", "Open Usage"),
            qsTranslate("Global", "Open Models"),
            qsTranslate("Global", "Open Execution"),
            qsTranslate("Global", "Open History"),
            qsTranslate("Global", "Open Settings"),
            qsTranslate("Global", "Change budget reserve"),
            qsTranslate("Global", "Settings · Budget"),
            qsTranslate("Global", "Change routing policy"),
            qsTranslate("Global", "Settings · Routing"),
            qsTranslate("Global", "Refresh quota"),
            qsTranslate("Global", "Toggle details"),
            qsTranslate("Global", "Platform default"),
            qsTranslate("Global", "Bundled profiles"),
            qsTranslate("Global", "Saved · language applied now; other changes apply on next launch"),
            qsTranslate("Global", "Provider unavailable. Persisted state could not be loaded."),
            qsTranslate("Global", "Usage history is unavailable."),
            qsTranslate("Global", "Snapshot history is unavailable."),
            qsTranslate("Global", "Model profiles are unavailable."),
            qsTranslate("Global", "Enter a task before analysis."),
            qsTranslate("Global", "No persisted snapshot. Refresh quota before routing."),
            qsTranslate("Global", "No route is available. Check model profiles and quota state."),
            qsTranslate("Global", "Analyze a task before creating an execution plan."),
            qsTranslate("Global", "Execution plan could not be created."),
            qsTranslate("Global", "Execution plan is unavailable. Verify the directory and quota freshness."),
            qsTranslate("Global", "Execution failed before a safe result was available."),
            qsTranslate("Global", "Invalid setting value."),
            qsTranslate("Global", "Configuration could not be saved."),
            qsTranslate("Global", "Review value"),
            qsTranslate("Global", "Focus task input"),
            qsTranslate("Global", "Open Models"),
            qsTranslate("Global", "Open Route")
        ]
    }

    Shortcut { sequence: "Ctrl+P"; onActivated: commandPalette.show() }
    Shortcut { sequence: "Ctrl+R"; enabled: !commandPalette.open; onActivated: appController.refresh() }
    Shortcut { sequence: "Ctrl+D"; enabled: !commandPalette.open; onActivated: appController.toggleDetails() }
    Shortcut { sequence: "Ctrl+,"; enabled: !commandPalette.open; onActivated: appController.navigate("Settings") }
    Shortcut { sequence: "Escape"; enabled: !commandPalette.open; onActivated: appController.navigate("Overview") }

    RowLayout {
        anchors.fill: parent; spacing: 0
        Rectangle {
            Layout.preferredWidth: 126; Layout.fillHeight: true
            color: Tokens.color.surface
            border.color: Tokens.color.border
            ColumnLayout {
                anchors.fill: parent; spacing: Tokens.space.xs
                Text {
                    text: "QuotaPilot"; color: Tokens.color.textPrimary
                    font.family: Tokens.font.mono; font.pixelSize: Tokens.type.label; font.weight: Font.DemiBold
                    Layout.leftMargin: Tokens.space.lg; Layout.topMargin: Tokens.space.lg; Layout.bottomMargin: Tokens.space.lg
                }
                Repeater {
                    model: ["Overview", "Usage", "Models", "Route", "Execute", "History", "Settings"]
                    delegate: Rectangle {
                        required property string modelData
                        Layout.fillWidth: true; implicitHeight: 36
                        color: appController.pageName === modelData || navigationHover.hovered
                               ? Tokens.color.accentSubtle : "transparent"
                        Rectangle { visible: appController.pageName === modelData; width: 2; height: parent.height; color: Tokens.color.accent }
                        Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: Tokens.space.lg; text: qsTranslate("Global", modelData); color: appController.pageName === modelData ? Tokens.color.accent : Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body }
                        HoverHandler { id: navigationHover }
                        TapHandler { onTapped: appController.navigate(modelData) }
                    }
                }
                Item { Layout.fillHeight: true }
                Text { text: "Ctrl+P"; color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption; Layout.leftMargin: Tokens.space.lg; Layout.bottomMargin: Tokens.space.lg }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0
            Rectangle {
                Layout.fillWidth: true; implicitHeight: 44; color: Tokens.color.window
                border.color: Tokens.color.border
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: Tokens.space.lg; anchors.rightMargin: Tokens.space.lg
                    Text { text: qsTranslate("Global", appController.pageName); color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    Item { Layout.fillWidth: true }
                    Text { text: appController.detailsVisible ? qsTranslate("Global", "DETAILS ON") : qsTranslate("Global", "DETAILS OFF"); color: appController.detailsVisible ? Tokens.color.accent : Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    Text { text: qsTranslate("Global", "Ctrl+P commands"); color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                }
            }
            StackLayout {
                Layout.fillWidth: true; Layout.fillHeight: true
                currentIndex: appController.pageIndex
                Overview {}
                Usage {}
                Models {}
                Route {}
                Execute {}
                History {}
                Settings {}
            }
        }
    }
    CommandPalette { anchors.fill: parent }
    Component.onCompleted: if (!appController.smokeMode) appController.initialize()
}
