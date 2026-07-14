.pragma library

function ensureVisible(flickable, item, margin) {
    if (!flickable || !item || !flickable.contentItem)
        return
    var current = item
    var belongsToContent = false
    while (current) {
        if (current === flickable.contentItem) {
            belongsToContent = true
            break
        }
        current = current.parent
    }
    if (!belongsToContent)
        return
    var point = item.mapToItem(flickable.contentItem, 0, 0)
    var safeMargin = Math.max(8, Number(margin || 20))
    var top = point.y
    var bottom = point.y + Math.max(item.height, 1)
    var viewTop = flickable.contentY
    var viewBottom = flickable.contentY + flickable.height
    var target = flickable.contentY
    if (top < viewTop + safeMargin)
        target = top - safeMargin
    else if (bottom > viewBottom - safeMargin)
        target = bottom - flickable.height + safeMargin
    target = Math.max(0, Math.min(target, Math.max(0, flickable.contentHeight - flickable.height)))
    if (Math.abs(target - flickable.contentY) > 2)
        flickable.contentY = target
}
