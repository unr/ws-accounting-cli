"""Accessible financial themes — blue/orange semantic pairing."""

from textual.theme import Theme

financial_dark = Theme(
    name="financial-dark",
    primary="#4FC3F7",
    secondary="#81D4FA",
    accent="#FFB74D",
    success="#4FC3F7",       # Blue (not green) — income/positive
    error="#FF8A65",         # Orange (not red) — expenses/negative
    warning="#FFB74D",
    background="#1A1A2E",
    surface="#16213E",
    panel="#1F2F4E",
    foreground="#E0E0E0",
    dark=True,
)

financial_light = Theme(
    name="financial-light",
    primary="#0277BD",
    secondary="#0288D1",
    accent="#F57C00",
    success="#0277BD",
    error="#E65100",
    warning="#F57F17",
    background="#FAFAFA",
    surface="#FFFFFF",
    panel="#F5F5F5",
    foreground="#212121",
    dark=False,
)

ALL_THEMES = [financial_dark, financial_light]
