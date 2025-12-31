-- Add usage tracking fields to profiles table
-- Monthly counters that reset based on subscription start date

ALTER TABLE profiles ADD COLUMN IF NOT EXISTS current_month_start DATE DEFAULT CURRENT_DATE;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS tasks_completed_this_month INTEGER DEFAULT 0;
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS images_generated_this_month INTEGER DEFAULT 0;

-- Function to get the current month's start date based on subscription
CREATE OR REPLACE FUNCTION get_current_month_start(user_id UUID)
RETURNS DATE AS $$
DECLARE
    subscription_start DATE;
    current_date DATE := CURRENT_DATE;
    months_diff INTEGER;
BEGIN
    -- Get subscription start date
    SELECT DATE(subscription_start_date) INTO subscription_start
    FROM profiles
    WHERE id = user_id;

    -- If no subscription start date, use current month start
    IF subscription_start IS NULL THEN
        RETURN DATE_TRUNC('month', current_date)::DATE;
    END IF;

    -- Calculate months since subscription started
    months_diff := EXTRACT(YEAR FROM AGE(current_date, subscription_start)) * 12 +
                   EXTRACT(MONTH FROM AGE(current_date, subscription_start));

    -- Return the start date for current month based on subscription
    RETURN subscription_start + INTERVAL '1 month' * months_diff;
END;
$$ LANGUAGE plpgsql;

-- Function to reset monthly counters if month has changed
CREATE OR REPLACE FUNCTION reset_monthly_counters_if_needed(user_id UUID)
RETURNS void AS $$
DECLARE
    calculated_month_start DATE;
    stored_month_start DATE;
BEGIN
    -- Get current month start based on subscription
    calculated_month_start := get_current_month_start(user_id);

    -- Get stored month start
    SELECT current_month_start INTO stored_month_start
    FROM profiles
    WHERE id = user_id;

    -- Reset counters if month has changed
    IF stored_month_start IS NULL OR stored_month_start != calculated_month_start THEN
        UPDATE profiles
        SET
            current_month_start = calculated_month_start,
            tasks_completed_this_month = 0,
            images_generated_this_month = 0
        WHERE id = user_id;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Function to increment task completed count
CREATE OR REPLACE FUNCTION increment_task_count(user_id UUID)
RETURNS INTEGER AS $$
DECLARE
    new_count INTEGER;
BEGIN
    -- Reset counters if month changed
    PERFORM reset_monthly_counters_if_needed(user_id);

    -- Increment task count
    UPDATE profiles
    SET tasks_completed_this_month = tasks_completed_this_month + 1
    WHERE id = user_id
    RETURNING tasks_completed_this_month INTO new_count;

    RETURN new_count;
END;
$$ LANGUAGE plpgsql;

-- Function to increment image generated count
CREATE OR REPLACE FUNCTION increment_image_count(user_id UUID)
RETURNS INTEGER AS $$
DECLARE
    new_count INTEGER;
BEGIN
    -- Reset counters if month changed
    PERFORM reset_monthly_counters_if_needed(user_id);

    -- Increment image count
    UPDATE profiles
    SET images_generated_this_month = images_generated_this_month + 1
    WHERE id = user_id
    RETURNING images_generated_this_month INTO new_count;

    RETURN new_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get current usage counts
CREATE OR REPLACE FUNCTION get_usage_counts(user_id UUID)
RETURNS TABLE(tasks_count INTEGER, images_count INTEGER) AS $$
BEGIN
    -- Reset counters if month changed
    PERFORM reset_monthly_counters_if_needed(user_id);

    RETURN QUERY
    SELECT
        tasks_completed_this_month,
        images_generated_this_month
    FROM profiles
    WHERE id = user_id;
END;
$$ LANGUAGE plpgsql;

-- Add comments for documentation
COMMENT ON COLUMN profiles.current_month_start IS 'Start date of current usage month based on subscription';
COMMENT ON COLUMN profiles.tasks_completed_this_month IS 'Number of tasks completed this month';
COMMENT ON COLUMN profiles.images_generated_this_month IS 'Number of images generated this month';

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_profiles_current_month_start ON profiles(current_month_start);
CREATE INDEX IF NOT EXISTS idx_profiles_tasks_completed ON profiles(tasks_completed_this_month);
CREATE INDEX IF NOT EXISTS idx_profiles_images_generated ON profiles(images_generated_this_month);
