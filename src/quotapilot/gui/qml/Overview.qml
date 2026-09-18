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

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Tokens.space.xs
                Text {
                    text: "Overview"
                    color: Tokens.color.textPrimary
                    font.family: Tokens.font.ui
                    font.pixelSize: Tokens.type.title
                    font.weight: Font.DemiBold
                }
                Text {
                    text: overviewViewModel.data.provider + "  ·  " + overviewViewModel.data.freshness
                    color: overviewViewModel.data.stale ? Tokens.color.stale : Tokens.color.textMuted
                    font.family: Tokens.font.mono
                    font.pixelSize: Tokens.type.caption
                }
            }
            FlatButton {
                text: overviewViewModel.busy ? "Refreshing…" : "Refresh"
                enabled: !overviewViewModel.busy
                onClicked: overviewViewModel.refresh()
            }
        }

        InlineMessage {
            visible: overviewViewModel.hasError
            Layout.fillWidth: true
            title: "Provider unavailable"
            detail: overviewViewModel.errorMessage
            action: Component { FlatButton { text: "Retry"; onClicked: overviewViewModel.refresh() } }
        }

        EmptyState {
            visible: !overviewViewModel.data.available && !overviewViewModel.busy
            title: "No persisted snapshot"
            detail: "Refresh quota to capture current provider state. Unknown values remain unknown."
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
                        text: overviewViewModel.data.remaining
                        color: Tokens.color.textPrimary
                        font.family: Tokens.font.mono
                        font.pixelSize: Tokens.type.metric
                        font.weight: Font.DemiBold
                    }
                    Text {
                        text: "remaining quota"
                        color: Tokens.color.textSecondary
                        font.family: Tokens.font.ui
                        font.pixelSize: Tokens.type.body
                    }
                }
                ColumnLayout {
                    Layout.preferredWidth: 150
                    MetricLine { label: "Reset"; value: overviewViewModel.data.reset; primary: true }
                    MetricLine { label: "Today"; value: overviewViewModel.data.todayBudget; primary: true }
                }
                ColumnLayout {
                    Layout.preferredWidth: 150
                    Text {
                        text: "Budget state"
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
                MetricLine { Layout.fillWidth: true; label: "Pressure"; value: overviewViewModel.data.pressure }
                MetricLine { Layout.fillWidth: true; label: "Routable"; value: overviewViewModel.data.routableModels }
                MetricLine { Layout.fillWidth: true; label: "Profiles"; value: overviewViewModel.data.profileFreshness }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Tokens.space.md
            SectionHeader { text: "Actual usage vs expected pace" }
            UsageChart { Layout.fillWidth: true; points: usageViewModel.points }
            RowLayout {
                spacing: Tokens.space.xl
                Text { text: "— actual"; color: Tokens.color.accent; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                Text { text: "- - expected"; color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
            }
        }

        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Tokens.space.sm
            SectionHeader { text: "Suggested" }
            Text {
                text: overviewViewModel.hasRecommendation
                      ? overviewViewModel.recommendation.model + " · " + overviewViewModel.recommendation.effort
                      : "Analyze a task"
                color: overviewViewModel.hasRecommendation ? Tokens.color.textPrimary : Tokens.color.textSecondary
                font.family: Tokens.font.mono
                font.pixelSize: 20
                font.weight: Font.DemiBold
            }
            Text {
                Layout.fillWidth: true
                text: overviewViewModel.hasRecommendation && overviewViewModel.recommendation.explanation.length
                      ? overviewViewModel.recommendation.explanation[0]
                      : "Recommendations depend on a task profile and current persisted quota."
                color: Tokens.color.textSecondary
                font.family: Tokens.font.ui
                font.pixelSize: Tokens.type.body
                wrapMode: Text.Wrap
            }
            FlatButton { text: "Route a task"; onClicked: appController.navigate("Route") }
        }
    }

    Component.onCompleted: if (!appController.smokeMode) usageViewModel.load()
}
