"""Generate rich seed data for a dense, globally-distributed map."""

import random
import uuid
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# Major wine regions with coordinates
REGIONS = [
    ("Napa Valley", 38.4, -122.4, "winery"),
    ("Sonoma County", 38.5, -122.8, "winery"),
    ("Paso Robles", 35.6, -120.7, "winery"),
    ("Santa Barbara", 34.4, -119.7, "winery"),
    ("Willamette Valley", 45.3, -123.0, "winery"),
    ("Finger Lakes", 42.5, -77.0, "winery"),
    ("Texas Hill Country", 30.3, -98.5, "winery"),
    ("Bordeaux", 44.8, -0.6, "winery"),
    ("Burgundy", 47.0, 4.7, "winery"),
    ("Champagne", 49.2, 4.0, "winery"),
    ("Rhone Valley", 44.8, 4.8, "winery"),
    ("Tuscany", 43.3, 11.3, "winery"),
    ("Piedmont", 44.7, 8.0, "winery"),
    ("Rioja", 42.5, -2.5, "winery"),
    ("Barossa Valley", -34.5, 138.9, "winery"),
    ("Marlborough", -41.5, 173.8, "winery"),
    ("Mendoza", -32.9, -68.8, "winery"),
    ("Stellenbosch", -33.9, 18.9, "winery"),
    ("Mosel", 50.0, 7.0, "winery"),
    ("Douro Valley", 41.2, -7.7, "winery"),
    ("Chile", -33.4, -70.6, "winery"),
    ("Tokyo", 35.7, 139.7, "bar"),
    ("New York", 40.7, -74.0, "bar"),
    ("London", 51.5, -0.1, "bar"),
    ("Paris", 48.9, 2.3, "restaurant"),
    ("Sydney", -33.9, 151.2, "restaurant"),
    ("Barcelona", 41.4, 2.2, "restaurant"),
    ("Melbourne", -37.8, 145.0, "restaurant"),
    ("Cape Town", -33.9, 18.4, "restaurant"),
    ("Buenos Aires", -34.6, -58.4, "restaurant"),
    ("Porto", 41.1, -8.6, "bar"),
    ("Athens", 37.9, 23.7, "restaurant"),
    ("Hong Kong", 22.3, 114.2, "bar"),
    ("Singapore", 1.3, 103.8, "bar"),
    ("Dubai", 25.2, 55.3, "bar"),
    ("Mumbai", 19.1, 72.9, "restaurant"),
    ("Bangkok", 13.8, 100.5, "bar"),
    ("Seoul", 37.6, 127.0, "bar"),
    ("Mexico City", 19.4, -99.1, "restaurant"),
]

VENUE_NAMES = {
    "winery": ["Vineyard", "Cellars", "Estate", "Winery", "Tasting Room", "Cellar Door", "Vineyard & Winery", "Family Winery", "Hillside Vineyard", "Valley Estate"],
    "restaurant": ["Bistro", "Restaurant", "Kitchen", "Grill", "Eatery", "Brasserie", "Bouchon", "Osteria", "Trattia", "Cafe"],
    "bar": ["Bar", "Lounge", "Pub", "Tavern", "Cocktail Bar", "Wine Bar", "Speakeasy", "Taproom", "Saloon", "Club"],
}

NOTES = [
    "Absolutely stunning! Will definitely have again.",
    "Great value for money. Would recommend.",
    "A pleasant surprise. Very drinkable.",
    "Complex and layered. Needs time to open up.",
    "Perfect for a casual evening.",
    "Impressive depth. One of the best I've tried.",
    "Light and refreshing. Great with food.",
    "Bold and structured. Aging potential is excellent.",
    "Elegant and refined. A real treat.",
    "Solid choice. Nothing extraordinary but very enjoyable.",
    "Amazing nose. Beautifully balanced.",
    "Too tannic for my taste but well-made.",
    "Lovely fruit-forward style. Very approachable.",
    "Outstanding! A new favorite.",
    "Decent but overpriced for what you get.",
]


def main():
    db_path = Path("data/wine.db")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Get existing wines and users
    c.execute("SELECT id FROM wines")
    wines = [r[0] for r in c.fetchall()]
    print(f"Wines available: {len(wines)}")

    c.execute("SELECT id FROM users")
    users = [r[0] for r in c.fetchall()]
    print(f"Users: {len(users)}")

    if not wines or not users:
        print("Need at least some wines and users first!")
        return

    added_locations = 0
    added_tastings = 0

    for name, lat, lon, vtype in REGIONS:
        num_venues = random.randint(2, 5)
        for i in range(num_venues):
            offset_lat = lat + random.uniform(-0.4, 0.4)
            offset_lon = lon + random.uniform(-0.4, 0.4)
            venue_name = f"{name} {random.choice(VENUE_NAMES[vtype])}"
            loc_id = uuid.uuid4().hex[:12]

            c.execute(
                "INSERT INTO locations (id, name, address, lat, lon, venue_type) VALUES (?, ?, ?, ?, ?, ?)",
                (loc_id, venue_name, f"{name}, Region", offset_lat, offset_lon, vtype)
            )
            added_locations += 1

            # Add 1-4 tastings per location
            num_tastings = random.randint(1, 4)
            for j in range(num_tastings):
                wine_id = random.choice(wines)
                user_id = random.choice(users)
                rating = random.randint(2, 5)
                note_id = uuid.uuid4().hex[:12]
                notes = random.choice(NOTES)

                c.execute(
                    """INSERT INTO tasting_notes 
                       (id, wine_id, user_id, location_id, rating, appearance, nose, palate, finish, body, sweetness, acidity, tannins, food_pairing, photo_url, notes, is_public) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                    (note_id, wine_id, user_id, loc_id, rating, 
                     "Deep color", "Fruity, oaky", "Full-bodied, smooth", "Long, pleasant",
                     "medium", "dry", "medium", "medium", "", "", notes)
                )
                added_tastings += 1

    conn.commit()

    # Verify
    c.execute("SELECT COUNT(*) FROM locations")
    print(f"\nTotal locations: {c.fetchone()[0]}")
    c.execute("SELECT COUNT(*) FROM tasting_notes")
    print(f"Total tastings: {c.fetchone()[0]}")

    # Show distribution
    c.execute("SELECT venue_type, COUNT(*) FROM locations GROUP BY venue_type")
    print(f"By type: {c.fetchall()}")

    # Show global spread
    c.execute("SELECT MIN(lat), MAX(lat), MIN(lon), MAX(lon) FROM locations")
    bounds = c.fetchone()
    print(f"Map bounds: lat {bounds[0]:.2f} to {bounds[1]:.2f}, lon {bounds[2]:.2f} to {bounds[3]:.2f}")

    conn.close()


if __name__ == "__main__":
    main()
