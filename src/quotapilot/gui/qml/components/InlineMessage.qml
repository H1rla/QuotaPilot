import QtQuick
import QtQuick.Layouts
import "../Tokens.js" as Tokens

Rectangle {
    id: root
    property string title: ""
    property string detail: ""
    property string tone: "error"
    property alias action: actionLoader.sourceComponent
    implicitHeight: content.implicitHeight + Tokens.space.lg * 2
    color: Tokens.color.surface
    border.color: root.tone === "stale" ? Tokens.color.stale : Tokens.color.error
    border.width: 1
    radius: Tokens.radius.control

    RowLayout {
        id: content
        anchors.fill: parent
        anchors.margins: Tokens.space.lg
        spacing: Tokens.space.lg
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Tokens.space.xs
            Text {
                text: qsTranslate("Global", root.title)
                color: Tokens.color.textPrimary
                font.family: Tokens.font.ui
                font.pixelSize: Tokens.type.body
                font.weight: Font.DemiBold
            }
            Text {
                text: qsTranslate("Global", root.detail)
                visible: text.length > 0
                color: Tokens.color.textSecondary
                font.family: Tokens.font.ui
                font.pixelSize: Tokens.type.caption
                wrapMode: Text.Wrap
                Layout.fillWidth: true
            }
        }
        Loader { id: actionLoader }
    }
}
