"""Design-style presets. One bot = one style. Each maps to a builder + example render."""

# slug -> metadata. The builder for every style currently routes through the
# businesspad-dark composer in render.py (add more composers as styles grow).
PRESETS = {
    "businesspad-dark": {
        "title": "BusinessPad Dark",
        "description": "Тёмный фирменный стиль BusinessPad: Manrope, #7C88FC/#FF8562, карточки, стат-пилюли.",
        # examples shown via «Смотреть примеры» (paths relative to OpenMontage dir)
        "examples": [
            "projects/top-oss-week-bp/hyperframes/renders/final_businesspad.mp4",
            "projects/businesspad-features-bp/hyperframes/renders/final_businesspad.mp4",
        ],
    },
}

DEFAULT_STYLE = "businesspad-dark"


def get_preset(slug):
    return PRESETS.get(slug, PRESETS[DEFAULT_STYLE])


def example_paths(slug):
    return get_preset(slug).get("examples", [])
