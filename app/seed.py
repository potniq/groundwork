from fastapi import HTTPException

from app.db import SessionLocal
from app.main import create_city_profile
from app.models import CreateCityRequest

CITIES = [
    {"city_name": "London", "country": "United Kingdom", "country_code": "GB", "latitude": 51.5074, "longitude": -0.1278, "slug": "london-gb"},
    {"city_name": "Barcelona", "country": "Spain", "country_code": "ES", "latitude": 41.3874, "longitude": 2.1686, "slug": "barcelona-es"},
    {"city_name": "Tokyo", "country": "Japan", "country_code": "JP", "latitude": 35.6762, "longitude": 139.6503, "slug": "tokyo-jp"},
    {"city_name": "Dubai", "country": "United Arab Emirates", "country_code": "AE", "latitude": 25.2048, "longitude": 55.2708, "slug": "dubai-ae"},
    {"city_name": "New York", "country": "United States", "country_code": "US", "latitude": 40.7128, "longitude": -74.0060, "slug": "new-york-us"},
    {"city_name": "Singapore", "country": "Singapore", "country_code": "SG", "latitude": 1.3521, "longitude": 103.8198, "slug": "singapore-sg"},
    {"city_name": "Paris", "country": "France", "country_code": "FR", "latitude": 48.8566, "longitude": 2.3522, "slug": "paris-fr"},
    {"city_name": "Berlin", "country": "Germany", "country_code": "DE", "latitude": 52.5200, "longitude": 13.4050, "slug": "berlin-de"},
    {"city_name": "Amsterdam", "country": "Netherlands", "country_code": "NL", "latitude": 52.3676, "longitude": 4.9041, "slug": "amsterdam-nl"},
    {"city_name": "Hong Kong", "country": "Hong Kong", "country_code": "HK", "latitude": 22.3193, "longitude": 114.1694, "slug": "hong-kong-hk"},
    {"city_name": "Sydney", "country": "Australia", "country_code": "AU", "latitude": -33.8688, "longitude": 151.2093, "slug": "sydney-au"},
    {"city_name": "San Francisco", "country": "United States", "country_code": "US", "latitude": 37.7749, "longitude": -122.4194, "slug": "san-francisco-us"},
    {"city_name": "Los Angeles", "country": "United States", "country_code": "US", "latitude": 34.0522, "longitude": -118.2437, "slug": "los-angeles-us"},
    {"city_name": "Chicago", "country": "United States", "country_code": "US", "latitude": 41.8781, "longitude": -87.6298, "slug": "chicago-us"},
    {"city_name": "Toronto", "country": "Canada", "country_code": "CA", "latitude": 43.6532, "longitude": -79.3832, "slug": "toronto-ca"},
    {"city_name": "Seoul", "country": "South Korea", "country_code": "KR", "latitude": 37.5665, "longitude": 126.9780, "slug": "seoul-kr"},
    {"city_name": "Shanghai", "country": "China", "country_code": "CN", "latitude": 31.2304, "longitude": 121.4737, "slug": "shanghai-cn"},
    {"city_name": "Bangkok", "country": "Thailand", "country_code": "TH", "latitude": 13.7563, "longitude": 100.5018, "slug": "bangkok-th"},
    {"city_name": "Mumbai", "country": "India", "country_code": "IN", "latitude": 19.0760, "longitude": 72.8777, "slug": "mumbai-in"},
    {"city_name": "Istanbul", "country": "Turkey", "country_code": "TR", "latitude": 41.0082, "longitude": 28.9784, "slug": "istanbul-tr"},
    {"city_name": "Rome", "country": "Italy", "country_code": "IT", "latitude": 41.9028, "longitude": 12.4964, "slug": "rome-it"},
    {"city_name": "Milan", "country": "Italy", "country_code": "IT", "latitude": 45.4642, "longitude": 9.1900, "slug": "milan-it"},
    {"city_name": "Vienna", "country": "Austria", "country_code": "AT", "latitude": 48.2082, "longitude": 16.3738, "slug": "vienna-at"},
    {"city_name": "Zurich", "country": "Switzerland", "country_code": "CH", "latitude": 47.3769, "longitude": 8.5417, "slug": "zurich-ch"},
    {"city_name": "Dublin", "country": "Ireland", "country_code": "IE", "latitude": 53.3498, "longitude": -6.2603, "slug": "dublin-ie"},
    {"city_name": "Stockholm", "country": "Sweden", "country_code": "SE", "latitude": 59.3293, "longitude": 18.0686, "slug": "stockholm-se"},
    {"city_name": "Copenhagen", "country": "Denmark", "country_code": "DK", "latitude": 55.6761, "longitude": 12.5683, "slug": "copenhagen-dk"},
    {"city_name": "Lisbon", "country": "Portugal", "country_code": "PT", "latitude": 38.7223, "longitude": -9.1393, "slug": "lisbon-pt"},
    {"city_name": "São Paulo", "country": "Brazil", "country_code": "BR", "latitude": -23.5558, "longitude": -46.6396, "slug": "sao-paulo-br"},
    {"city_name": "Mexico City", "country": "Mexico", "country_code": "MX", "latitude": 19.4326, "longitude": -99.1332, "slug": "mexico-city-mx"},
]


def main() -> None:
    db = SessionLocal()
    try:
        created = 0
        skipped = 0
        failed = 0

        for city in CITIES:
            try:
                create_city_profile(db, CreateCityRequest(**city))
                created += 1
                print(f"Created: {city['city_name']}")
            except HTTPException as exc:
                if exc.status_code == 409:
                    skipped += 1
                    print(f"Skipped (already exists): {city['city_name']}")
                else:
                    failed += 1
                    print(f"Failed ({city['city_name']}): {exc.detail}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"Failed ({city['city_name']}): {exc}")

        print(f"Seed complete. created={created} skipped={skipped} failed={failed}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
