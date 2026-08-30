"""Seed wineries into the database — curated list of notable wineries worldwide."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db, async_session
from backend.models.location import Location


FAMOUS_WINERIES = [
    # Napa Valley, CA
    {"name": "Opus One Winery", "address": "7900 St Helena Hwy, Oakville, CA 94562", "lat": 38.4372, "lon": -122.4131, "website": "https://www.opusonewinery.com", "description": "Iconic Napa Valley Bordeaux-style blend, founded by Robert Mondavi and Baron Philippe de Rothschild.", "phone": "(707) 944-9442"},
    {"name": "Robert Mondavi Winery", "address": "7801 St Helena Hwy, Oakville, CA 94562", "lat": 38.4333, "lon": -122.4167, "website": "https://www.robertmondaviwinery.com", "description": "Pioneering Napa Valley winery founded in 1966. Known for Cabernet Sauvignon and Fumé Blanc.", "phone": "(888) 766-6328"},
    {"name": "Screaming Eagle Winery", "address": "1100 Conn Creek Rd, Oakville, CA 94562", "lat": 38.4442, "lon": -122.3986, "website": "https://www.screamingeagle.com", "description": "Ultra-premium Napa Cabernet Sauvignon. One of the most sought-after wines in the world.", "phone": ""},
    {"name": "Stag's Leap Wine Cellars", "address": "5766 Silverado Trail, Napa, CA 94558", "lat": 38.4281, "lon": -122.3344, "website": "https://www.stagsleapwinecellars.com", "description": "Famous for winning the 1976 Judgment of Paris with their 1973 Cabernet Sauvignon.", "phone": "(707) 944-2020"},
    {"name": "Silver Oak Cellars", "address": "915 Oakville Cross Rd, Oakville, CA 94562", "lat": 38.4397, "lon": -122.4094, "website": "https://www.silveroak.com", "description": "Known exclusively for Cabernet Sauvignon — both Alexander Valley and Napa Valley bottlings.", "phone": "(707) 942-7022"},
    {"name": "Caymus Vineyards", "address": "8700 Conn Creek Rd, Rutherford, CA 94573", "lat": 38.4525, "lon": -122.4050, "website": "https://www.caymus.com", "description": "Famous for Napa Valley Cabernet Sauvignon. Known for rich, bold style.", "phone": "(707) 967-3010"},
    {"name": "Domaine Chandon", "address": "1 California Dr, Yountville, CA 94599", "lat": 38.3981, "lon": -122.3581, "website": "https://www.chandon.com", "description": "California outpost of Moët & Chandon. Specializes in sparkling wines and beautiful gardens.", "phone": "(707) 204-7528"},
    {"name": "Beringer Vineyards", "address": "2000 Main St, St Helena, CA 94574", "lat": 38.5058, "lon": -122.4708, "website": "https://www.beringer.com", "description": "Napa's oldest continuously operating winery, founded in 1876. Historic Rhine House.", "phone": "(707) 967-4434"},

    # Sonoma, CA
    {"name": "Kendall-Jackson", "address": "5007 Fulton Rd, Fulton, CA 95439", "lat": 38.4967, "lon": -122.7733, "website": "https://www.kj.com", "description": "One of California's largest wineries. Famous for Vintner's Reserve Chardonnay.", "phone": "(707) 544-4000"},
    {"name": "La Crema Winery", "address": "4157 Gravenstein Hwy S, Sebastopol, CA 95472", "lat": 38.3522, "lon": -122.8317, "website": "https://www.lacrema.com", "description": "Specializes in cool-climate Pinot Noir and Chardonnay from Sonoma Coast.", "phone": "(707) 431-9400"},

    # Bordeaux, France
    {"name": "Château Margaux", "address": "1 Route de l'Île Vincent, 33460 Margaux, France", "lat": 45.0406, "lon": -0.6747, "website": "https://www.chateau-margaux.com", "description": "First Growth Bordeaux estate. One of only four châteaux with Premier Grand Cru Classé status.", "phone": "+33 5 57 88 83 83"},
    {"name": "Château Haut-Brion", "address": "135 Avenue Jean Jaurès, 33600 Pessac, France", "lat": 44.8058, "lon": -0.5764, "website": "https://www.haut-brion.com", "description": "First Growth Bordeaux estate. Oldest and smallest of the five First Growths.", "phone": "+33 5 56 00 29 30"},
    {"name": "Château Lafite Rothschild", "address": "33250 Pauillac, France", "lat": 45.2419, "lon": -0.7700, "website": "https://www.lafite.com", "description": "First Growth estate in Pauillac. One of the most famous wine estates in the world.", "phone": "+33 5 56 73 18 18"},

    # Burgundy, France
    {"name": "Domaine de la Romanée-Conti", "address": "1 Rue Derrière le Four, 21700 Vosne-Romanée, France", "lat": 47.1500, "lon": 4.9667, "website": "https://www.romanee-conti.com", "description": "The most prestigious wine estate in Burgundy. Produces some of the world's most expensive wines.", "phone": ""},
    {"name": "Domaine Leflaive", "address": "Place des Marronniers, 21190 Puligny-Montrachet, France", "lat": 46.9500, "lon": 4.7500, "website": "https://www.domaine-leflaive.com", "description": "Legendary producer of white Burgundy. Grand Cru Montrachets are among the world's finest whites.", "phone": "+33 3 80 21 30 13"},

    # Champagne, France
    {"name": "Maison Veuve Clicquot", "address": "1 Place des Droits de l'Homme, 51100 Reims, France", "lat": 49.2583, "lon": 4.0331, "website": "https://www.veuveclicquot.com", "description": "Founded in 1772. Famous for Yellow Label Brut and the invention of the riddling table.", "phone": "+33 3 26 89 53 00"},
    {"name": "Dom Pérignon", "address": "4 Rue de la Brèche d'Oger, 51190 Le Mesnil-sur-Oger, France", "lat": 48.9667, "lon": 4.0333, "website": "https://www.domperignon.com", "description": "The prestige cuvée of Moët & Chandon. Vintage-only Champagne of exceptional quality.", "phone": ""},

    # Tuscany, Italy
    {"name": "Tenuta San Guido (Sassicaia)", "address": "Loc. Le Capanne, 27, 57022 Bolgheri LI, Italy", "lat": 43.2333, "lon": 10.5333, "website": "https://www.sassicaia.com", "description": "Home of Sassicaia — the Super Tuscan that put Bolgheri on the world wine map.", "phone": "+39 0565 762003"},
    {"name": "Antinori nel Chianti Classico", "address": "Via Cassia per Siena, 133, 50026 San Casciano VP, Italy", "lat": 43.6000, "lon": 11.2167, "website": "https://www.antinori.it", "description": "One of Italy's oldest and most famous wine families. Founded in 1385.", "phone": "+39 055 235 97 00"},

    # Piedmont, Italy
    {"name": "Gaja Winery", "address": "Via Torino, 5, 12050 Barbaresco CN, Italy", "lat": 44.7167, "lon": 8.0833, "website": "https://www.gaja.com", "description": "Piedmont's most famous producer. Known for Barbaresco, Barolo, and Super-Tuscan blends.", "phone": "+39 0173 635158"},

    # Barossa, Australia
    {"name": "Penfolds Magill Estate", "address": "78 Penfold Rd, Magill SA 5072, Australia", "lat": -34.9167, "lon": 138.6833, "website": "https://www.penfolds.com", "description": "Home of Penfolds Grange — Australia's most famous wine. Founded in 1844.", "phone": "+61 8 8301 5569"},

    # Marlborough, New Zealand
    {"name": "Cloudy Bay Winery", "address": "230 Jacksons Rd, Blenheim 7273, New Zealand", "lat": -41.5167, "lon": 173.9500, "website": "https://www.cloudybay.co.nz", "description": "Pioneering Marlborough producer. Famous for Sauvignon Blanc that put NZ on the world wine map.", "phone": "+64 3 520 9140"},

    # Rioja, Spain
    {"name": "Marqués de Riscal", "address": "Calle Torrea, 1, 01340 Elciego, Álava, Spain", "lat": 42.5156, "lon": -2.6222, "website": "https://www.marquesderiscal.com", "description": "Legendary Rioja producer founded in 1858. Known for Reserva and Gran Reserva. Frank Gehry-designed hotel.", "phone": "+34 945 60 60 00"},

    # Douro, Portugal
    {"name": "Symington Family Estates", "address": "Travessa Barão de Forrester, 4400-111 Vila Nova de Gaia, Portugal", "lat": 41.1333, "lon": -8.6167, "website": "https://www.symington.com", "description": "Portugal's leading Port producer. Owns Graham's, Dow's, Warre's, and Cockburn's.", "phone": "+351 223 776 600"},

    # Washington State
    {"name": "Château Ste. Michelle", "address": "14111 NE 145th St, Woodinville, WA 98072", "lat": 47.7367, "lon": -122.1500, "website": "https://www.ste-michelle.com", "description": "Washington's oldest and most acclaimed winery. Founded in 1934.", "phone": "(425) 488-1133"},
]


async def seed_wineries():
    await init_db()

    async with async_session() as session:
        # Count existing wineries
        from sqlalchemy import select, func
        result = await session.execute(
            select(func.count()).select_from(Location).where(Location.venue_type == "winery")
        )
        existing = result.scalar() or 0
        if existing > 0:
            print(f"Database already has {existing} wineries. Re-run after dropping DB to re-seed.")
            return

        created = 0
        for w in FAMOUS_WINERIES:
            location = Location(
                name=w["name"],
                address=w["address"],
                lat=w["lat"],
                lon=w["lon"],
                venue_type="winery",
                website=w.get("website", ""),
                description=w.get("description", ""),
                phone=w.get("phone", ""),
            )
            session.add(location)
            created += 1

        await session.commit()
        print(f"✅ Seeded {created} famous wineries into the database!")
        print(f"   Regions: Napa, Sonoma, Bordeaux, Burgundy, Champagne, Tuscany, Piedmont, Barossa, Marlborough, Rioja, Douro, Washington")


if __name__ == "__main__":
    asyncio.run(seed_wineries())