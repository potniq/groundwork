CREATE TABLE IF NOT EXISTS cities (
    id SERIAL PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    city_name TEXT NOT NULL,
    country TEXT NOT NULL,
    country_code TEXT NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    metro_area_name TEXT,
    status TEXT NOT NULL DEFAULT 'generating',
    retrieved_at TIMESTAMPTZ DEFAULT NOW(),
    stale_after TIMESTAMPTZ,
    intel JSONB,
    raw_response TEXT
);

CREATE INDEX IF NOT EXISTS idx_cities_slug ON cities(slug);
CREATE INDEX IF NOT EXISTS idx_cities_status ON cities(status);

CREATE TABLE IF NOT EXISTS city_requests (
    id SERIAL PRIMARY KEY,
    raw_input TEXT NOT NULL,
    email TEXT,
    requested_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'pending'
);

CREATE INDEX IF NOT EXISTS idx_city_requests_status ON city_requests(status);
