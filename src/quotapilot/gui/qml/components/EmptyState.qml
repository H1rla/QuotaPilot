import QtQuick
import QtQuick.Layouts
import "../Tokens.js" as Tokens

ColumnLayout {
    property string title: "Insufficient data"
    property string detail: ""
    spacing: Tokens.space.sm
    Text {
        text: parent.title
        color: Tokens.color.textPrimary
        font.family: Tokens.font.ui
        font.pixelSize: Tokens.type.section
        font.weight: Font.DemiBold
    }
    Text {
        text: parent.detail
        color: Tokens.color.textSecondary
        font.family: Tokens.font.ui
        font.pixelSize: Tokens.type.body
        wrapMode: Text.Wrap
        Layout.maximumWidth: 520
    }
}

