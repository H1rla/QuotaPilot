.pragma library

function format(item) {
    var rendered = qsTranslate("Global", item.source)
    for (var index = 0; index < item.args.length; ++index)
        rendered = rendered.arg(item.args[index])
    return rendered
}
