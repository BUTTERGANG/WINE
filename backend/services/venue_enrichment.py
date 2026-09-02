"""Venue enrichment service — fetch rich business data from Google Places API."""

import json
import logging
from datetime import datetime
from typing import Optional

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

GOOGLE_PLACES_BASE = "https://places.googleapis.com/v1"
GOOGLE_MAPS_BASE = "https://maps.googleapis.com/maps/api"


async def enrich_venue_from_google(
    name: str,
    lat: float,
    lon: float,
    venue_type: str = "restaurant",
) -> Optional[dict]:
    """
    Fetch rich business data from Google Places API.
    
    Returns dict with: website, phone, address, hours, rating, review_count,
    photos, menu_url, price_level, amenities, description
    """
    api_key = settings.google_maps_api_key
    if not api_key:
        logger.debug("No Google Maps API key configured, skipping enrichment")
        return None

    try:
        # 1. Search for the place by name and location
        place_id = await _search_place(api_key, name, lat, lon, venue_type)
        if not place_id:
            return None

        # 2. Get detailed place info
        details = await _get_place_details(api_key, place_id)
        if not details:
            return None

        # 3. Parse and return structured data
        return _parse_place_details(details)

    except Exception as e:
        logger.warning(f"Failed to enrich venue '{name}': {e}")
        return None


async def _search_place(
    api_key: str,
    name: str,
    lat: float,
    lon: float,
    venue_type: str,
) -> Optional[str]:
    """Search for a place by name near coordinates."""
    type_map = {
        "winery": "winery",
        "restaurant": "restaurant",
        "bar": "bar",
        "shop": "store",
        "home": "establishment",
        "other": "establishment",
    }
    place_type = type_map.get(venue_type, "establishment")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{GOOGLE_PLACES_BASE}/places:searchText",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.id,places.displayName,places.location",
            },
            json={
                "textQuery": f"{name} {place_type}",
                "maxResultCount": 3,
                "locationBias": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lon},
                        "radius": 5000.0,
                    }
                },
            },
        )

        if resp.status_code != 200:
            logger.debug(f"Place search failed: {resp.status_code}")
            return None

        data = resp.json()
        places = data.get("places", [])
        if not places:
            return None

        # Return the first (best) match
        return places[0].get("id")


async def _get_place_details(api_key: str, place_id: str) -> Optional[dict]:
    """Get detailed information about a place."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{GOOGLE_PLACES_BASE}/places/{place_id}",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": (
                    "id,displayName,formattedAddress,location,types,"
                    "rating,userRatingCount,regularOpeningHours,"
                    "internationalPhoneNumber,websiteUri,priceLevel,"
                    "reviews,photos,editorialSummary,regularOpeningHours.weekdayDescriptions"
                ),
            },
        )

        if resp.status_code != 200:
            logger.debug(f"Place details failed: {resp.status_code}")
            return None

        return resp.json()


def _parse_place_details(details: dict) -> dict:
    """Parse Google Places API response into structured data."""
    result = {
        "google_place_id": details.get("id", ""),
        "name": details.get("displayName", {}).get("text", ""),
        "address": details.get("formattedAddress", ""),
        "phone": details.get("internationalPhoneNumber", ""),
        "website": details.get("websiteUri", ""),
        "google_rating": details.get("rating"),
        "google_review_count": details.get("userRatingCount", 0),
        "price_level": _parse_price_level(details.get("priceLevel", "")),
        "description": details.get("editorialSummary", ""),
        "photo_urls": [],
        "hours": {},
        "menu_url": "",
        "amenities": [],
    }

    # Parse photos
    photos = details.get("photos", [])
    for photo in photos[:10]:  # Limit to 10 photos
        photo_name = photo.get("name", "")
        if photo_name:
            result["photo_urls"].append(
                f"{GOOGLE_PLACES_BASE}/{photo_name}/media"
                f"?maxWidthPx=800&key={settings.google_maps_api_key}"
            )

    # Parse hours
    hours_data = details.get("regularOpeningHours", {})
    if hours_data:
        weekday_descriptions = hours_data.get("weekdayDescriptions", [])
        if weekday_descriptions:
            days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
            for i, desc in enumerate(weekday_descriptions):
                if i < len(days):
                    result["hours"][days[i]] = desc

    # Parse reviews for amenities hints
    reviews = details.get("reviews", [])
    review_texts = [r.get("text", {}).get("text", "") for r in reviews[:5]]
    result["review_preview"] = review_texts[0] if review_texts else ""

    # Parse types as amenities
    types = details.get("types", [])
    type_labels = {
        "restaurant": "Restaurant",
        "bar": "Bar",
        "cafe": "Cafe",
        "winery": "Winery",
        "liquor_store": "Liquor Store",
        "meal_takeaway": "Takeaway",
        "meal_delivery": "Delivery",
        "night_club": "Night Club",
        "hotel": "Hotel",
        "lodging": "Lodging",
        "tourist_attraction": "Tourist Attraction",
        "point_of_interest": "Point of Interest",
        "establishment": "Establishment",
        "food": "Food",
        "store": "Store",
        "parking": "Parking",
        "wheelchair_accessible_entrance": "Wheelchair Accessible",
        "outdoor_seating": "Outdoor Seating",
        "reservable": "Reservable",
        "serves_beer": "Serves Beer",
        "serves_wine": "Serves Wine",
        "serves_breakfast": "Serves Breakfast",
        "serves_brunch": "Serves Brunch",
        "serves_lunch": "Serves Lunch",
        "serves_dinner": "Serves Dinner",
        "dine_in": "Dine In",
        "takeout": "Takeout",
        "delivery": "Delivery",
        "good_for_children": "Good for Children",
        "groups": "Good for Groups",
        "live_music": "Live Music",
        "music": "Music",
    }
    result["amenities"] = [type_labels.get(t, t.replace("_", " ").title()) for t in types if t in type_labels]

    return result


def _parse_price_level(price_level_str: str) -> Optional[int]:
    """Convert Google price level string to integer."""
    mapping = {
        "PRICE_LEVEL_FREE": 0,
        "PRICE_LEVEL_INEXPENSIVE": 1,
        "PRICE_LEVEL_MODERATE": 2,
        "PRICE_LEVEL_EXPENSIVE": 3,
        "PRICE_LEVEL_VERY_EXPENSIVE": 4,
    }
    return mapping.get(price_level_str)


async def enrich_venue(venue) -> bool:
    """
    Enrich a venue object with data from Google Places.
    Returns True if enrichment was successful.
    """
    data = await enrich_venue_from_google(
        name=venue.name,
        lat=venue.lat,
        lon=venue.lon,
        venue_type=venue.venue_type,
    )

    if not data:
        return False

    # Update venue fields
    venue.website = data.get("website") or venue.website
    venue.phone = data.get("phone") or venue.phone
    venue.address = data.get("address") or venue.address
    venue.google_rating = data.get("google_rating")
    venue.google_review_count = data.get("google_review_count", 0)
    venue.google_place_id = data.get("google_place_id", "")
    venue.price_level = data.get("price_level")
    venue.description = data.get("description") or venue.description
    venue.menu_url = data.get("menu_url", "")
    venue.enriched_at = datetime.utcnow()

    # JSON fields
    photo_urls = data.get("photo_urls", [])
    if photo_urls:
        venue.photo_urls = json.dumps(photo_urls)
        venue.image_url = photo_urls[0]  # First photo as primary

    hours = data.get("hours", {})
    if hours:
        venue.hours = json.dumps(hours)

    amenities = data.get("amenities", [])
    if amenities:
        venue.amenities = json.dumps(amenities)

    return True
