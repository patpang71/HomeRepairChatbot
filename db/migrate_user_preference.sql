-- Add User.Preference (concise | detail). Safe to re-run.

ALTER TABLE "User"
    ADD COLUMN IF NOT EXISTS "Preference" VARCHAR(20);

UPDATE "User"
SET "Preference" = 'concise'
WHERE "Preference" IS NULL OR TRIM("Preference") = '';

ALTER TABLE "User"
    ALTER COLUMN "Preference" SET DEFAULT 'concise';

ALTER TABLE "User"
    ALTER COLUMN "Preference" SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'user_preference_check'
    ) THEN
        ALTER TABLE "User"
            ADD CONSTRAINT user_preference_check
            CHECK ("Preference" IN ('concise', 'detail'));
    END IF;
END $$;
