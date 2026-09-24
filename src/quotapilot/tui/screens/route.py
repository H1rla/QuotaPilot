"""Task entry and concise advisory recommendation."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Static, TextArea

from quotapilot.capabilities.enrichment import capability_views
from quotapilot.providers.base import ProviderConnection
from quotapilot.routing.models import QuotaPressureSource
from quotapilot.tui.localization import Localizer
from quotapilot.tui.viewmodels.route import RouteState


class RouteView(VerticalScroll):
    can_focus = True

    def __init__(self, localizer: Localizer) -> None:
        super().__init__(id="route-view", classes="destination-view")
        self._localizer = localizer
        self.details = False
        self.provider_connection = ProviderConnection.UNKNOWN

    def compose(self) -> ComposeResult:
        yield Static(self._localizer.text("destination.route"), classes="screen-title")
        yield Static(self._localizer.text("route.prompt"), classes="section-title")
        yield TextArea(id="route-task")
        with Horizontal(classes="action-row"):
            yield Button(self._localizer.text("route.analyze"), id="route-analyze")
        yield Static("", id="route-message", classes="notice")
        with Vertical(id="route-result"):
            yield Static(self._localizer.text("route.recommended"), classes="section-title")
            yield Static("", id="route-model", classes="route-model")
            yield Static(self._localizer.text("route.why"), classes="section-title")
            yield Static("", id="route-why")
            yield Static(self._localizer.text("route.escalation"), classes="section-title")
            yield Static("", id="route-escalation")
            yield Static("", id="route-context", classes="muted")
            yield Static("", id="route-details", classes="muted")
            with Horizontal(classes="action-row"):
                yield Button(self._localizer.text("route.dry_run"), id="route-dry-run")
                yield Button(self._localizer.text("destination.execute"), id="route-execute")
                yield Button(self._localizer.text("route.details"), id="route-toggle-details")

    def on_mount(self) -> None:
        self.update_state(RouteState())

    def focus_editor(self) -> None:
        self.query_one("#route-task", TextArea).focus()

    def update_state(self, state: RouteState) -> None:
        if not self.is_mounted:
            return
        context = state.context
        self.query_one("#route-result", Vertical).display = context is not None
        message = self._localizer.text(state.message_id) if state.message_id else ""
        if state.status == "analyzing":
            message = self._localizer.text("route.analyzing")
        elif state.status == "empty" and self.provider_connection is ProviderConnection.UNAVAILABLE:
            message = self._localizer.text("route.provider_unavailable")
        message_widget = self.query_one("#route-message", Static)
        message_widget.set_class(state.status == "error", "semantic-error")
        message_widget.update(Text(message))
        if context is None:
            return
        recommendation = context.recommendation
        profile = recommendation.task_profile
        effort = recommendation.selected_effort or self._localizer.text("value.unknown")
        self.query_one("#route-model", Static).update(
            Text(f"{recommendation.selected_model_id} · {effort}")
        )
        pressure_reason = (
            self._localizer.text("route.reason.unknown_pressure")
            if recommendation.quota_pressure_source is QuotaPressureSource.FALLBACK_UNKNOWN
            else self._localizer.text(
                "route.reason.pressure", value=f"{recommendation.quota_pressure:.2f}"
            )
        )
        reasons = [
            self._localizer.text("route.reason.capability"),
            self._localizer.text(
                "route.reason.verifiability", value=f"{profile.verifiability:.2f}"
            ),
            pressure_reason,
        ]
        self.query_one("#route-why", Static).update(Text("\n".join(f"• {x}" for x in reasons)))
        path = recommendation.escalation_path
        escalation = (
            " → ".join(
                f"{step.model_id} · {step.effort or self._localizer.text('value.unknown')}"
                for step in path
            )
            if path
            else self._localizer.text("route.no_escalation")
        )
        self.query_one("#route-escalation", Static).update(Text(escalation))
        flags: list[tuple[str, bool]] = []
        if context.budget_report.is_stale:
            flags.append((self._localizer.text("route.stale"), True))
        if recommendation.quota_pressure_source is QuotaPressureSource.FALLBACK_UNKNOWN:
            flags.append((self._localizer.text("route.unknown_quota"), False))
        selected = next(
            (
                model
                for model in context.capabilities.models
                if model.id == recommendation.selected_model_id
            ),
            None,
        )
        if selected is not None:
            profile_warnings = selected.metadata.get("routing_profile", {}).get("warnings", ())
            if any(":stale:not_applied" in warning for warning in profile_warnings):
                flags.append((self._localizer.text("route.profile_stale"), True))
        if self.provider_connection is ProviderConnection.UNAVAILABLE:
            flags.append((self._localizer.text("route.provider_unavailable"), False))
        context_text = Text()
        for index, (label, stale) in enumerate(flags):
            if index:
                context_text.append(" · ")
            context_text.append(
                label,
                style=self.app.current_theme.variables["stale"] if stale else None,
            )
        self.query_one("#route-context", Static).update(context_text)
        details = (
            f"{self._localizer.text('route.complexity')}: {profile.complexity:.2f}   "
            f"{self._localizer.text('route.ambiguity')}: {profile.ambiguity:.2f}\n"
            f"{self._localizer.text('route.failure_cost')}: {profile.failure_cost:.2f}   "
            f"{self._localizer.text('route.verifiability')}: {profile.verifiability:.2f}\n"
            f"{self._localizer.text('route.context_demand')}: {profile.context_demand:.2f}   "
            f"{self._localizer.text('route.latency')}: {profile.latency_sensitivity:.2f}\n"
            f"{self._localizer.text('route.required_power')}: "
            f"{recommendation.required_power:.2f}   "
            f"{self._localizer.text('route.profile_source')}: {profile.profile_source.value}\n"
            + "\n".join(
                f"{score.model_id}: {score.utility:.2f}"
                for score in recommendation.candidate_scores
                if score.utility is not None
            )
        )
        unknown = self._localizer.text("value.unknown")

        def metric(value: float | None) -> str:
            return unknown if value is None else f"{value:.2f}"

        score_lines = []
        for score in recommendation.candidate_scores:
            score_lines.append(
                f"{score.model_id}: "
                f"{self._localizer.text('route.utility')}={metric(score.utility)}, "
                f"{self._localizer.text('route.quality')}={metric(score.quality_score)}, "
                f"{self._localizer.text('route.quota_penalty')}={metric(score.quota_penalty)}, "
                f"{self._localizer.text('route.latency_penalty')}={metric(score.latency_penalty)}"
            )
        if score_lines:
            details += "\n" + self._localizer.text("route.scoring") + "\n"
            details += "\n".join(score_lines)
        selected_view = next(
            (
                view
                for view in capability_views(context.capabilities)
                if view.model_id == recommendation.selected_model_id
            ),
            None,
        )
        if selected_view is not None:
            details += (
                "\n"
                + self._localizer.text("route.profile_metadata")
                + "\n"
                + self._localizer.text("models.profile")
                + ": "
                + (selected_view.profile_name or unknown)
                + "\n"
                + self._localizer.text("models.confidence")
                + ": "
                + (
                    selected_view.profile_confidence.value
                    if selected_view.profile_confidence
                    else unknown
                )
                + "\n"
                + self._localizer.text("models.verified")
                + ": "
                + (selected_view.verified_at.isoformat() if selected_view.verified_at else unknown)
            )
        if recommendation.explanation:
            details += "\n" + self._localizer.text("route.core_explanation")
            details += "\n" + "\n".join(f"• {item}" for item in recommendation.explanation)
        detail_widget = self.query_one("#route-details", Static)
        detail_widget.update(Text(details))
        detail_widget.display = self.details

    def toggle_details(self, state: RouteState) -> None:
        self.details = not self.details
        self.update_state(state)
