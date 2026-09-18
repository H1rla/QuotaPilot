import QtQuick
import QtQuick.Controls
import "../Tokens.js" as Tokens

Button {
    id: control
    property bool primary: false
    property bool danger: false
    implicitHeight: 36
    leftPadding: Tokens.space.lg
    rightPadding: Tokens.space.lg
    font.family: Tokens.font.ui
    font.pixelSize: Tokens.type.body
    font.weight: Font.Medium
    focusPolicy: Qt.StrongFocus

    contentItem: Text {
        text: control.text
        color: control.primary ? Tokens.color.accentOn
                               : control.danger ? Tokens.color.error : Tokens.color.textPrimary
        font: control.font
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle {
        radius: Tokens.radius.control
        color: control.primary
               ? (control.down ? Tokens.color.accentPressed
                               : control.hovered ? Tokens.color.accentHover : Tokens.color.accent)
               : control.hovered ? Tokens.color.surfaceRaised : "transparent"
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? Tokens.color.accent : Tokens.color.border
    }
}

