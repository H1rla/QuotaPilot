pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import "../Tokens.js" as Tokens

Item {
    id: root
    property var points: []
    property string unavailableReason: ""
    property bool stale: false
    property bool detailsVisible: false
    implicitHeight: content.implicitHeight

    function dayLabel(point) {
        if (point.today) return qsTranslate("Global", "Today")
        switch (point.weekday) {
        case 0: return qsTranslate("Global", "Mon")
        case 1: return qsTranslate("Global", "Tue")
        case 2: return qsTranslate("Global", "Wed")
        case 3: return qsTranslate("Global", "Thu")
        case 4: return qsTranslate("Global", "Fri")
        case 5: return qsTranslate("Global", "Sat")
        default: return qsTranslate("Global", "Sun")
        }
    }

    function stateLabel(value) {
        switch (value) {
        case "VERY_UNDER": return qsTranslate("Global", "VERY UNDER")
        case "UNDER": return qsTranslate("Global", "UNDER")
        case "ON_TRACK": return qsTranslate("Global", "ON TRACK")
        case "OVER": return qsTranslate("Global", "OVER")
        case "CRITICAL": return qsTranslate("Global", "CRITICAL")
        default: return qsTranslate("Global", "UNKNOWN")
        }
    }

    function reasonLabel(value) {
        if (value === "insufficient_evidence" || value === "incompatible_window")
            return qsTranslate("Global", "Insufficient data to estimate today's pace.")
        if (value === "reset_unknown") return qsTranslate("Global", "Reset is unknown.")
        if (value === "quota_unknown") return qsTranslate("Global", "Quota is unknown.")
        if (value === "reset_passed") return qsTranslate("Global", "Quota window has ended.")
        return qsTranslate("Global", "Forecast unavailable")
    }

    ColumnLayout {
        id: content
        width: root.width
        spacing: Tokens.space.md
        RowLayout {
            Layout.fillWidth: true
            Text { text: qsTranslate("Global", "Forecast — today's pace"); color: Tokens.color.textPrimary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.section; font.weight: Font.DemiBold }
            Item { Layout.fillWidth: true }
            Text { visible: root.stale; text: qsTranslate("Global", "Based on persisted data · STALE"); color: Tokens.color.stale; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
        }
        Text {
            visible: root.points.length === 0
            text: root.reasonLabel(root.unavailableReason)
            color: Tokens.color.textSecondary
            font.family: Tokens.font.ui
            font.pixelSize: Tokens.type.body
        }
        GridLayout {
            id: grid
            visible: root.points.length > 0
            Layout.fillWidth: true
            columns: root.width >= 650 ? 7 : 4
            columnSpacing: root.width >= 650 ? Tokens.space.sm : Tokens.space.xs
            rowSpacing: Tokens.space.lg
            Repeater {
                model: root.points
                delegate: ColumnLayout {
                    id: cell
                    required property var modelData
                    Layout.preferredWidth: Math.max(0, (grid.width - (grid.columns - 1) * grid.columnSpacing) / grid.columns)
                    Layout.alignment: Qt.AlignTop
                    spacing: Tokens.space.xs
                    Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
                    Text { text: root.dayLabel(cell.modelData); color: Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body }
                    Text { objectName: "forecastProjected"; text: cell.modelData.projectedText; color: Tokens.color.textPrimary; font.family: Tokens.font.mono; font.pixelSize: 22; font.weight: Font.DemiBold }
                    Text { objectName: "forecastState"; text: root.stateLabel(cell.modelData.statusValue); color: Tokens.stateColor(cell.modelData.statusValue); font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    Loader {
                        objectName: "forecastDetails"
                        active: root.detailsVisible
                        Layout.preferredHeight: active ? implicitHeight : 0
                        sourceComponent: ColumnLayout {
                            spacing: Tokens.space.xs
                            Text { text: cell.modelData.date; color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                            Text { text: qsTranslate("Global", "Expected") + " " + cell.modelData.expectedText; color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                            Text { text: qsTranslate("Global", "Delta") + " " + cell.modelData.deltaText; color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                            Text { text: qsTranslate("Global", "Remaining") + " " + cell.modelData.remainingText; color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                        }
                    }
                }
            }
        }
        Text { visible: root.detailsVisible && root.points.length > 0 && !root.stale; text: qsTranslate("Global", "Based on persisted data") + " · " + qsTranslate("Global", "Projected end of each day"); color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
    }
}
