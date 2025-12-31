# GPT-4 Usage Report

This document lists all locations where GPT-4 (the expensive model) is being used in the codebase.

## Summary
- **Total GPT-4 Usage**: 41,013 tokens ($1.533720) across 42 requests
- **Most Expensive Model**: GPT-4 is ~10x more expensive than GPT-4o-mini

## Usage Locations

### 1. Content Generation & Editing

#### `backend/routers/content.py`
- **Line 1023**: `ai_edit_content()` endpoint
  - **Feature**: AI content editing
  - **Model**: `gpt-4`
  - **Purpose**: Edit user-provided content
  - **Max Tokens**: 2000

#### `backend/agents/content_creation_agent.py`
- **Line 612**: `generate_single_post()` method
  - **Feature**: Content generation
  - **Model**: `gpt-4`
  - **Purpose**: Generate social media posts for campaigns
  - **Max Tokens**: Platform-specific (varies by platform)

### 2. Blog Writing

#### `backend/agents/blog_writing_agent.py`
- **Line 462**: Blog content generation
  - **Feature**: Blog generation
  - **Model**: `gpt-4`
  - **Purpose**: Generate blog post content
  - **Max Tokens**: 3000

#### `backend/routers/blogs.py`
- **Line 1522**: `generate_tags_categories()` endpoint
  - **Feature**: Blog generation
  - **Model**: `gpt-4`
  - **Purpose**: Generate tags and categories for blog content
  - **Max Tokens**: 500

- **Line 1708**: `check_tags_categories_relevance()` endpoint
  - **Feature**: Blog generation
  - **Model**: `gpt-4`
  - **Purpose**: Check relevance of tags and categories
  - **Max Tokens**: 500

- **Line 2075**: Another blog-related endpoint
  - **Feature**: Blog generation
  - **Model**: `gpt-4`
  - **Purpose**: Blog content processing
  - **Max Tokens**: Varies

### 3. Custom Content Creation

#### `backend/agents/custom_content_agent.py`
- **Line 1208**: `generate_script()` method
  - **Feature**: Custom content
  - **Model**: `gpt-4`
  - **Purpose**: Generate video scripts for Instagram Reels/short-form content
  - **Max Tokens**: 2000

### 4. Ads Creation

#### `backend/agents/ads_creation_agent.py`
- **Line 303**: `_generate_ad_copy()` method
  - **Feature**: Ads creation
  - **Model**: `gpt-4`
  - **Purpose**: Generate ad copy for marketing campaigns
  - **Max Tokens**: 2000

### 5. Lead Management

#### `backend/routers/leads.py`
- **Line 625**: `create_lead()` endpoint - Email generation
  - **Feature**: Lead email generation
  - **Model**: `gpt-4`
  - **Purpose**: Generate personalized emails for leads
  - **Max Tokens**: 600

- **Line 1175**: Bulk email generation
  - **Feature**: Lead email generation
  - **Model**: `gpt-4`
  - **Purpose**: Generate emails for multiple leads
  - **Max Tokens**: 600

- **Line 1960**: Another lead-related endpoint
  - **Feature**: Lead email generation
  - **Model**: `gpt-4`
  - **Purpose**: Lead management functionality
  - **Max Tokens**: Varies

#### `backend/agents/lead_management_agent.py`
- **Line 250**: Lead processing
  - **Feature**: Lead email generation
  - **Model**: `gpt-4`
  - **Purpose**: Process and manage leads
  - **Max Tokens**: Varies

- **Line 500**: Lead analysis
  - **Feature**: Lead email generation
  - **Model**: `gpt-4`
  - **Purpose**: Analyze lead data
  - **Max Tokens**: Varies

- **Line 693**: Lead email generation
  - **Feature**: Lead email generation
  - **Model**: `gpt-4`
  - **Purpose**: Generate emails for leads
  - **Max Tokens**: Varies

### 6. Template Editing

#### `backend/agents/template_editor_agent.py`
- **Line 1047**: Content generation for templates
  - **Feature**: Template editing
  - **Model**: `gpt-4`
  - **Purpose**: Generate content for template placeholders
  - **Max Tokens**: 300

- **Line 1075**: Content validation
  - **Feature**: Template editing
  - **Model**: `gpt-4`
  - **Purpose**: Validate spelling and grammar of generated content
  - **Max Tokens**: 200

- **Line 1554**: Template processing
  - **Feature**: Template editing
  - **Model**: `gpt-4`
  - **Purpose**: Process template content
  - **Max Tokens**: Varies

## Cost Optimization Recommendations

### High Priority (Most Usage)
1. **Content Generation** (`content_creation_agent.py`, `blog_writing_agent.py`)
   - Consider switching to `gpt-4o-mini` for initial drafts
   - Use `gpt-4` only for final polish/editing

2. **Blog Writing** (`blog_writing_agent.py`, `routers/blogs.py`)
   - Tags/categories generation can use `gpt-4o-mini` (simpler task)
   - Main blog content can use `gpt-4o` instead of `gpt-4`

### Medium Priority
3. **Lead Email Generation** (`routers/leads.py`, `lead_management_agent.py`)
   - Email generation is relatively simple - consider `gpt-4o-mini` or `gpt-4o`

4. **Ads Creation** (`ads_creation_agent.py`)
   - Consider `gpt-4o` for ad copy generation

### Lower Priority (Less Frequent)
5. **Template Editing** (`template_editor_agent.py`)
   - Content validation can use `gpt-4o-mini`
   - Content generation can use `gpt-4o`

6. **Custom Content** (`custom_content_agent.py`)
   - Script generation can use `gpt-4o` instead of `gpt-4`

## Cost Comparison

| Model | Input Price/1M | Output Price/1M | Relative Cost |
|-------|---------------|-----------------|---------------|
| gpt-4 | $30.00 | $60.00 | 100% (baseline) |
| gpt-4o | $2.50 | $10.00 | ~8-17% |
| gpt-4o-mini | $0.15 | $0.60 | ~0.5-1% |

**Potential Savings**: Switching from GPT-4 to GPT-4o-mini could save ~99% on costs, or ~95% switching to GPT-4o.

## Notes

- GPT-4 is the most expensive model and should be used sparingly
- GPT-4o provides similar quality at ~10x lower cost
- GPT-4o-mini is suitable for simpler tasks and is ~200x cheaper
- Consider using GPT-4 only for tasks requiring the highest quality output



