import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Tokens.js" as Tokens

Item {
    id: overlay
    visible: commandPalette.open
    anchors.fill: parent
    z: 100
    Rectangle { anchors.fill: parent; color: "#99000000"; TapHandler { onTapped: commandPalette.close() } }
    Rectangle {
        width: Math.min(620, parent.width - 64)
        height: Math.min(420, parent.height - 100)
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.top: parent.top; anchors.topMargin: 72
        color: Tokens.color.surfaceRaised
        border.color: Tokens.color.border; border.width: 1; radius: Tokens.radius.overlay
        ColumnLayout {
            anchors.fill: parent; spacing: 0
            TextField {
                id: query
                Layout.fillWidth: true; Layout.preferredHeight: 48
                placeholderText: qsTranslate("Global", "Type a command")
                color: Tokens.color.textPrimary; placeholderTextColor: Tokens.color.textMuted
                font.family: Tokens.font.mono; font.pixelSize: Tokens.type.body
                leftPadding: Tokens.space.lg; rightPadding: Tokens.space.lg
                background: Rectangle { color: Tokens.color.surface; border.width: 0 }
                onTextChanged: commandPalette.setQuery(text)
                Keys.onDownPressed: commandPalette.moveNext()
                Keys.onUpPressed: commandPalette.movePrevious()
                Keys.onReturnPressed: commandPalette.activateSelected()
                Keys.onEscapePressed: commandPalette.close()
            }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Tokens.color.border }
            ListView {
                id: commands
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                model: commandPalette.rows
                currentIndex: commandPalette.selectedIndex
                delegate: Rectangle {
                    required property int index
                    required property string title
                    required property string hint
                    width: ListView.view.width; height: 42
                    color: index === commandPalette.selectedIndex || commandHover.hovered
                           ? Tokens.color.accentSubtle : "transparent"
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: Tokens.space.lg; anchors.rightMargin: Tokens.space.lg
                        Text { text: title; color: index === commandPalette.selectedIndex ? Tokens.color.accent : Tokens.color.textPrimary; font.family: Tokens.font.ui; font.pixelSize: Tokens.type.body; Layout.fillWidth: true }
                        Text { text: hint; color: Tokens.color.textMuted; font.family: Tokens.font.mono; font.pixelSize: Tokens.type.caption }
                    }
                    HoverHandler { id: commandHover }
                    TapHandler { onTapped: commandPalette.activate(index) }
                }
            }
        }
    }
    onVisibleChanged: if (visible) { query.text = ""; query.forceActiveFocus() }
}
