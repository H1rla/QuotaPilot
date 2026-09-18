import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "I18n.js" as I18n
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

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Tokens.space.xs
                Text {
                    text: qsTranslate("Global", "Overview")
                    color: Tokens.color.textPrimary
                    font.family: Tokens.font.ui
                    font.pixelSize: Tokens.type.title
                    font.weight: Font.DemiBold
                }
                Text {
                    text: qsTranslate("Global", overviewViewModel.data.provider) + "  ·  "
                          + qsTranslate("Global", "Snapshot %1 ago").arg(
                                qsTranslate("Global", overviewViewModel.data.freshnessAge))
                          + (overviewViewModel.data.stale ? " · " + qsTranslate("Global", "STALE") : "")
                    color: overviewViewModel.data.stale ? Tokens.color.stale : Tokens.color.textMuted
                    font.family: Tokens.font.mono
                    font.pixelSize: Tokens.type.caption
                }
            }
            FlatButton {
                text: overviewViewModel.busy ? qsTranslate("Global", "Refreshing…") : qsTranslate("Global", "Refresh")
                enabled: !overviewViewModel.busy
                onClicked: overviewViewModel.refresh()
            }
        }

        InlineMessage {
            visible: overviewViewModel.hasError
            Layout.fillWidth: true
            title: qsTranslate("Global", "Provider unavailable")
            detail: overviewViewModel.errorMessage
            action: Component { FlatButton { text: qsTranslate("Global", "Retry"); onClicked: overviewViewModel.refresh() } }
        }

        EmptyState {
            visible: !overviewViewModel.data.available && !overviewViewModel.busy
            title: qsTranslate("Global", "No persisted snapshot")
            detail: qsTranslate("Global", "Refresh quota to capture current provider state. Unknown values remain unknown.")
        }

        ColumnLayout {
            visible: overviewViewModel.data.available
            Layout.fillWidth: true
            spacing: Tokens.space.md
            RowLayout {
                Layout.fillWidth: true
                spacing: Tokens.space.xl
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0
                    Text {
                        text: qsTranslate("Global", overviewViewModel.data.remaining)
                        color: Tokens.color.textPrimary
                        font.family: Tokens.font.mono
                        font.pixelSize: Tokens.type.metric
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: qsTranslate("Global", "remaining quota")
                        color: Tokens.color.textSecondary
                        font.family: Tokens.font.ui
                        font.pixelSize: Tokens.type.body
                    }
                }
                ColumnLayout {
                    Layout.preferredWidth: 150
                    MetricLine { label: qsTranslate("Global", "Reset"); value: overviewViewModel.data.reset; primary: true; translateValue: true }
                    MetricLine { label: qsTranslate("Global", "Today"); value: overviewViewModel.data.todayBudget; primary: true; translateValue: true }
                }
                ColumnLayout {
                    Layout.preferredWidth: 150
                    Text {
                        text: qsTranslate("Global", "Budget state")
                        color: Tokens.color.textMuted
                        font.family: Tokens.font.ui
                        font.pixelSize: Tokens.type.caption
                    }
                    StateText { statusText: overviewViewModel.data.state; font.pixelSize: Tokens.type.section }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 6
                color: Tokens.color.surfaceRaised
                radius: 3
                Rectangle {
                    height: parent.height
                    width: overviewViewModel.data.remainingValue === null
                           || overviewViewModel.data.remainingValue === undefined
                           ? 0 : parent.width * overviewViewModel.data.remainingValue
                    color: Tokens.color.accent
                    radius: 3
                    Behavior on width { NumberAnimation { duration: Tokens.motion.normal } }
                }
            }

            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }

            RowLayout {
                Layout.fillWidth: true
                visible: page.width >= 850 || appController.detailsVisible
                spacing: Tokens.space.xl
                MetricLine { Layout.fillWidth: true; label: qsTranslate("Global", "Pressure"); value: overviewViewModel.data.pressure; translateValue: true }
                MetricLine { Layout.fillWidth: true; label: qsTranslate("Global", "Routable"); value: overviewViewModel.data.routableModels; translateValue: true }
                MetricLine { Layout.fillWidth: true; label: qsTranslate("Global", "Profiles"); value: overviewViewModel.data.profileFreshness; translateValue: true }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Tokens.space.sm
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
            RowLayout {
                Layout.fillWidth: true
                SectionHeader { text: qsTranslate("Global", "Provider") }
                Item { Layout.fillWidth: true }
                StateText { statusText: overviewViewModel.providerStatus.status; statusValue: overviewViewModel.providerStatus.statusValue }
            }
            GridLayout {
                Layout.fillWidth: true
                columns: page.width >= 850 ? 3 : 1
                rowSpacing: Tokens.space.sm
                columnSpacing: Tokens.space.xl
                MetricLine { label: qsTranslate("Global", "Authentication"); value: overviewViewModel.providerStatus.authentication; translateValue: true }
                MetricLine { label: qsTranslate("Global", "Last refresh"); value: overviewViewModel.providerStatus.lastRefresh; translateValue: true }
                MetricLine { label: qsTranslate("Global", "Data"); value: overviewViewModel.providerStatus.data; translateValue: true }
            }
            Text {
                visible: overviewViewModel.providerStatus.status !== "Connected"
                text: qsTranslate("Global", overviewViewModel.providerStatus.guidance)
                color: Tokens.color.textSecondary
                font.family: Tokens.font.ui
                font.pixelSize: Tokens.type.caption
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Tokens.space.md
            SectionHeader { text: qsTranslate("Global", "Actual usage vs expected pace") }
            UsageChart { Layout.fillWidth: true; points: usageViewModel.points }
            RowLayout {
                spacing: Tokens.space.xl
                Text { text: qsTranslate("Global", "— actual"); color: Tokens.color.accent; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                Text { text: qsTranslate("Global", "- - expected"); color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
            }
        }

        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Tokens.space.sm
            SectionHeader { text: qsTranslate("Global", "Suggested") }
            Text {
                text: overviewViewModel.hasRecommendation
                      ? overviewViewModel.recommendation.model + " · "
                        + qsTranslate("Global", overviewViewModel.recommendation.effort)
                      : qsTranslate("Global", "Analyze a task")
                color: overviewViewModel.hasRecommendation ? Tokens.color.textPrimary : Tokens.color.textSecondary
                font.family: Tokens.font.mono
                font.pixelSize: 20
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: overviewViewModel.hasRecommendation && overviewViewModel.recommendation.explanation.length
                      ? I18n.format(overviewViewModel.recommendation.explanation[0])
                      : qsTranslate("Global", "Recommendations depend on a task profile and current persisted quota.")
                color: Tokens.color.textSecondary
                font.family: Tokens.font.ui
                font.pixelSize: Tokens.type.body
                wrapMode: Text.Wrap
            }
            FlatButton { text: qsTranslate("Global", "Route a task"); onClicked: appController.navigate("Route") }
        }
    }

    Component.onCompleted: if (!appController.smokeMode) usageViewModel.load()
}
