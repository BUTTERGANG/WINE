"""Seed script — populate DB with demo data."""

import asyncio
import sys
from pathlib import Path

# Ensure backend is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from backend.config import settings
from backend.database import Base, init_db, async_session
from backend.models.wine import Wine, TastingNote
from backend.models.location import Location
from backend.models.user import User
from backend.services.auth import hash_password


SEED_WINES = [
    {"producer": "Château Margaux", "name": "Margaux Grand Cru", "vintage": 2016, "region": "Bordeaux", "country": "France", "varietal": "Bordeaux Blend", "wine_type": "red", "abv": 13.5},
    {"producer": "Opus One", "name": "Napa Valley Red", "vintage": 2018, "region": "Napa Valley", "country": "USA", "varietal": "Bordeaux Blend", "wine_type": "red", "abv": 14.5},
    {"producer": "Domaine de la Romanée-Conti", "name": "Romanée-Conti Grand Cru", "vintage": 2015, "region": "Burgundy", "country": "France", "varietal": "Pinot Noir", "wine_type": "red", "abv": 13.0},
    {"producer": "Screaming Eagle", "name": "Cabernet Sauvignon", "vintage": 2019, "region": "Napa Valley", "country": "USA", "varietal": "Cabernet Sauvignon", "wine_type": "red", "abv": 15.0},
    {"producer": "Cloudy Bay", "name": "Sauvignon Blanc", "vintage": 2021, "region": "Marlborough", "country": "New Zealand", "varietal": "Sauvignon Blanc", "wine_type": "white", "abv": 13.0},
    {"producer": "Kendall-Jackson", "name": "Vintner's Reserve Chardonnay", "vintage": 2020, "region": "California", "country": "USA", "varietal": "Chardonnay", "wine_type": "white", "abv": 13.5},
    {"producer": "Château d'Yquem", "name": "Sauternes Grand Cru", "vintage": 2005, "region": "Bordeaux", "country": "France", "varietal": "Sémillon", "wine_type": "dessert", "abv": 14.0},
    {"producer": "Penfolds", "name": "Grange", "vintage": 2016, "region": "South Australia", "country": "Australia", "varietal": "Shiraz", "wine_type": "red", "abv": 14.5},
    {"producer": "Veuve Clicquot", "name": "Yellow Label Brut", "vintage": None, "region": "Champagne", "country": "France", "varietal": "Champagne Blend", "wine_type": "sparkling", "abv": 12.0},
    {"producer": "Silver Oak", "name": "Alexander Valley Cabernet", "vintage": 2017, "region": "Sonoma County", "country": "USA", "varietal": "Cabernet Sauvignon", "wine_type": "red", "abv": 14.0},
    {"producer": "La Crema", "name": "Monterey Pinot Noir", "vintage": 2019, "region": "Monterey", "country": "USA", "varietal": "Pinot Noir", "wine_type": "red", "abv": 13.5},
    {"producer": "Kim Crawford", "name": "Marlborough Pinot Grigio", "vintage": 2022, "region": "Marlborough", "country": "New Zealand", "varietal": "Pinot Grigio", "wine_type": "white", "abv": 12.5},
    {"producer": "NV Moët & Chandon", "name": "Brut Impérial", "vintage": None, "region": "Champagne", "country": "France", "varietal": "Champagne Blend", "wine_type": "sparkling", "abv": 12.0},
    {"producer": "Caymus Vineyards", "name": "Special Select Cabernet", "vintage": 2019, "region": "Napa Valley", "country": "USA", "varietal": "Cabernet Sauvignon", "wine_type": "red", "abv": 15.2},
    {"producer": "Santa Margherita", "name": "Valdadige Pinot Grigio", "vintage": 2021, "region": "Trentino-Alto Adige", "country": "Italy", "varietal": "Pinot Grigio", "wine_type": "white", "abv": 12.5},
    {"producer": "Beringer", "name": "Knights Valley Cabernet", "vintage": 2018, "region": "Napa Valley", "country": "USA", "varietal": "Cabernet Sauvignon", "wine_type": "red", "abv": 14.0},
    {"producer": "Château Haut-Brion", "name": "Pessac-Léognan Grand Cru", "vintage": 2014, "region": "Bordeaux", "country": "France", "varietal": "Bordeaux Blend", "wine_type": "red", "abv": 13.5},
    {"producer": "Dom Pérignon", "name": "Vintage Brut", "vintage": 2012, "region": "Champagne", "country": "France", "varietal": "Champagne Blend", "wine_type": "sparkling", "abv": 12.5},
    {"producer": "Duckhorn Vineyards", "name": "Napa Valley Merlot", "vintage": 2019, "region": "Napa Valley", "country": "USA", "varietal": "Merlot", "wine_type": "red", "abv": 14.2},
    {"producer": "Tenuta San Guido", "name": "Sassicaia Bolgheri", "vintage": 2018, "region": "Tuscany", "country": "Italy", "varietal": "Cabernet Sauvignon", "wine_type": "red", "abv": 14.0},
    {"producer": "Antinori", "name": "Tignanello Toscana", "vintage": 2019, "region": "Tuscany", "country": "Italy", "varietal": "Sangiovese Blend", "wine_type": "red", "abv": 14.0},
    {"producer": "Ridge Vineyards", "name": "Monte Bello", "vintage": 2017, "region": "Santa Cruz Mountains", "country": "USA", "varietal": "Cabernet Sauvignon", "wine_type": "red", "abv": 13.8},
    {"producer": "Provenance Vineyards", "name": "Napa Valley Rosé", "vintage": 2022, "region": "Napa Valley", "country": "USA", "varietal": "Rosé Blend", "wine_type": "rosé", "abv": 12.5},
    {"producer": "Château Lafite Rothschild", "name": "Pauillac Grand Cru", "vintage": 2016, "region": "Bordeaux", "country": "France", "varietal": "Bordeaux Blend", "wine_type": "red", "abv": 13.0},
    {"producer": "Louis Jadot", "name": "Puligny-Montrachet", "vintage": 2020, "region": "Burgundy", "country": "France", "varietal": "Chardonnay", "wine_type": "white", "abv": 13.0},
    {"producer": "Mondavi", "name": "Reserve Cabernet", "vintage": 2017, "region": "Napa Valley", "country": "USA", "varietal": "Cabernet Sauvignon", "wine_type": "red", "abv": 14.2},
    {"producer": "Torres", "name": "Mas La Plana", "vintage": 2018, "region": "Penedès", "country": "Spain", "varietal": "Cabernet Sauvignon", "wine_type": "red", "abv": 14.0},
    {"producer": "Gaja", "name": "Barbaresco DOCG", "vintage": 2016, "region": "Piedmont", "country": "Italy", "varietal": "Nebbiolo", "wine_type": "red", "abv": 14.0},
    {"producer": "Stag's Leap Wine Cellars", "name": "Cask 23 Cabernet", "vintage": 2018, "region": "Napa Valley", "country": "USA", "varietal": "Cabernet Sauvignon", "wine_type": "red", "abv": 14.5},
    {"producer": "Harlan Estate", "name": "Napa Valley Red", "vintage": 2016, "region": "Napa Valley", "country": "USA", "varietal": "Bordeaux Blend", "wine_type": "red", "abv": 15.0},
]

