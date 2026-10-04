-- Home Repair Chatbot schema

CREATE TABLE IF NOT EXISTS "ComponentType" (
    "ComponentTypeId"   SERIAL PRIMARY KEY,
    "ComponentTypeName" VARCHAR(100) NOT NULL UNIQUE
);

INSERT INTO "ComponentType" ("ComponentTypeName") VALUES
    ('WATER_HEATER'),
    ('TOILET'),
    ('SHOWER'),
    ('SINK'),
    ('WATER_FACET')
ON CONFLICT ("ComponentTypeName") DO NOTHING;

CREATE TABLE IF NOT EXISTS "User" (
    "UserId"        SERIAL PRIMARY KEY,
    "Email"         VARCHAR(255) NOT NULL UNIQUE,
    "StreetAddress" VARCHAR(255),
    "City"          VARCHAR(100),
    "State"         VARCHAR(50),
    "Zip"           VARCHAR(20) NOT NULL,
    "Preference"    VARCHAR(20) NOT NULL DEFAULT 'concise'
        CHECK ("Preference" IN ('concise', 'detail'))
);

CREATE TABLE IF NOT EXISTS "HomeComponent" (
    "ComponentId"      SERIAL PRIMARY KEY,
    "UserId"           INTEGER NOT NULL REFERENCES "User"("UserId"),
    "Type"             VARCHAR(100) NOT NULL REFERENCES "ComponentType"("ComponentTypeName"),
    "ManufacturerId"   VARCHAR(255),
    "ProblemDesc"      TEXT,
    "ResolutionDetail" TEXT,
    "Resolved"         BOOLEAN NOT NULL DEFAULT FALSE,
    "TimeStamp"        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "SearchResult" (
    "SearchId"       SERIAL PRIMARY KEY,
    "ComponentId"    INTEGER NOT NULL REFERENCES "HomeComponent"("ComponentId"),
    "UserId"         INTEGER NOT NULL REFERENCES "User"("UserId"),
    "SearchQuestion" TEXT NOT NULL,
    "SearchResult"   TEXT NOT NULL,
    "TimeStamp"      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "Session" (
    "SessionId"     SERIAL PRIMARY KEY,
    "UserId"        INTEGER NOT NULL REFERENCES "User"("UserId"),
    "SessionDetail" TEXT
);

CREATE TABLE IF NOT EXISTS "ToolRecommandation" (
    "ToolKind" VARCHAR(100) PRIMARY KEY,
    "Url"      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "ToolSelected" (
    "ToolSelectedId" SERIAL PRIMARY KEY,
    "ComponentId"    INTEGER NOT NULL REFERENCES "HomeComponent"("ComponentId"),
    "UserId"         INTEGER NOT NULL REFERENCES "User"("UserId"),
    "ToolKind"       VARCHAR(100) NOT NULL,
    "Url"            TEXT NOT NULL
);

-- Mock tool catalog
INSERT INTO "ToolRecommandation" ("ToolKind", "Url") VALUES
    ('screwdriver', 'https://tools.example.com/screwdriver'),
    ('pliers', 'https://tools.example.com/pliers'),
    ('pipe wrench', 'https://tools.example.com/pipe-wrench'),
    ('pipe', 'https://tools.example.com/pipe'),
    ('wrench', 'https://tools.example.com/wrench'),
    ('hammer', 'https://tools.example.com/hammer'),
    ('plunger', 'https://tools.example.com/plunger'),
    ('tape measure', 'https://tools.example.com/tape-measure'),
    ('adjustable wrench', 'https://tools.example.com/adjustable-wrench'),
    ('channel lock pliers', 'https://tools.example.com/channel-lock-pliers'),
    ('Teflon tape', 'https://tools.example.com/teflon-tape'),
    ('putty knife', 'https://tools.example.com/putty-knife'),
    ('multimeter', 'https://tools.example.com/multimeter'),
    ('bucket', 'https://tools.example.com/bucket'),
    ('Water Heater', 'https://test.com/waterheater'),
    ('recessed light', 'https://parts.example.com/recessed-light'),
    ('recess light', 'https://parts.example.com/recessed-light'),
    ('fuse', 'https://parts.example.com/fuse'),
    ('water facet', 'https://parts.example.com/water-faucet'),
    ('water faucet', 'https://parts.example.com/water-faucet'),
    ('faucet', 'https://parts.example.com/water-faucet'),
    ('garbage disposal', 'https://parts.example.com/garbage-disposal'),
    ('shower head', 'https://parts.example.com/shower-head'),
    ('showerhead', 'https://parts.example.com/shower-head'),
    ('cartridge', 'https://parts.example.com/cartridge'),
    ('valve', 'https://parts.example.com/valve'),
    ('flapper', 'https://parts.example.com/flapper'),
    ('aerator', 'https://parts.example.com/aerator'),
    ('circuit breaker', 'https://parts.example.com/circuit-breaker'),
    ('Volt-Alert AC Non-Contact Voltage Tester', 'https://tools.example.com/volt-alert-non-contact-voltage-tester'),
    ('GFCI Outlet Tester', 'https://tools.example.com/gfci-outlet-tester'),
    ('Cable Stapler', 'https://tools.example.com/cable-stapler'),
    ('Digital Circuit Breaker Finder', 'https://tools.example.com/digital-circuit-breaker-finder'),
    ('Electricians True RMS Multimeter', 'https://tools.example.com/electricians-true-rms-multimeter'),
    ('Circuit Analyzer', 'https://tools.example.com/circuit-analyzer'),
    ('Lever-Nut Assortment Pack', 'https://tools.example.com/lever-nut-assortment-pack'),
    ('Impact Driver Kit', 'https://tools.example.com/impact-driver-kit'),
    ('Nonconductive Electrical Wire Pliers', 'https://tools.example.com/nonconductive-electrical-wire-pliers'),
    ('Wet-Dry Vacuum', 'https://tools.example.com/wet-dry-vacuum'),
    ('Digital Multimeter Electrical Test Kit', 'https://tools.example.com/digital-multimeter-electrical-test-kit'),
    ('Circuit Breaker Finder Tool Kit', 'https://tools.example.com/circuit-breaker-finder-tool-kit'),
    ('Advanced Circuit Breaker Finder and Wire Tracer Kit', 'https://tools.example.com/advanced-circuit-breaker-finder-wire-tracer-kit'),
    ('Multi Tool', 'https://tools.example.com/multi-tool'),
    ('Wire Cutter', 'https://tools.example.com/wire-cutter'),
    ('Wire Stripper', 'https://tools.example.com/wire-stripper')
ON CONFLICT ("ToolKind") DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_homecomponent_userid_ts
    ON "HomeComponent" ("UserId", "TimeStamp" DESC);

CREATE INDEX IF NOT EXISTS idx_searchresult_component
    ON "SearchResult" ("ComponentId", "TimeStamp" DESC);

CREATE INDEX IF NOT EXISTS idx_toolselected_component
    ON "ToolSelected" ("ComponentId");

CREATE INDEX IF NOT EXISTS idx_toolselected_user
    ON "ToolSelected" ("UserId");
