"""Navigation and cross-view coordination without business calculations."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot

from ..async_runner import AsyncRunner
from ..dependencies import GuiDependencies
from ..viewmodels.command_palette import CommandPaletteViewModel
from ..viewmodels.execute import ExecuteViewModel
from ..viewmodels.history import HistoryViewModel
from ..viewmodels.models import ModelsViewModel
from ..viewmodels.overview import OverviewViewModel
from ..viewmodels.route import RouteViewModel
from ..viewmodels.settings import SettingsViewModel
from ..viewmodels.usage import UsageViewModel

PAGES = ("Overview", "Usage", "Models", "Route", "Execute", "History", "Settings")


class AppController(QObject):
    navigationChanged = Signal()

    def __init__(self, dependencies: GuiDependencies, *, smoke_mode: bool = False) -> None:
        super().__init__()
        self.runner = AsyncRunner(self)
        self.overview = OverviewViewModel(dependencies, self.runner)
        self.usage = UsageViewModel(dependencies, self.runner)
        self.models = ModelsViewModel(dependencies, self.runner)
        self.route = RouteViewModel(dependencies, self.runner)
        self.execute = ExecuteViewModel(dependencies, self.runner)
        self.history = HistoryViewModel(dependencies, self.runner)
        self.settings = SettingsViewModel(dependencies, self.runner)
        self.palette = CommandPaletteViewModel()
        self._page_index = 0
        self._details_visible = False
        self._smoke_mode = smoke_mode
        self.route.recommendationReady.connect(self.overview.set_recommendation)
        self.palette.commandActivated.connect(self.triggerCommand)

    @Property(int, notify=navigationChanged)
    def pageIndex(self) -> int:  # noqa: N802
        return self._page_index

    @Property(str, notify=navigationChanged)
    def pageName(self) -> str:  # noqa: N802
        return PAGES[self._page_index]

    @Property(bool, notify=navigationChanged)
    def detailsVisible(self) -> bool:  # noqa: N802
        return self._details_visible

    @Property(str, constant=True)
    def workingDirectory(self) -> str:  # noqa: N802
        return str(Path.cwd())

    @Property(bool, constant=True)
    def smokeMode(self) -> bool:  # noqa: N802
        return self._smoke_mode

    @Slot(str)
    def navigate(self, page: str) -> None:
        normalized = page.strip().title()
        if normalized not in PAGES:
            return
        self._page_index = PAGES.index(normalized)
        self.navigationChanged.emit()
        self._load_page(normalized)

    @Slot()
    def refresh(self) -> None:
        self.overview.refresh()

    @Slot()
    def toggleDetails(self) -> None:  # noqa: N802
        self._details_visible = not self._details_visible
        self.navigationChanged.emit()

    @Slot(str)
    def triggerCommand(self, command_id: str) -> None:  # noqa: N802
        page_commands = {
            "overview": "Overview",
            "usage": "Usage",
            "models": "Models",
            "route": "Route",
            "execute": "Execute",
            "history": "History",
            "settings": "Settings",
            "settings-budget": "Settings",
            "settings-routing": "Settings",
        }
        if command_id in page_commands:
            self.navigate(page_commands[command_id])
        elif command_id == "refresh":
            self.refresh()
        elif command_id == "details":
            self.toggleDetails()

    @Slot()
    def initialize(self) -> None:
        self.overview.load()

    def _load_page(self, page: str) -> None:
        if page == "Overview":
            self.overview.load()
        elif page == "Usage":
            self.usage.load()
        elif page == "Models":
            self.models.load()
        elif page == "History":
            self.history.load()
