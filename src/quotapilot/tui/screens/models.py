"""Narrow model list, local filter, and progressively disclosed detail."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from quotapilot.capabilities.models import ProfileFreshness
from quotapilot.tui.localization import Localizer
from quotapilot.tui.viewmodels.models import ModelRow, ModelsState


class ModelsView(VerticalScroll):
    can_focus = True

    def __init__(self, localizer: Localizer) -> None:
        super().__init__(id="models-view", classes="destination-view")
        self._localizer = localizer
        self._state = ModelsState()
        self._visible: tuple[ModelRow, ...] = ()
        self.selected_id: str | None = None
        self.detail_open = False
        self.evidence_open = False
        self.compact = True

    def compose(self) -> ComposeResult:
        yield Static(self._localizer.text("destination.models"), classes="screen-title")
        yield Input(placeholder=self._localizer.text("models.filter"), id="models-filter")
        yield Static("", id="models-message", classes="notice")
        with Horizontal(id="models-main"):
            with Vertical(id="models-list-region"):
                yield OptionList(id="models-list")
                yield Static("", id="models-count", classes="muted")
            with Vertical(id="models-detail-region"):
                yield Static("", id="models-detail")
                yield Static("", id="models-evidence", classes="muted")

    def on_mount(self) -> None:
        self.query_one("#models-detail-region", Vertical).can_focus = True
        self.update_state(ModelsState())

    def focus_list(self) -> None:
        self.query_one("#models-list", OptionList).focus()

    def focus_filter(self) -> None:
        self.query_one("#models-filter", Input).focus()

    def set_filter(self, query: str) -> None:
        self.query_one("#models-filter", Input).value = query
        self._rebuild_list()

    def set_compact(self, compact: bool) -> None:
        self.compact = compact
        if self.is_mounted:
            self._render_detail()

    def update_state(self, state: ModelsState) -> None:
        self._state = state
        if not self.is_mounted:
            return
        message_id = state.message_id
        if state.status == "loading":
            message_id = "models.loading"
        message_widget = self.query_one("#models-message", Static)
        message_widget.set_class(state.status == "error", "semantic-error")
        message_widget.update(Text(self._localizer.text(message_id) if message_id else ""))
        self._rebuild_list()

    def _rebuild_list(self) -> None:
        query = self.query_one("#models-filter", Input).value.casefold().strip()
        self._visible = tuple(
            row
            for row in self._state.models
            if query
            in " ".join(
                (
                    row.view.model_id,
                    row.view.freshness.value if row.view.freshness else "unknown",
                    self._localizer.text(
                        f"models.{row.view.freshness.value}"
                        if row.view.freshness
                        else "models.unknown"
                    ),
                    "routable" if row.view.routable else "not routable",
                    self._localizer.text(
                        "models.routable" if row.view.routable else "models.not_routable"
                    ),
                )
            ).casefold()
        )
        options = self.query_one("#models-list", OptionList)
        options.clear_options()
        for row in self._visible:
            view = row.view
            freshness = self._localizer.text(
                f"models.{view.freshness.value}" if view.freshness else "models.unknown"
            )
            routable = self._localizer.text(
                "models.routable" if view.routable else "models.not_routable"
            )
            prompt = Text(f"{view.model_id}   {freshness}   {routable}")
            if view.freshness is ProfileFreshness.STALE:
                start = len(view.model_id) + 3
                prompt.stylize(
                    self.app.current_theme.variables["stale"], start, start + len(freshness)
                )
            options.add_option(Option(prompt, id=view.model_id))
        ids = [row.view.model_id for row in self._visible]
        self.selected_id = (
            self.selected_id if self.selected_id in ids else (ids[0] if ids else None)
        )
        if self.selected_id is not None:
            options.highlighted = ids.index(self.selected_id)
        self.query_one("#models-count", Static).update(
            Text(
                self._localizer.text(
                    "models.count",
                    count=len(self._visible),
                    routable=sum(row.view.routable for row in self._visible),
                )
            )
        )
        self._render_detail()

    def select(self, model_id: str | None) -> None:
        if model_id is None:
            return
        self.selected_id = model_id
        self.detail_open = True
        self._render_detail()
        self.query_one("#models-detail-region", Vertical).focus()

    def close_detail(self) -> None:
        self.detail_open = False
        self.evidence_open = False
        self._render_detail()
        self.focus_list()

    def toggle_evidence(self) -> None:
        self.evidence_open = not self.evidence_open
        self._render_detail()

    def _render_detail(self) -> None:
        region = self.query_one("#models-detail-region", Vertical)
        region.display = self.detail_open and self.selected_id is not None
        self.query_one("#models-list-region", Vertical).display = (
            not self.detail_open or not self.compact
        )
        if not region.display:
            return
        row = next(row for row in self._visible if row.view.model_id == self.selected_id)
        view = row.view
        unknown = self._localizer.text("value.unknown")

        def metric(value: float | None) -> str:
            return unknown if value is None else f"{value:.2f}"

        def line(key: str, value: str) -> str:
            return f"{self._localizer.text(key)}: {value}"

        freshness = self._localizer.text(
            f"models.{view.freshness.value}" if view.freshness else "models.unknown"
        )
        lines = [
            view.model_id,
            line(
                "models.selectable",
                self._localizer.text("models.yes" if view.selectable else "models.no"),
            ),
            line(
                "models.routable_label",
                self._localizer.text("models.routable" if view.routable else "models.not_routable"),
            ),
            line("models.power", metric(view.relative_power)),
            line("models.cost", metric(view.relative_cost)),
            line("models.latency", metric(view.relative_latency)),
            line("models.efforts", ", ".join(row.supported_efforts) or unknown),
            line("models.effort_order", ", ".join(view.effort_order or ()) or unknown),
            line("models.profile", view.profile_name or unknown),
            line("models.source", view.profile_source.value if view.profile_source else unknown),
            line(
                "models.confidence",
                view.profile_confidence.value if view.profile_confidence else unknown,
            ),
            line("models.verified", view.verified_at.isoformat() if view.verified_at else unknown),
            line("models.freshness", freshness),
        ]
        detail_text = Text("\n".join(lines))
        if view.freshness is ProfileFreshness.STALE:
            detail_text.stylize(
                self.app.current_theme.variables["stale"],
                len(detail_text.plain) - len(freshness),
                len(detail_text.plain),
            )
        self.query_one("#models-detail", Static).update(detail_text)
        provenance = tuple(
            f"{field}: {source}" for field, source in sorted(view.field_sources.items())
        )
        evidence = "\n".join(view.profile_evidence + view.warnings + provenance)
        self.query_one("#models-evidence", Static).update(
            Text(f"{self._localizer.text('models.evidence')}: {evidence or unknown}")
        )
        self.query_one("#models-evidence", Static).display = self.evidence_open
