"""Styles for SALSA - Following official Reflex dashboard template patterns."""

import reflex as rx

# =============================================================================
# COLOR TOKENS - Theme-aware (matches dashboard template exactly)
# =============================================================================

border_radius = "var(--radius-2)"
border = f"1px solid {rx.color('gray', 5)}"
text_color = rx.color("gray", 11)
gray_color = rx.color("gray", 11)
gray_bg_color = rx.color("gray", 3)
accent_text_color = rx.color("accent", 10)
accent_color = rx.color("accent", 1)
accent_bg_color = rx.color("accent", 3)

# =============================================================================
# HOVER PATTERNS - Reusable dicts
# =============================================================================

hover_accent_color = {"_hover": {"color": accent_text_color}}
hover_accent_bg = {"_hover": {"background_color": accent_color}}

# =============================================================================
# LAYOUT CONSTANTS
# =============================================================================

sidebar_width = "20em"
sidebar_content_width = "16em"
max_width = "1480px"

# =============================================================================
# TEMPLATE STYLES - Page-level
# =============================================================================

template_page_style = {
    "padding_top": ["1em", "1em", "2em"],
    "padding_x": ["1em", "1em", "2em"],
}

template_content_style = {
    "padding": "1em",
    "margin_bottom": "2em",
    "min_height": "90vh",
}

# =============================================================================
# COMPONENT STYLES
# =============================================================================

box_shadow = "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)"

# =============================================================================
# BASE STYLES
# =============================================================================

base_stylesheets = [
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
]

base_style = {
    "font_family": "Inter",
}
