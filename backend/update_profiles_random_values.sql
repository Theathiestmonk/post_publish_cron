-- Add random day_of_week and time_bucket values to existing profiles
-- This script will update all existing users with random values

-- First, add the columns if they don't exist
ALTER TABLE public.profiles
ADD COLUMN IF NOT EXISTS day_of_week INTEGER,
ADD COLUMN IF NOT EXISTS time_bucket TEXT;

-- Update existing rows with random values
UPDATE public.profiles
SET
    day_of_week = floor(random() * 7)::int,
    time_bucket = (
        ARRAY['morning','afternoon','evening','night']
    )[floor(random() * 4 + 1)]
WHERE day_of_week IS NULL OR time_bucket IS NULL;

-- Set defaults for new rows
ALTER TABLE public.profiles
ALTER COLUMN day_of_week
SET DEFAULT floor(random() * 7)::int;

ALTER TABLE public.profiles
ALTER COLUMN time_bucket
SET DEFAULT (
    ARRAY['morning','afternoon','evening','night']
)[floor(random() * 4 + 1)];

-- Add constraints (drop if they exist first to avoid conflicts)
ALTER TABLE public.profiles
DROP CONSTRAINT IF EXISTS check_day_of_week_range;

ALTER TABLE public.profiles
ADD CONSTRAINT check_day_of_week_range
CHECK (day_of_week BETWEEN 0 AND 6);

ALTER TABLE public.profiles
DROP CONSTRAINT IF EXISTS check_time_bucket_values;

ALTER TABLE public.profiles
ADD CONSTRAINT check_time_bucket_values
CHECK (time_bucket IN ('morning','afternoon','evening','night'));
