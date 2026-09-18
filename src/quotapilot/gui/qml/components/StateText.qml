import QtQuick
import "../Tokens.js" as Tokens

Text {
    property string statusText: "UNKNOWN"
    property string statusValue: statusText
    text: qsTranslate("Global", statusText)
    color: Tokens.stateColor(statusValue)
    font.family: Tokens.font.mono
    font.pixelSize: Tokens.type.body
    font.weight: Font.DemiBold
}
