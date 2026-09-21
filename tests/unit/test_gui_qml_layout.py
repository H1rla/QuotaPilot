"""Behavioral QML layout regressions for scrolling and shared table columns."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

QML_DIR = Path(__file__).parents[2] / "src" / "quotapilot" / "gui" / "qml"


def _run_layout_probe() -> dict[str, Any]:
    environment = dict(os.environ)
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "QSG_RHI_BACKEND": "software",
            "QT_QUICK_BACKEND": "software",
            "QUOTAPILOT_QML_DIR": str(QML_DIR),
        }
    )
    probe = r'''
import json
import os
from pathlib import Path

from PySide6.QtCore import QByteArray, QObject, QPointF, Property, QTranslator, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickView

qml_dir = Path(os.environ["QUOTAPILOT_QML_DIR"])
app = QGuiApplication([])

engine = QQmlEngine()
engine.addImportPath(str(qml_dir))
component = QQmlComponent(engine)
component.setData(
    QByteArray(
        b"import QtQuick\n"
        b"import QtQuick.Layouts\n"
        b"PageScrollView {\n"
        b"    width: 774; height: 556; contentSpacing: 16\n"
        b"    Repeater {\n"
        b"        model: 30\n"
        b"        delegate: Rectangle { implicitWidth: 700; implicitHeight: 30 }\n"
        b"    }\n"
        b"}\n"
    ),
    QUrl.fromLocalFile(str(qml_dir / "ScrollGeometryProbe.qml")),
)
if component.isError():
    raise RuntimeError("; ".join(error.toString() for error in component.errors()))
scroll = component.create()
app.processEvents()
content = scroll.findChild(QObject, "pageContent")
flickable = next(
    child for child in scroll.children()
    if "Flickable" in child.metaObject().className()
)
scroll_results = []
for width, height in ((774, 556), (974, 676)):
    scroll.setProperty("width", width)
    scroll.setProperty("height", height)
    app.processEvents()
    maximum = scroll.property("contentHeight") - scroll.property("availableHeight")
    flickable.setProperty("contentY", maximum)
    app.processEvents()
    scroll_results.append(
        {
            "size": [width, height],
            "contentHeight": scroll.property("contentHeight"),
            "visualBottom": content.property("y") + content.property("height") + 24,
            "contentY": flickable.property("contentY"),
            "maximum": maximum,
        }
    )


class HistoryModel(QObject):
    @Property(bool, constant=True)
    def hasError(self):
        return False

    @Property(str, constant=True)
    def errorMessage(self):
        return ""

    @Property(bool, constant=True)
    def empty(self):
        return False

    @Property(bool, constant=True)
    def busy(self):
        return False

    @Property("QVariantList", constant=True)
    def items(self):
        return [
            {
                "capturedText": "2026-09-21 12:00",
                "actualText": "65.0%",
                "expectedText": "54.0%",
                "statusValue": "OVER",
            }
            for _ in range(12)
        ]


def visual_items(root):
    found = {}

    def visit(item):
        if item.objectName():
            found.setdefault(item.objectName(), item)
        for child in item.childItems():
            visit(child)

    visit(root)
    return found


def history_geometry(language):
    translator = None
    if language == "ja":
        translator = QTranslator()
        if not translator.load(str(qml_dir.parent / "i18n" / "quotapilot_ja.qm")):
            raise RuntimeError("Japanese catalog did not load")
        app.installTranslator(translator)
    view = QQuickView()
    view.setResizeMode(QQuickView.SizeRootObjectToView)
    model = HistoryModel(view)
    view.rootContext().setContextProperty("historyViewModel", model)
    view.setSource(QUrl.fromLocalFile(str(qml_dir / "History.qml")))
    view.resize(774, 556)
    view.show()
    app.processEvents()
    root = view.rootObject()
    items = visual_items(root)
    result = {}
    for name in ("Actual", "Expected", "State"):
        header = items["historyHeader" + name]
        row = items["historyRow" + name]
        result[name] = {
            "headerX": header.mapToItem(root, QPointF()).x(),
            "rowX": row.mapToItem(root, QPointF()).x(),
            "headerWidth": header.width(),
            "rowWidth": row.width(),
            "text": header.property("text"),
        }
    if translator is not None:
        app.removeTranslator(translator)
    return result


print(json.dumps({
    "scroll": scroll_results,
    "historyEn": history_geometry("en"),
    "historyJa": history_geometry("ja"),
}))
'''
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=Path(__file__).parents[2],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_scroll_bottom_is_in_content_geometry_at_supported_sizes() -> None:
    result = _run_layout_probe()

    for measurement in result["scroll"]:
        assert measurement["contentHeight"] == measurement["visualBottom"]
        assert measurement["contentY"] == measurement["maximum"]

    for name in ("Overview", "Usage", "Route", "Execute", "Settings"):
        assert "PageScrollView {" in (QML_DIR / f"{name}.qml").read_text()


def test_history_columns_share_geometry_in_english_and_japanese() -> None:
    result = _run_layout_probe()

    assert [result["historyEn"][name]["text"] for name in ("Actual", "Expected", "State")] == [
        "Actual",
        "Expected",
        "State",
    ]
    assert [result["historyJa"][name]["text"] for name in ("Actual", "Expected", "State")] == [
        "実績",
        "想定",
        "状態",
    ]
    for language in ("historyEn", "historyJa"):
        for name in ("Actual", "Expected", "State"):
            measurement = result[language][name]
            assert measurement["headerX"] == measurement["rowX"]
            assert measurement["headerWidth"] == measurement["rowWidth"]
