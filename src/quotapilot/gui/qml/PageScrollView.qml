import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "Tokens.js" as Tokens

ScrollView {
    id: root
    objectName: "pageScroll"

    default property alias pageContent: contentColumn.data
    property alias contentSpacing: contentColumn.spacing
    property int pagePadding: Tokens.space.xl

    clip: true
    contentWidth: availableWidth
    // ScrollView's automatic size ignores a sole child's x/y offset. Include
    // both page gutters so the visual bottom is also the scrollable bottom.
    contentHeight: contentColumn.implicitHeight + pagePadding * 2
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

    ColumnLayout {
        id: contentColumn
        objectName: "pageContent"
        width: Math.max(0, root.availableWidth - root.pagePadding * 2)
        x: root.pagePadding
        y: root.pagePadding
    }
}
