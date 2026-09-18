import QtQuick
import "../Tokens.js" as Tokens

Text {
    property string statusText: "UNKNOWN"
    text: statusText
    color: Tokens.stateColor(statusText)
    font.family: Tokens.font.mono
    font.pixelSize: Tokens.type.body
    font.weight: Font.DemiBold
}
