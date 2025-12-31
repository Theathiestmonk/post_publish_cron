-- Enhanced Content Creation Agent Tables with AI Image Support
-- Run this after the main schema.sql

-- Content Campaigns Table
CREATE TABLE IF NOT EXISTS content_campaigns (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    campaign_name TEXT NOT NULL,
    week_start_date DATE NOT NULL,
    week_end_date DATE NOT NULL,
    status TEXT DEFAULT 'draft', -- draft, generating, completed, failed
    total_posts INTEGER DEFAULT 0,
    generated_posts INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Content Posts Table
CREATE TABLE IF NOT EXISTS content_posts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    campaign_id UUID REFERENCES content_campaigns(id) ON DELETE CASCADE,
    platform TEXT NOT NULL, -- facebook, instagram, linkedin, etc.
    post_type TEXT NOT NULL, -- text, image, video, carousel, story, etc.
    title TEXT,
    content TEXT NOT NULL,
    hashtags TEXT[],
    scheduled_date DATE NOT NULL,
    scheduled_time TIME NOT NULL,
    status TEXT DEFAULT 'draft', -- draft, scheduled, published, failed
    metadata JSONB, -- platform-specific data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- AI Generated Images Table
CREATE TABLE IF NOT EXISTS content_images (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    post_id UUID REFERENCES content_posts(id) ON DELETE CASCADE,
    image_url TEXT NOT NULL, -- URL to the generated image
    image_prompt TEXT NOT NULL, -- Prompt used to generate the image
    image_style TEXT, -- artistic, realistic, cartoon, etc.
    image_size TEXT DEFAULT '1024x1024', -- 1024x1024, 512x512, etc.
    image_quality TEXT DEFAULT 'standard', -- standard, hd
    generation_model TEXT DEFAULT 'dall-e-3', -- dall-e-3, midjourney, etc.
    generation_cost DECIMAL(10,4), -- Cost of generation
    generation_time INTEGER, -- Time taken in seconds
    is_approved BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Content Templates Table
CREATE TABLE IF NOT EXISTS content_templates (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    platform TEXT NOT NULL,
    content_type TEXT NOT NULL, -- text, image, video, carousel, story
    template_name TEXT NOT NULL,
    template_prompt TEXT NOT NULL,
    image_prompt_template TEXT, -- Template for image generation
    image_style TEXT, -- Default image style for this template
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Image Generation Requests Table
CREATE TABLE IF NOT EXISTS image_generation_requests (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    post_id UUID REFERENCES content_posts(id) ON DELETE CASCADE,
    prompt TEXT NOT NULL,
    style TEXT,
    size TEXT DEFAULT '1024x1024',
    model TEXT DEFAULT 'dall-e-3',
    status TEXT DEFAULT 'pending', -- pending, generating, completed, failed
    image_url TEXT,
    error_message TEXT,
    cost DECIMAL(10,4),
    generation_time INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- User Image Preferences Table
CREATE TABLE IF NOT EXISTS user_image_preferences (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,
    preferred_style TEXT DEFAULT 'realistic', -- realistic, artistic, cartoon, minimalist
    brand_colors TEXT[], -- Array of hex color codes
    avoid_content TEXT[], -- Content to avoid in images
    preferred_subjects TEXT[], -- Preferred subjects for images
    image_quality TEXT DEFAULT 'standard', -- standard, hd
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Content Generation Progress Table
CREATE TABLE IF NOT EXISTS content_generation_progress (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES content_campaigns(id) ON DELETE CASCADE,
    current_step TEXT NOT NULL, -- initializing, loading_profile, generating_content, etc.
    progress_percentage INTEGER DEFAULT 0, -- 0-100
    step_details TEXT, -- Detailed description of current step
    total_platforms INTEGER DEFAULT 0,
    completed_platforms INTEGER DEFAULT 0,
    current_platform TEXT,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE content_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_images ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE image_generation_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_image_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_generation_progress ENABLE ROW LEVEL SECURITY;

-- RLS Policies for content_campaigns
CREATE POLICY "Users can view own campaigns" ON content_campaigns
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own campaigns" ON content_campaigns
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own campaigns" ON content_campaigns
    FOR UPDATE USING (auth.uid() = user_id);

-- RLS Policies for content_posts
CREATE POLICY "Users can view own posts" ON content_posts
    FOR SELECT USING (auth.uid() = (SELECT user_id FROM content_campaigns WHERE id = campaign_id));

CREATE POLICY "Users can insert own posts" ON content_posts
    FOR INSERT WITH CHECK (auth.uid() = (SELECT user_id FROM content_campaigns WHERE id = campaign_id));

CREATE POLICY "Users can update own posts" ON content_posts
    FOR UPDATE USING (auth.uid() = (SELECT user_id FROM content_campaigns WHERE id = campaign_id));

-- RLS Policies for content_images
CREATE POLICY "Users can view own images" ON content_images
    FOR SELECT USING (auth.uid() = (SELECT user_id FROM content_campaigns WHERE id = (SELECT campaign_id FROM content_posts WHERE id = post_id)));

CREATE POLICY "Users can insert own images" ON content_images
    FOR INSERT WITH CHECK (auth.uid() = (SELECT user_id FROM content_campaigns WHERE id = (SELECT campaign_id FROM content_posts WHERE id = post_id)));

CREATE POLICY "Users can update own images" ON content_images
    FOR UPDATE USING (auth.uid() = (SELECT user_id FROM content_campaigns WHERE id = (SELECT campaign_id FROM content_posts WHERE id = post_id)));

-- RLS Policies for image_generation_requests
CREATE POLICY "Users can view own image requests" ON image_generation_requests
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own image requests" ON image_generation_requests
    FOR INSERT WITH CHECK (auth.uid() = user_id);

-- RLS Policies for user_image_preferences
CREATE POLICY "Users can view own image preferences" ON user_image_preferences
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own image preferences" ON user_image_preferences
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own image preferences" ON user_image_preferences
    FOR UPDATE USING (auth.uid() = user_id);

-- RLS Policies for content_generation_progress
CREATE POLICY "Users can view own progress" ON content_generation_progress
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own progress" ON content_generation_progress
    FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own progress" ON content_generation_progress
    FOR UPDATE USING (auth.uid() = user_id);

-- Templates are public (read-only for users)
CREATE POLICY "Anyone can view templates" ON content_templates
    FOR SELECT USING (is_active = true);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_content_campaigns_user_id ON content_campaigns(user_id);
CREATE INDEX IF NOT EXISTS idx_content_posts_campaign_id ON content_posts(campaign_id);
CREATE INDEX IF NOT EXISTS idx_content_posts_platform ON content_posts(platform);
CREATE INDEX IF NOT EXISTS idx_content_images_post_id ON content_images(post_id);
CREATE INDEX IF NOT EXISTS idx_image_generation_requests_user_id ON image_generation_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_image_generation_requests_status ON image_generation_requests(status);

-- Insert default content templates
INSERT INTO content_templates (platform, content_type, template_name, template_prompt, image_prompt_template, image_style) VALUES
('facebook', 'text', 'Educational Post', 'Create an educational post about {topic} for {business_name}. Keep it engaging and informative, suitable for Facebook audience. Include relevant hashtags.', 'Professional illustration of {topic} in {brand_colors}, clean and modern style', 'realistic'),
('instagram', 'image', 'Behind the Scenes', 'Create a behind-the-scenes post for {business_name} showing {activity}. Make it personal and authentic for Instagram audience.', 'Behind the scenes photo of {activity} at {business_name}, natural lighting, candid moment', 'photographic'),
('linkedin', 'text', 'Industry Insight', 'Write a professional industry insight post for {business_name} about {topic}. Make it thought-provoking and suitable for LinkedIn professionals.', 'Professional infographic about {topic}, corporate style, {brand_colors}', 'realistic'),
('twitter', 'text', 'Quick Tip', 'Create a quick tip tweet for {business_name} about {topic}. Keep it concise and actionable for Twitter audience.', 'Simple illustration of {topic} tip, minimalist design', 'minimalist');

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_content_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_content_campaigns_updated_at 
    BEFORE UPDATE ON content_campaigns 
    FOR EACH ROW 
    EXECUTE FUNCTION update_content_updated_at_column();

CREATE TRIGGER update_content_posts_updated_at 
    BEFORE UPDATE ON content_posts 
    FOR EACH ROW 
    EXECUTE FUNCTION update_content_updated_at_column();

CREATE TRIGGER update_user_image_preferences_updated_at 
    BEFORE UPDATE ON user_image_preferences 
    FOR EACH ROW 
    EXECUTE FUNCTION update_content_updated_at_column();

-- Storage Buckets for AI Generated Images
-- Create storage buckets for different types of content
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES 
    ('ai-generated-images', 'ai-generated-images', true, 10485760, ARRAY['image/jpeg', 'image/png', 'image/webp']),
    ('content-templates', 'content-templates', true, 5242880, ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/gif']),
    ('user-uploads', 'user-uploads', true, 10485760, ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/gif', 'video/mp4', 'video/webm'])
ON CONFLICT (id) DO NOTHING;

-- Storage Policies for ai-generated-images bucket
CREATE POLICY "Users can view AI generated images" ON storage.objects
    FOR SELECT USING (bucket_id = 'ai-generated-images' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can upload AI generated images" ON storage.objects
    FOR INSERT WITH CHECK (bucket_id = 'ai-generated-images' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can update own AI generated images" ON storage.objects
    FOR UPDATE USING (bucket_id = 'ai-generated-images' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can delete own AI generated images" ON storage.objects
    FOR DELETE USING (bucket_id = 'ai-generated-images' AND auth.uid()::text = (storage.foldername(name))[1]);

-- Storage Policies for content-templates bucket (public read)
CREATE POLICY "Anyone can view content templates" ON storage.objects
    FOR SELECT USING (bucket_id = 'content-templates');

CREATE POLICY "Authenticated users can upload content templates" ON storage.objects
    FOR INSERT WITH CHECK (bucket_id = 'content-templates' AND auth.role() = 'authenticated');

-- Storage Policies for user-uploads bucket
CREATE POLICY "Users can view own uploads" ON storage.objects
    FOR SELECT USING (bucket_id = 'user-uploads' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can upload to own folder" ON storage.objects
    FOR INSERT WITH CHECK (bucket_id = 'user-uploads' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can update own uploads" ON storage.objects
    FOR UPDATE USING (bucket_id = 'user-uploads' AND auth.uid()::text = (storage.foldername(name))[1]);

CREATE POLICY "Users can delete own uploads" ON storage.objects
    FOR DELETE USING (bucket_id = 'user-uploads' AND auth.uid()::text = (storage.foldername(name))[1]);
