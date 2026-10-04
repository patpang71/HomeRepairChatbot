-- Migrate existing home_repair_db from enum Type to ComponentType table

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

-- Ensure any existing HomeComponent Type values exist in ComponentType
INSERT INTO "ComponentType" ("ComponentTypeName")
SELECT DISTINCT "Type"::text
FROM "HomeComponent"
ON CONFLICT ("ComponentTypeName") DO NOTHING;

ALTER TABLE "HomeComponent"
    ALTER COLUMN "Type" TYPE VARCHAR(100)
    USING "Type"::text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'HomeComponent_Type_fkey'
    ) THEN
        ALTER TABLE "HomeComponent"
            ADD CONSTRAINT "HomeComponent_Type_fkey"
            FOREIGN KEY ("Type") REFERENCES "ComponentType"("ComponentTypeName");
    END IF;
END $$;
