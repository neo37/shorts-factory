"""Design-style presets. One project chooses a design; the renderer themes the
composition from these tokens. Custom themes (e.g. derived from a website) can be
passed to the renderer as a dict with the same keys.
"""

# Each theme provides visual tokens; the composition layout stays the same.
# Keys: bg, panel, primary, accent, fg, fg2, muted, font_family, font_url,
#       radius(px), border(css), shadow(css), scrim(rgba), h1_weight, eyebrow_upper(bool)
THEMES = {
    "businesspad-dark": {
        "label": "BusinessPad Dark",
        "bg": "#000000", "panel": "#1A1A1A", "primary": "#7C88FC", "accent": "#FF8562",
        "fg": "#FFFFFF", "fg2": "rgba(255,255,255,.72)", "muted": "rgba(255,255,255,.5)",
        "font_family": '"Manrope",system-ui,sans-serif',
        "font_url": "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap",
        "radius": 24, "border": "none", "shadow": "none", "scrim": "rgba(0,0,0,.5)",
        "h1_weight": 800, "eyebrow_upper": True,
    },
    "neo-brutalism": {
        "label": "Нео-брутализм",
        "bg": "#FFE600", "panel": "#FFFFFF", "primary": "#1A1AFF", "accent": "#FF2D55",
        "fg": "#000000", "fg2": "#000000", "muted": "rgba(0,0,0,.6)",
        "font_family": '"Space Grotesk","Arial Black",sans-serif',
        "font_url": "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&display=swap",
        "radius": 0, "border": "5px solid #000", "shadow": "10px 10px 0 #000",
        "scrim": "rgba(255,255,255,.35)", "h1_weight": 700, "eyebrow_upper": True,
    },
    "apple-minimal": {
        "label": "Apple Minimal",
        "bg": "#FFFFFF", "panel": "#F5F5F7", "primary": "#0071E3", "accent": "#06C",
        "fg": "#1D1D1F", "fg2": "#424245", "muted": "#86868B",
        "font_family": '"Inter",-apple-system,system-ui,sans-serif',
        "font_url": "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap",
        "radius": 20, "border": "none", "shadow": "0 8px 40px rgba(0,0,0,.08)",
        "scrim": "rgba(0,0,0,.35)", "h1_weight": 700, "eyebrow_upper": False,
    },
    "editorial-serif": {
        "label": "Editorial (журнальный)",
        "bg": "#0E0E0C", "panel": "#1B1A17", "primary": "#E8C37E", "accent": "#D97757",
        "fg": "#F5F1E8", "fg2": "rgba(245,241,232,.75)", "muted": "rgba(245,241,232,.5)",
        "font_family": '"Playfair Display",Georgia,serif',
        "font_url": "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@500;700;800&display=swap",
        "radius": 8, "border": "1px solid rgba(232,195,126,.25)", "shadow": "none",
        "scrim": "rgba(0,0,0,.55)", "h1_weight": 800, "eyebrow_upper": True,
    },
}

DEFAULT_STYLE = "businesspad-dark"

# Order shown in the bot's design picker
PICKER_ORDER = ["businesspad-dark", "neo-brutalism", "apple-minimal", "editorial-serif"]

PRESETS = {slug: {"title": t["label"], "description": t["label"],
                  "examples": []} for slug, t in THEMES.items()}
PRESETS["businesspad-dark"]["examples"] = [
    "projects/top-oss-week-bp/hyperframes/renders/final_businesspad.mp4",
    "projects/businesspad-features-bp/hyperframes/renders/final_businesspad.mp4",
]


def get_theme(slug_or_custom):
    """Accept a slug (from THEMES) or a ready theme dict (custom). Returns a theme dict."""
    if isinstance(slug_or_custom, dict):
        base = dict(THEMES[DEFAULT_STYLE])
        base.update(slug_or_custom)   # custom tokens override defaults
        return base
    return THEMES.get(slug_or_custom, THEMES[DEFAULT_STYLE])


def get_preset(slug):
    return PRESETS.get(slug, PRESETS[DEFAULT_STYLE])


def example_paths(slug):
    return get_preset(slug).get("examples", [])