SEED_VENUES = [
    {"name": "The French Laundry", "address": "6640 Washington St, Yountville, CA 94599", "lat": 38.4033, "lon": -122.3622, "venue_type": "restaurant"},
    {"name": "Robert Mondavi Winery", "address": "7801 St Helena Hwy, Oakville, CA 94562", "lat": 38.4333, "lon": -122.4167, "venue_type": "winery"},
    {"name": "Bouchon Bistro", "address": "6534 Washington St, Yountville, CA 94599", "lat": 38.4019, "lon": -122.3661, "venue_type": "restaurant"},
    {"name": "Domaine de la Romanée-Conti", "address": "1 Rue Derrière le Four, 21700 Vosne-Romanée, France", "lat": 47.1500, "lon": 4.9667, "venue_type": "winery"},
    {"name": "Rutherford Grill", "address": "1180 Rutherford Rd, Rutherford, CA 94573", "lat": 38.4564, "lon": -122.4169, "venue_type": "restaurant"},
    {"name": "Opus One Winery", "address": "7900 St Helena Hwy, Oakville, CA 94562", "lat": 38.4372, "lon": -122.4131, "venue_type": "winery"},
    {"name": "The Bar at The Ritz", "address": "15 Piccadilly, London W1J 7DG, UK", "lat": 51.5074, "lon": -0.1427, "venue_type": "bar"},
    {"name": "Home Cellar", "address": "123 Oak Lane, Napa, CA 94558", "lat": 38.3082, "lon": -122.2974, "venue_type": "home"},
]

