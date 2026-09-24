"""Category/list editor with staged strict validation and explicit save."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, OptionList, Select, Static
from textual.widgets.option_list import Option

from quotapilot.tui.localization import Localizer
from quotapilot.tui.viewmodels.settings import (
    CATEGORIES,
    SETTING_SPECS,
    SettingSpec,
    SettingsViewModel,
    setting_value,
)


class SettingsView(VerticalScroll):
    can_focus = True

    def __init__(self, localizer: Localizer, view_model: SettingsViewModel) -> None:
        super().__init__(id="settings-view", classes="destination-view")
        self._localizer = localizer
        self.view_model = view_model
        self.category = "general"
        self.selected: SettingSpec | None = None
        self.editor_open = False
        self.category_open = False
        self.discard_armed = False
        self.compact = True
        self.feedback_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Static(self._localizer.text("destination.settings"), classes="screen-title")
        yield Input(placeholder=self._localizer.text("settings.filter"), id="settings-filter")
        with Horizontal(id="settings-main"):
            with Vertical(id="settings-categories-region"):
                yield OptionList(id="settings-categories")
            with Vertical(id="settings-fields-region"):
                yield Static("", id="settings-category-title", classes="section-title")
                yield OptionList(id="settings-fields")
                yield Static("", id="settings-apply-note", classes="muted")
        with Vertical(id="settings-editor-region"):
            yield Static("", id="settings-editor-title", classes="section-title")
            yield Input(id="settings-input")
            yield Select[str]([("Default", "")], id="settings-select", allow_blank=False)
            with Horizontal(classes="action-row"):
                yield Button(self._localizer.text("settings.stage"), id="settings-stage")
                yield Button(
                    self._localizer.text("settings.cancel_edit"), id="settings-cancel-edit"
                )
        with Horizontal(classes="action-row"):
            yield Button(self._localizer.text("settings.save"), id="settings-save")
            yield Button(self._localizer.text("settings.discard"), id="settings-discard")
        yield Static("", id="settings-message", classes="notice")

    def on_mount(self) -> None:
        self._render_categories()
        self._render_fields()
        self._render_editor()

    def set_compact(self, compact: bool) -> None:
        self.compact = compact
        if self.is_mounted:
            self._render_editor()

    def focus_filter(self) -> None:
        self.query_one("#settings-filter", Input).focus()

    def focus_categories(self) -> None:
        self.query_one("#settings-categories", OptionList).focus()

    def select_category(self, category: str) -> None:
        if category not in CATEGORIES:
            return
        self.category = category
        self.category_open = True
        self.editor_open = False
        self._render_fields()
        self._render_editor()
        self.query_one("#settings-fields", OptionList).focus()

    def select_field(self, key: str) -> None:
        spec = next((item for item in SETTING_SPECS if item.key == key), None)
        if spec is None:
            return
        self.selected = spec
        self.category = spec.category
        self.category_open = True
        self.editor_open = True
        self._render_fields()
        self._render_editor()
        if spec.kind in {"enum", "bool"}:
            self.query_one("#settings-select", Select).focus()
        else:
            self.query_one("#settings-input", Input).focus()

    def deep_link(self, key: str) -> None:
        self.query_one("#settings-filter", Input).value = ""
        self.select_field(key)

    def close_editor(self) -> None:
        self.editor_open = False
        self._render_editor()
        self.query_one("#settings-fields", OptionList).focus()

    def close_category(self) -> None:
        self.category_open = False
        self._render_editor()
        self.focus_categories()

    def stage(self) -> bool:
        spec = self.selected
        if spec is None:
            return False
        if spec.kind in {"enum", "bool"}:
            selected = self.query_one("#settings-select", Select).value
            value = str(selected) if selected is not Select.BLANK else ""
        else:
            value = self.query_one("#settings-input", Input).value
        valid = self.view_model.update(spec, value)
        self.feedback_id = None
        self._render_fields()
        self._render_message()
        if valid:
            self.close_editor()
        return valid

    def discard(self) -> None:
        self.view_model.discard()
        self.discard_armed = False
        self.feedback_id = None
        self.editor_open = False
        self._render_fields()
        self._render_editor()
        self._render_message()

    def arm_discard(self) -> bool:
        if not self.view_model.dirty:
            return False
        if self.discard_armed:
            self.discard()
            return False
        self.discard_armed = True
        self._render_message()
        return True

    def update_editor_state(self) -> None:
        self.discard_armed = False
        self._render_categories()
        self._render_fields()
        self._render_message()

    def _render_categories(self) -> None:
        options = self.query_one("#settings-categories", OptionList)
        options.clear_options()
        query = self.query_one("#settings-filter", Input).value.casefold().strip()
        visible: list[str] = []
        for category in CATEGORIES:
            label = self._localizer.text(f"settings.category.{category}")
            fields = (
                f"{spec.key} {self._localizer.text(f'settings.field.{spec.key}')}"
                for spec in SETTING_SPECS
                if spec.category == category
            )
            if (
                query
                and query not in label.casefold()
                and not any(query in field.casefold() for field in fields)
            ):
                continue
            visible.append(category)
            options.add_option(Option(label, id=category))
        if visible:
            if self.category not in visible:
                self.category = visible[0]
            options.highlighted = visible.index(self.category)

    def _render_fields(self) -> None:
        t = self._localizer.text
        self.query_one("#settings-category-title", Static).update(
            t(f"settings.category.{self.category}")
        )
        query = self.query_one("#settings-filter", Input).value.casefold().strip()
        options = self.query_one("#settings-fields", OptionList)
        options.clear_options()
        for spec in SETTING_SPECS:
            if spec.category != self.category:
                continue
            label = t(f"settings.field.{spec.key}")
            category_label = t(f"settings.category.{spec.category}")
            if query not in f"{label} {spec.key} {category_label}".casefold():
                continue
            value = setting_value(self.view_model.draft, spec.key) or t("settings.default")
            if spec.kind in {"enum", "bool"}:
                raw = setting_value(self.view_model.draft, spec.key)
                value = t(f"settings.choice.{raw or 'default'}")
            options.add_option(Option(f"{label}    {value}", id=spec.key))
        if options.option_count:
            options.highlighted = 0
        note = t("settings.next_launch")
        resolution = getattr(self.app, "theme_resolution", None)
        if resolution is not None and resolution.used_fallback:
            note += "\n" + t("settings.system_fallback")
        self.query_one("#settings-apply-note", Static).update(note)
        self._render_message()

    def _render_editor(self) -> None:
        region = self.query_one("#settings-editor-region", Vertical)
        region.display = self.editor_open and self.selected is not None
        self.query_one("#settings-main", Horizontal).display = (
            not self.editor_open or not self.compact
        )
        self.query_one("#settings-categories-region", Vertical).display = (
            not self.compact or not self.category_open
        )
        self.query_one("#settings-fields-region", Vertical).display = (
            not self.compact or self.category_open
        )
        if not region.display or self.selected is None:
            return
        spec = self.selected
        self.query_one("#settings-editor-title", Static).update(
            self._localizer.text(f"settings.field.{spec.key}")
        )
        is_select = spec.kind in {"enum", "bool"}
        self.query_one("#settings-select", Select).display = is_select
        self.query_one("#settings-input", Input).display = not is_select
        value = setting_value(self.view_model.draft, spec.key)
        if is_select:
            values = spec.options if spec.kind == "enum" else ("false", "true")
            choices = [
                (self._localizer.text(f"settings.choice.{item or 'default'}"), item)
                for item in values
            ]
            selector = self.query_one("#settings-select", Select)
            selector.set_options(choices)
            selector.value = value
        else:
            self.query_one("#settings-input", Input).value = value

    def _render_message(self) -> None:
        t = self._localizer.text
        value = self.view_model.error or (
            "settings.discard_confirm"
            if self.discard_armed
            else "settings.unsaved"
            if self.view_model.dirty
            else self.feedback_id or ""
        )
        self.query_one("#settings-message", Static).update(t(value) if value else "")
