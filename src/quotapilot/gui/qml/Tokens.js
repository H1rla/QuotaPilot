.pragma library

var color = {
    window: "#0B0D10",
    surface: "#111419",
    surfaceRaised: "#15191F",
    border: "#242A31",
    textPrimary: "#F2F4F7",
    textSecondary: "#A5ADB8",
    textMuted: "#68717D",
    accent: "#7EE787",
    accentHover: "#93ED9A",
    accentPressed: "#68D878",
    accentSubtle: "#122318",
    accentFocus: "#254A31",
    accentOn: "#08110B",
    veryUnder: "#68C8D3",
    under: "#77B7C5",
    onTrack: "#A5ADB8",
    over: "#D6A85F",
    critical: "#F07178",
    success: "#5FBF7F",
    unknown: "#68717D",
    stale: "#B99152",
    error: "#F07178"
}

var space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 }
var radius = { structure: 0, control: 4, contained: 6, overlay: 8 }
var type = { caption: 11, body: 13, label: 14, section: 16, title: 25, metric: 34 }
var motion = { fast: 120, normal: 160, panel: 180 }
var font = {
    mono: "IBM Plex Mono, Berkeley Mono, Noto Sans Mono, DejaVu Sans Mono, monospace",
    ui: "Inter, Noto Sans, DejaVu Sans, sans-serif"
}

function stateColor(state) {
    var value = String(state || "UNKNOWN").toUpperCase()
    if (value === "VERY_UNDER") return color.veryUnder
    if (value === "UNDER") return color.under
    if (value === "ON_TRACK") return color.onTrack
    if (value === "OVER") return color.over
    if (value === "CRITICAL") return color.critical
    if (value === "SUCCEEDED" || value === "SUCCESS") return color.success
    if (value === "FAILED" || value === "DENIED" || value === "CANCELLED"
            || value === "QUOTA_CHANGED" || value === "CAPABILITY_CHANGED") return color.error
    if (value === "STALE") return color.stale
    if (value === "ERROR") return color.error
    return color.unknown
}
