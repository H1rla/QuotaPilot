"""Offscreen GUI forecast geometry and Japanese rendering."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

QML = Path(__file__).parents[2] / "src" / "quotapilot" / "gui" / "qml"


@pytest.mark.parametrize("language", ["en", "ja"])
def test_forecast_strip_row_wrap_overrun_and_details(language: str) -> None:
    environment = dict(os.environ)
    environment.update({
        "QT_QPA_PLATFORM": "offscreen",
        "QSG_RHI_BACKEND": "software",
        "QT_QUICK_BACKEND": "software",
        "FORECAST_QML": str(QML),
        "FORECAST_LANG": language,
    })
    probe = r'''
import json
import os
from pathlib import Path
from PySide6.QtCore import QPointF, QTranslator, QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView

qml = Path(os.environ["FORECAST_QML"])
app = QGuiApplication([])
if os.environ["FORECAST_LANG"] == "ja":
    translator = QTranslator()
    assert translator.load(str(qml.parent / "i18n" / "quotapilot_ja.qm"))
    app.installTranslator(translator)
view = QQuickView()
view.setResizeMode(QQuickView.SizeRootObjectToView)
view.engine().addImportPath(str(qml))
view.setSource(QUrl.fromLocalFile(str(qml / "components" / "ForecastStrip.qml")))
assert view.status() == QQuickView.Ready, [e.toString() for e in view.errors()]
root = view.rootObject()
points = []
for index, value in enumerate((43, 51, 59, 67, 105, 116, 123)):
    points.append({
        "date": f"2026-09-{25+index:02d}", "weekday": (4+index) % 7,
        "today": index == 0, "projectedText": f"{value}%",
        "expectedText": "39%", "deltaText": "+4%", "remainingText": "57%",
        "statusValue": "CRITICAL" if value >= 100 else "ON_TRACK",
    })
root.setProperty("points", points)
def visual_items(item):
    for child in item.childItems():
        yield child
        yield from visual_items(child)
result = []
for width in (926, 726, 570):
    view.resize(width, 350)
    view.show()
    app.processEvents()
    values = [item for item in visual_items(root) if item.objectName() == "forecastProjected"]
    states = [item for item in visual_items(root) if item.objectName() == "forecastState"]
    result.append({
        "width": width,
        "values": [item.property("text") for item in values],
        "positions": [
            [item.mapToItem(root, QPointF()).x(), item.mapToItem(root, QPointF()).y()]
            for item in values
        ],
        "states": [item.property("text") for item in states],
        "height": root.property("implicitHeight"),
        "detailActive": [item.property("active") for item in visual_items(root)
                         if item.objectName() == "forecastDetails"],
    })
root.setProperty("detailsVisible", True)
app.processEvents()
detail_items = [item for item in visual_items(root) if item.objectName() == "forecastDetails"]
result.append({"detailsHeight": root.property("implicitHeight"),
               "detailsVisible": root.property("detailsVisible"),
               "itemVisible": [item.isVisible() for item in detail_items],
               "itemHeight": [item.height() for item in detail_items]})
root.setProperty("detailsVisible", False)
root.setProperty("points", points[:3])
root.setProperty("stale", True)
app.processEvents()
result.append({"shortValues": [item.property("text") for item in visual_items(root)
                               if item.objectName() == "forecastProjected"],
               "visibleText": [item.property("text") for item in visual_items(root)
                               if item.metaObject().className().startswith("QQuickText")
                               and item.isVisible()]})
root.setProperty("points", [])
root.setProperty("unavailableReason", "insufficient_evidence")
app.processEvents()
result.append({"visibleText": [item.property("text") for item in visual_items(root)
                               if item.metaObject().className().startswith("QQuickText")
                               and item.isVisible()]})
print(json.dumps(result))
'''
    run = subprocess.run(
        [sys.executable, "-c", probe], cwd=QML.parents[3], env=environment,
        capture_output=True, text=True, timeout=20, check=False,
    )
    assert run.returncode == 0, run.stderr
    wide, standard, wrapped, details, short, unavailable = json.loads(run.stdout)
    for item in (wide, standard, wrapped):
        assert len(item["values"]) == 7
        assert item["values"][-1] == "123%"
        assert item["states"][-1] == ("重大" if language == "ja" else "CRITICAL")
    for item in (wide, standard):
        assert len({round(position[1]) for position in item["positions"]}) == 1, item
        assert item["positions"] == sorted(item["positions"], key=lambda position: position[0])
    assert len({round(position[1]) for position in wrapped["positions"]}) == 2
    assert not any(wrapped["detailActive"])
    assert all(details["itemVisible"])
    assert all(height > 0 for height in details["itemHeight"])
    assert short["shortValues"] == ["43%", "51%", "59%"]
    assert ("今日" if language == "ja" else "Today") in short["visibleText"]
    assert any("STALE" in str(value) for value in short["visibleText"])
    assert any("Insufficient" in str(value) or "不足" in str(value)
               for value in unavailable["visibleText"])