SEED_USERS = [
    {"username": "wine_lover", "email": "wine@example.com", "display_name": "Alex", "bio": "Exploring wines one glass at a time 🍷"},
    {"username": "sommelier_sam", "email": "sam@example.com", "display_name": "Sam", "bio": "Certified sommelier. Pinot Noir is life."},
    {"username": "cabernet_queen", "email": "queen@example.com", "display_name": "Jordan", "bio": "Napa Cab or bust."},
    {"username": "sparkling_steve", "email": "steve@example.com", "display_name": "Steve", "bio": "Life's too short for still wine."},
    {"username": "demo_taster", "email": "demo@example.com", "display_name": "Demo", "bio": "Just getting started!"},
]

NOTES_TEMPLATES = [
    {"rating": 5, "appearance": "Deep ruby, dense core", "nose": "Blackcurrant, cedar, tobacco, dark chocolate", "palate": "Full-bodied, velvety tannins, complex layers", "finish": "Extremely long, 60+ seconds", "notes": "Wine of a lifetime. Decanted 2 hours. Perfect now but will age beautifully.", "body": "full", "sweetness": "dry", "acidity": "medium", "tannins": "high"},
    {"rating": 4, "appearance": "Medium garnet", "nose": "Cherry, strawberry, earthy undertones, slight oak", "palate": "Medium-bodied, silky tannins, balanced acidity", "finish": "Long, elegant", "notes": "Beautifully balanced. Paired with roasted duck — magic.", "body": "medium", "sweetness": "dry", "acidity": "medium", "tannins": "medium"},
    {"rating": 4, "appearance": "Straw yellow, bright", "nose": "Citrus, green apple, wet stone, grass", "palate": "Crisp, zesty, mineral-driven", "finish": "Clean, refreshing", "notes": "Perfect summer afternoon wine. Great with oysters.", "body": "light", "sweetness": "dry", "acidity": "high", "tannins": ""},
    {"rating": 3, "appearance": "Pale gold", "nose": "Apple, pear, vanilla, butter", "palate": "Medium-bodied, buttery, smooth", "finish": "Medium, creamy", "notes": "Solid California Chard. Not complex but crowd-pleasing.", "body": "medium", "sweetness": "dry", "acidity": "medium", "tannins": ""},
    {"rating": 5, "appearance": "Pale pink, salmon hue", "nose": "Strawberry, watermelon, white flowers", "palate": "Light, crisp, bone dry", "finish": "Clean, short", "notes": "Provence in a glass. The perfect rosé for brunch.", "body": "light", "sweetness": "dry", "acidity": "high", "tannins": ""},
    {"rating": 4, "appearance": "Bright gold, fine bubbles", "nose": "Brioche, lemon zest, almond, green apple", "palate": "Creamy mousse, vibrant acidity, citrus", "finish": "Elegant, persistent", "notes": "Celebratory bottle. Always delivers.", "body": "light", "sweetness": "off-dry", "acidity": "high", "tannins": ""},
    {"rating": 3, "appearance": "Deep ruby", "nose": "Blackberry, vanilla, mocha, spice", "palate": "Rich, bold, sweet tannins", "finish": "Long, warm", "notes": "Big, bold Napa Cab. A bit too extracted for my taste but well made.", "body": "full", "sweetness": "dry", "acidity": "low", "tannins": "high"},
    {"rating": 4, "appearance": "Pale gold", "nose": "Apricot, honey, citrus blossom, ginger", "palate": "Luscious, rich, perfectly balanced sweetness", "finish": "Endless", "notes": "Dessert perfection. Pairs beautifully with blue cheese.", "body": "full", "sweetness": "sweet", "acidity": "high", "tannins": ""},
    {"rating": 5, "appearance": "Garnet with orange rim", "nose": "Dried cherry, rose petal, truffle, leather", "palate": "Ethereal, silky, profound depth", "finish": "Transcendent", "notes": "This is why Burgundy exists. Mind-blowing complexity.", "body": "medium", "sweetness": "dry", "acidity": "high", "tannins": "medium"},
    {"rating": 2, "appearance": "Medium ruby", "nose": "Jammy fruit, vanilla, alcohol", "palate": "Over-extracted, hot finish, flabby", "finish": "Short, harsh", "notes": "Disappointing for the price. Too much alcohol without structure.", "body": "full", "sweetness": "dry", "acidity": "low", "tannins": "medium"},
]


