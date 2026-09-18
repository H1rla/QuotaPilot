import QtQuick
import "../Tokens.js" as Tokens

Canvas {
    id: root
    property var points: []
    implicitHeight: 170
    onPointsChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    function drawSeries(ctx, field, color, dashed) {
        if (!points || points.length < 1) return
        var valid = []
        for (var i = 0; i < points.length; ++i) {
            var value = points[i][field]
            if (value !== null && value !== undefined) valid.push({x: i, y: value})
        }
        if (valid.length < 1) return
        ctx.beginPath()
        ctx.strokeStyle = color
        ctx.lineWidth = 2
        ctx.setLineDash(dashed ? [5, 5] : [])
        for (var j = 0; j < valid.length; ++j) {
            var px = 8 + (width - 16) * (points.length === 1 ? 0 : valid[j].x / (points.length - 1))
            var py = 8 + (height - 24) * (1 - valid[j].y)
            if (j === 0) ctx.moveTo(px, py)
            else ctx.lineTo(px, py)
        }
        ctx.stroke()
        ctx.setLineDash([])
    }

    onPaint: {
        var ctx = getContext("2d")
        ctx.reset()
        ctx.strokeStyle = Tokens.color.border
        ctx.lineWidth = 1
        for (var i = 0; i <= 4; ++i) {
            var y = 8 + (height - 24) * i / 4
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(width, y); ctx.stroke()
        }
        drawSeries(ctx, "expected", Tokens.color.textMuted, true)
        drawSeries(ctx, "actual", Tokens.color.accent, false)
    }
}

