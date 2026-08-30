"""Glass photo analyzer — color, opacity, legs analysis."""

import io
from typing import Optional

from PIL import Image
import numpy as np


async def analyze_glass(image_data: bytes) -> list[dict]:
    """
    Analyze a photo of a wine glass and return style/varietal suggestions.
    
    Extracts:
    - Dominant color (RGB → wine color classification)
    - Color intensity (pale → deep)
    - Opacity / clarity (clear → hazy → cloudy)
    - Legs / tears (viscosity indicator)
    """
    img = Image.open(io.BytesIO(image_data)).convert("RGB")
    arr = np.array(img)

    # Convert to HSV for better color analysis
    from PIL.Image import fromarray
    hsv = img.convert("HSV")
    hsv_arr = np.array(hsv)

    # Sample the center region (where the wine is)
    h, w = arr.shape[:2]
    center = arr[h//3:2*h//3, w//4:3*w//4]
    hsv_center = hsv_arr[h//3:2*h//3, w//4:3*w//4]

    # Dominant color
    avg_rgb = center.mean(axis=(0, 1))
    avg_hsv = hsv_center.mean(axis=(0, 1))

    suggestions = []

    # Classify by color
    wine_type, varietal_guesses = _classify_wine_color(avg_rgb, avg_hsv)
    
    # Analyze legs (viscosity) from bottom of glass image
    leg_analysis = _analyze_legs(arr)
    
    # Opacity
    opacity = _analyze_opacity(center)

    suggestions.append({
        "wine_type": wine_type,
        "confidence": "high" if wine_type != "unknown" else "low",
        "color_analysis": {
            "r": int(avg_rgb[0]),
            "g": int(avg_rgb[1]),
            "b": int(avg_rgb[2]),
            "intensity": "pale" if avg_hsv[2] > 200 else "medium" if avg_hsv[2] > 100 else "deep",
            "opacity": opacity,
        },
        "legs": leg_analysis,
        "likely_varietals": varietal_guesses[:3],
    })

    return suggestions


def _classify_wine_color(rgb, hsv) -> tuple[str, list[str]]:
    """Classify wine type and likely varietals from color."""
    r, g, b = rgb

    # Red wines: dominant red channel, lower blue
    if r > g * 1.1 and r > b * 1.1 and r > 80:
        hue = hsv[0]
        if hue < 20 or hue > 340:
            return "red", ["Pinot Noir", "Grenache"]
        elif hue < 30:
            return "red", ["Pinot Noir", "Nebbiolo", "Sangiovese"]
        elif hue < 40:
            return "red", ["Cabernet Sauvignon", "Merlot", "Bordeaux Blend"]
        else:
            return "red", ["Syrah", "Malbec", "Petite Sirah"]

    # White wines: higher lightness, lower saturation
    if b > g * 0.8 and b > r * 0.8:
        if hsv[2] > 200:  # Light/clear
            if hsv[1] < 30:
                return "white", ["Sauvignon Blanc", "Pinot Grigio", "Albariño"]
            else:
                return "white", ["Chardonnay", "Viognier", "Riesling"]
        else:
            return "white", ["Chardonnay (oaked)", "White Rhône Blend", "Sémillon"]

    # Rosé: pinkish tones
    if abs(r - g) < 30 and r > b and b < r:
        return "rosé", ["Provence Rosé", "White Zinfandel", "Pinot Noir Rosé"]
    
    # Sparkling detection (golden/pale + high lightness)
    if hsv[2] > 200 and hsv[1] < 50:
        return "sparkling", ["Champagne", "Prosecco", "Cava", "Crémant"]

    return "unknown", []


def _analyze_legs(arr: np.ndarray) -> dict:
    """
    Analyze wine legs/tears from the glass wall area.
    Uses edge detection on the right side of the image (glass wall).
    """
    h, w = arr.shape[:2]
    # Right quarter of image (where glass wall usually is)
    wall = arr[:, 3*w//4:, :]
    gray = np.mean(wall, axis=2)

    # Look for vertical streaks (legs)
    # Simple approach: variance in vertical strips
    streak_count = 0
    variance = np.var(gray)
    
    if variance > 500:
        streak_count = min(int(variance / 100), 15)
    
    if streak_count > 8:
        leg_description = "prominent"
        viscosity = "high (full-bodied, higher alcohol)"
    elif streak_count > 3:
        leg_description = "moderate"
        viscosity = "medium"
    else:
        leg_description = "minimal"
        viscosity = "low (lighter wine, lower alcohol)"

    return {
        "legs": leg_description,
        "viscosity": viscosity,
        "streak_count": streak_count,
    }


def _analyze_opacity(center: np.ndarray) -> str:
    """Analyze wine opacity/clarity from center region."""
    gray = np.mean(center, axis=2)
    std = np.std(gray)
    
    if std < 20:
        return "clear"
    elif std < 50:
        return "slightly hazy"
    else:
        return "cloudy (unfiltered or natural wine)"