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
                        color: appController.pageName === modelData ? Tokens.color.accentSubtle : "transparent"
                        Rectangle { visible: appController.pageName === modelData; width: 2; height: parent.height; color: Tokens.color.accent }
                        Text { anchors.verticalCenter: parent.verticalCenter; anchors.left: parent.left; anchors.leftMargin: Tokens.space.lg; text: modelData; color: appController.pageName === modelData ? Tokens.color.accent : Tokens.color.textSecondary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body }
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
                    Text { text: appController.pageName; color: Tokens.color.textSecondary; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    Item { Layout.fillWidth: true }
                    Text { text: appController.detailsVisible ? "DETAILS ON" : "DETAILS OFF"; color: appController.detailsVisible ? Tokens.color.accent : Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    Text { text: "Ctrl+P commands"; color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
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
