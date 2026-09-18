import QtQuick
import QtQuick.Layouts
import "../Tokens.js" as Tokens

RowLayout {
    id: root
    property string label: ""
    property string value: "Unknown"
    property bool primary: false
    property bool translateValue: false
    spacing: Tokens.space.md
    Text {
        text: qsTranslate("Global", root.label)
        color: Tokens.color.textMuted
        font.family: Tokens.font.ui
        font.pixelSize: Tokens.type.caption
        Layout.preferredWidth: root.primary ? 112 : 132
    }
    Text {
        text: root.translateValue ? qsTranslate("Global", root.value) : root.value
        color: Tokens.color.textPrimary
        font.family: Tokens.font.mono
        font.pixelSize: root.primary ? Tokens.type.label : Tokens.type.body
        font.weight: root.primary ? Font.DemiBold : Font.Normal
        Layout.fillWidth: true
        elide: Text.ElideRight
    }
}