async def seed():
    await init_db()
    
    async with async_session() as session:
        # Check if already seeded
        result = await session.execute(sa.select(sa.func.count()).select_from(Wine))
        count = result.scalar() or 0
        if count > 0:
            print(f"Database already has {count} wines. Skipping seed (delete data/wine.db to re-seed).")
            return

        # Create users
        users = {}
        for u in SEED_USERS:
            user = User(
                username=u["username"],
                email=u["email"],
                password_hash=hash_password("password"),
                display_name=u["display_name"],
                bio=u["bio"],
            )
            session.add(user)
            await session.flush()
            users[u["username"]] = user
        print(f"✅ Created {len(users)} users")

        # Create wines
        wines = []
        for w in SEED_WINES:
            wine = Wine(**w)
            session.add(wine)
            wines.append(wine)
        await session.flush()
        print(f"✅ Created {len(wines)} wines")

        # Create venues
        venues = []
        for v in SEED_VENUES:
            venue = Location(**v)
            session.add(venue)
            venues.append(venue)
        await session.flush()
        print(f"✅ Created {len(venues)} venues")

        # Create tasting notes
        import random
        notes_count = 0
        for i, note_data in enumerate(NOTES_TEMPLATES):
            user_key = list(users.keys())[i % len(users)]
            wine = wines[i % len(wines)]
            venue = venues[i % len(venues)]
            
            note = TastingNote(
                wine_id=wine.id,
                user_id=users[user_key].id,
                location_id=venue.id,
                rating=note_data["rating"],
                appearance=note_data["appearance"],
                nose=note_data["nose"],
                palate=note_data["palate"],
                finish=note_data["finish"],
                notes=note_data["notes"],
                body=note_data["body"],
                sweetness=note_data["sweetness"],
                acidity=note_data["acidity"],
                tannins=note_data["tannins"],
                food_pairing=random.choice(["Grilled steak", "Roasted chicken", "Oysters", "Cheese plate", "Dark chocolate", ""]),
                is_public=True,
            )
            session.add(note)
            notes_count += 1

        # Add a few more random notes
        for i in range(10):
            user_key = random.choice(list(users.keys()))
            wine = random.choice(wines)
            venue = random.choice(venues)
            rating = random.randint(2, 5)
            note = TastingNote(
                wine_id=wine.id,
                user_id=users[user_key].id,
                location_id=venue.id,
                rating=rating,
                notes=f"Just tried this at {venue.name}. {'Loved it!' if rating >= 4 else 'Solid.' if rating == 3 else 'Not my favorite.'}",
                is_public=True,
            )
            session.add(note)
            notes_count += 1

        await session.commit()
        print(f"✅ Created {notes_count} tasting notes")
        print("\n🎉 Seed complete!")
        print(f"   Users: {len(SEED_USERS)} (password: password)")
        print(f"   Wines: {len(SEED_WINES)}")
        print(f"   Venues: {len(SEED_VENUES)}")
        print(f"   Tasting Notes: {notes_count}")


if __name__ == "__main__":
    asyncio.run(seed())