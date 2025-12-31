-- Migration: Add channel column to created_content table
-- Date: 2025-12-24
-- Description: Add channel field to created_content table and set default value for existing records

-- Step 1: Add channel column to created_content table
ALTER TABLE created_content
ADD COLUMN IF NOT EXISTS channel VARCHAR(50);

-- Step 2: Set default value for all existing records
UPDATE created_content
SET channel = 'Social Media'
WHERE channel IS NULL;

-- Step 3: Set NOT NULL constraint after updating existing records
ALTER TABLE created_content
ALTER COLUMN channel SET NOT NULL;

-- Step 4: Set default value for future inserts
ALTER TABLE created_content
ALTER COLUMN channel SET DEFAULT 'Social Media';

-- Step 5: Add check constraint to ensure valid channel values
ALTER TABLE created_content
ADD CONSTRAINT check_channel_values 
CHECK (channel IN ('Social Media', 'Blog', 'Email', 'Messages'));

-- Verification query (run this to verify the migration)
-- SELECT channel, COUNT(*) as count 
-- FROM created_content 
-- GROUP BY channel;







