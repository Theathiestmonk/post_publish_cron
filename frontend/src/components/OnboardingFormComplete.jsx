import React, { useState, useEffect } from 'react'
import { onboardingAPI } from '../services/onboarding'
import { ArrowLeft, ArrowRight, Check, X } from 'lucide-react'

const OnboardingForm = ({ 
  initialData = null, 
  isEditMode = false, 
  onClose = null, 
  onSuccess = null,
  showHeader = true,
  showProgress = true 
}) => {
  const [currentStep, setCurrentStep] = useState(0)
  const [formData, setFormData] = useState({
    business_name: '',
    business_type: [],
    industry: [],
    business_description: '',
    target_audience: [],
    unique_value_proposition: '',
    brand_voice: '',
    brand_tone: '',
    website_url: '',
    phone_number: '',
    street_address: '',
    city: '',
    state: '',
    country: '',
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || '',
    social_media_platforms: [],
    primary_goals: [],
    key_metrics_to_track: [],
    monthly_budget_range: '',
    preferred_content_types: [],
    content_themes: [],
    main_competitors: '',
    market_position: '',
    products_or_services: '',
    important_launch_dates: '',
    planned_promotions_or_campaigns: '',
    top_performing_content_types: [],
    best_time_to_post: [],
    successful_campaigns: '',
    hashtags_that_work_well: '',
    customer_pain_points: '',
    typical_customer_journey: '',
    automation_level: '',
    platform_specific_tone: {},
    current_presence: [],
    focus_areas: [],
    platform_details: {},
    facebook_page_name: '',
    instagram_profile_link: '',
    linkedin_company_link: '',
    youtube_channel_link: '',
    x_twitter_profile: '',
    google_business_profile: '',
    google_ads_account: '',
    whatsapp_business: '',
    email_marketing_platform: '',
    // New fields for comprehensive onboarding
    target_audience_age_groups: [],
    target_audience_life_stages: [],
    target_audience_professional_types: [],
    target_audience_lifestyle_interests: [],
    target_audience_buyer_behavior: [],
    platform_tone_instagram: [],
    platform_tone_facebook: [],
    platform_tone_linkedin: [],
    platform_tone_youtube: [],
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  
  // State for "Other" input fields
  const [otherInputs, setOtherInputs] = useState({
    businessTypeOther: '',
    industryOther: '',
    socialPlatformOther: '',
    goalOther: '',
    metricOther: '',
    contentTypeOther: '',
    contentThemeOther: '',
    postingTimeOther: '',
    currentPresenceOther: '',
    topPerformingContentTypeOther: ''
  })

  // State for expandable cards
  const [expandedCards, setExpandedCards] = useState({
    ageGroups: false,
    lifeStages: false,
    professionalTypes: false,
    lifestyleInterests: false,
    buyerBehavior: false
  })

  // Load initial data if provided
  useEffect(() => {
    if (initialData) {
      setFormData(prev => ({
        ...prev,
        ...initialData
      }))
    }
  }, [initialData])

  const steps = [
    'Basic Business Info',
    'Business Description', 
    'Brand & Contact',
    'Current Presence & Focus Areas',
    'Digital Marketing & Goals',
    'Content Strategy',
    'Market & Competition',
    'Campaign Planning',
    'Performance & Customer',
    'Automation & Platform',
    'Review & Submit'
  ]

  const businessTypes = [
    'B2B', 'B2C', 'E-Commerce', 'SaaS', 'Restaurant', 
    'Service-based', 'Franchise', 'Marketplace', 'D2C', 'Other'
  ]

  const industries = [
    'Technology/IT', 'Retail/E-commerce', 'Education/eLearning', 'Healthcare/Wellness', 
    'Fashion/Apparel', 'Food & Beverage', 'Travel & Hospitality', 'Finance/Fintech/Insurance', 
    'Construction/Infrastructure', 'Automobile/Mobility', 'Media/Entertainment/Creators', 
    'Real Estate', 'Logistics/Supply Chain', 'Manufacturing/Industrial', 'Professional Services', 
    'Non-Profit/NGO/Social Enterprise', 'Others'
  ]

  const socialPlatforms = [
    'Instagram', 'Facebook', 'LinkedIn', 'YouTube', 'Google'
  ]

  const goals = [
    'Increase Sales', 'Brand Awareness', 'Website Traffic', 'Lead Generation', 
    'Community Building', 'Customer Engagement', 'Other'
  ]

  const metrics = [
    'Followers', 'Likes', 'Clicks', 'Engagement Rate', 'Leads', 'Shares', 
    'Comments', 'Conversions', 'Website Traffic/Visitors', 'Not sure — let Emily decide', 'Other'
  ]

  const budgetRanges = [
    '₹0–₹5,000', '₹5,000–₹10,000', '₹10,000–₹25,000', 
    '₹25,000–₹50,000', '₹50,000+'
  ]


  const contentTypes = [
    'Image Posts', 'Reels', 'Carousels', 'Stories', 'Blogs', 'Videos', 
    'Live Sessions', 'Other'
  ]

  const contentThemes = [
    'Product Features', 'Behind the Scenes', 'Customer Stories', 'Tips & Tricks', 
    'Educational', 'Announcements', 'User-Generated Content', 'Inspirational', 
    'Entertaining', 'Not sure', 'Others'
  ]

  const postingTimes = [
    'Early Morning (6 AM – 9 AM)', 'Mid-Morning (9 AM – 12 PM)', 'Afternoon (12 PM – 3 PM)', 
    'Late Afternoon (3 PM – 6 PM)', 'Evening (6 PM – 9 PM)', 'Late Night (9 PM – 12 AM)', 
    'Weekdays', 'Weekends', 'Not sure — let Emily analyze and suggest', 'Other'
  ]

  const marketPositions = [
    { value: 'Niche Brand', label: 'Niche Brand', description: 'Focused on a specific target audience' },
    { value: 'Challenger Brand', label: 'Challenger Brand', description: 'Competing against bigger or more known players' },
    { value: 'Market Leader', label: 'Market Leader', description: 'Top brand in your category or region' },
    { value: 'New Entrant/Startup', label: 'New Entrant / Startup', description: 'Launched within the last 1-2 years' },
    { value: 'Established Business', label: 'Established Business', description: 'Steady brand with moderate presence' },
    { value: 'Disruptor/Innovator', label: 'Disruptor / Innovator', description: 'Bringing something new or different to the market' },
    { value: 'Local Business', label: 'Local Business', description: 'Serving a city or region' },
    { value: 'Online-Only Business', label: 'Online-Only Business', description: 'No physical presence' },
    { value: 'Franchise/Multi-location Business', label: 'Franchise / Multi-location Business', description: 'Multiple locations or franchise model' },
    { value: 'Not Sure — Need Help Positioning', label: 'Not Sure — Need Help Positioning', description: 'Need assistance determining market position' }
  ]

  const brandVoices = [
    'Professional', 'Conversational', 'Friendly', 'Bold', 'Playful', 
    'Approachable/Trustworthy', 'Sophisticated/Elegant', 'Quirky/Offbeat', 
    'Confident', 'Not sure yet'
  ]

  const brandTones = [
    'Formal', 'Informal', 'Humorous', 'Inspirational', 'Empathetic', 
    'Encouraging', 'Direct', 'Flexible'
  ]

  const timezones = [
    'Asia/Kolkata', 'Asia/Dubai', 'Asia/Shanghai', 'Asia/Tokyo', 'Asia/Singapore', 
    'Europe/London', 'Europe/Paris', 'Europe/Berlin', 'America/New_York', 
    'America/Los_Angeles', 'America/Chicago', 'America/Toronto', 
    'Australia/Sydney', 'Australia/Melbourne', 'Pacific/Auckland'
  ]

  const automationLevels = [
    { 
      value: 'Full Automation – I want Emily to do everything', 
      label: 'Full Automation', 
      description: 'I want Emily to do everything automatically' 
    },
    { 
      value: 'Suggestions Only – I will take action manually', 
      label: 'Suggestions Only', 
      description: 'I will take action manually based on Emily\'s suggestions' 
    },
    { 
      value: 'Manual Approval Before Posting', 
      label: 'Manual Approval', 
      description: 'Emily creates content but I approve before posting' 
    },
    { 
      value: 'Hybrid (platform/content-based mix – specify later)', 
      label: 'Hybrid Approach', 
      description: 'Mix of automation and manual control (platform/content-based)' 
    },
    { 
      value: 'Not sure – need help deciding', 
      label: 'Not Sure', 
      description: 'Need help deciding the best automation level' 
    }
  ]

  const currentPresenceOptions = [
    'Website', 'Facebook Page', 'Instagram', 'LinkedIn', 'X (formerly Twitter)', 
    'YouTube', 'WhatsApp Business', 'Google Business Profile', 'Google Ads', 
    'Meta Ads (Facebook/Instagram)', 'Email Marketing Platform', 'Other'
  ]

  const focusAreas = [
    'SEO', 'Blog/Article Writing', 'Website Optimization/Copywriting', 
    'Social Media Marketing (Organic Growth)', 'Paid Advertising', 
    'Email Marketing & Campaigns', 'YouTube/Video Marketing', 'Influencer Marketing', 
    'PPC', 'Lead Generation Campaigns', 'Brand Awareness', 'Local SEO/Maps Presence', 
    'Customer Retargeting', 'Not Sure – Let Emily suggest the best path'
  ]

  const targetAudienceCategories = {
    ageGroups: [
      'Teens (13–19)', 'College Students/Youth (18–24)', 'Young Professionals (25–35)', 
      'Working Adults (30–50)', 'Seniors/Retirees (60+)', 'Kids/Children (0–12)'
    ],
    lifeStages: [
      'Students', 'Parents/Families', 'Newlyweds/Couples', 'Homeowners/Renters', 'Retired Individuals'
    ],
    professionalTypes: [
      'Business Owners/Entrepreneurs', 'Corporate Clients/B2B Buyers', 'Freelancers/Creators', 
      'Government Employees', 'Educators/Trainers', 'Job Seekers/Career Switchers', 'Writers and Journalists'
    ],
    lifestyleInterests: [
      'Fitness Enthusiasts', 'Outdoor/Adventure Lovers', 'Fashion/Beauty Conscious', 
      'Health-Conscious/Wellness Seekers', 'Pet Owners', 'Tech Enthusiasts/Gamers', 'Travelers/Digital Nomads'
    ],
    buyerBehavior: [
      'Premium Buyers/High-Income Consumers', 'Budget-Conscious Shoppers', 'Impulse Buyers', 
      'Ethical/Sustainable Shoppers', 'Frequent Online Buyers'
    ]
  }

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }))
    setError('')
  }

  const handleArrayChange = (field, value, checked) => {
    setFormData(prev => ({
      ...prev,
      [field]: checked 
        ? [...prev[field], value]
        : prev[field].filter(item => item !== value)
    }))
  }

  const handleOtherInputChange = (field, value) => {
    setOtherInputs(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const toggleCard = (cardName) => {
    setExpandedCards(prev => ({
      ...prev,
      [cardName]: !prev[cardName]
    }))
  }

  const getSelectedCount = (field) => {
    return formData[field].length
  }

  const validateCurrentStep = () => {
    switch (currentStep) {
      case 0: // Basic Business Info
        return formData.business_name && formData.business_type.length > 0 && formData.industry.length > 0
      case 1: // Business Description
        return formData.business_description && formData.unique_value_proposition &&
               (formData.target_audience_age_groups.length > 0 || 
                formData.target_audience_life_stages.length > 0 || 
                formData.target_audience_professional_types.length > 0 || 
                formData.target_audience_lifestyle_interests.length > 0 || 
                formData.target_audience_buyer_behavior.length > 0)
      case 2: // Brand & Contact
        return formData.brand_voice && formData.brand_tone && formData.phone_number && 
               formData.street_address && formData.city && formData.state && formData.country
      case 3: // Current Presence & Focus Areas
        // If Website is selected, website_url is required
        if (formData.current_presence.includes('Website') && !formData.website_url) {
          return false;
        }
        return true
      case 4: // Digital Marketing & Goals
        return formData.social_media_platforms.length > 0 && formData.primary_goals.length > 0 && 
               formData.key_metrics_to_track.length > 0
      case 5: // Content Strategy
        return formData.preferred_content_types.length > 0 && formData.content_themes.length > 0
      case 6: // Market & Competition
        return formData.market_position && formData.products_or_services
      case 7: // Campaign Planning
        return formData.top_performing_content_types.length > 0 && formData.best_time_to_post.length > 0
      case 8: // Performance & Customer
        return formData.successful_campaigns && formData.hashtags_that_work_well && 
               formData.customer_pain_points && formData.typical_customer_journey
      case 9: // Automation & Platform
        return formData.automation_level
      case 10: // Review & Submit
        return true // Review step
      default:
        return true
    }
  }

  const nextStep = () => {
    if (validateCurrentStep()) {
      setCurrentStep(prev => Math.min(prev + 1, steps.length - 1))
      setError('')
    } else {
      setError('Please fill in all required fields before proceeding.')
    }
  }

  const prevStep = () => {
    setCurrentStep(prev => Math.max(prev - 1, 0))
    setError('')
  }

  const handleSubmit = async () => {
    setIsSubmitting(true)
    setError('')

    try {
      // Prepare the data for submission
      const submissionData = {
        ...formData,
        // Populate the general target_audience field with all selected target audience details
        target_audience: [
          ...formData.target_audience_age_groups,
          ...formData.target_audience_life_stages,
          ...formData.target_audience_professional_types,
          ...formData.target_audience_lifestyle_interests,
          ...formData.target_audience_buyer_behavior
        ].filter(Boolean), // Remove any empty values
        
        // Include all "Other" input fields
        business_type_other: otherInputs.businessTypeOther,
        industry_other: otherInputs.industryOther,
        social_platform_other: otherInputs.socialPlatformOther,
        goal_other: otherInputs.goalOther,
        metric_other: otherInputs.metricOther,
        content_type_other: otherInputs.contentTypeOther,
        content_theme_other: otherInputs.contentThemeOther,
        posting_time_other: otherInputs.postingTimeOther,
        current_presence_other: otherInputs.currentPresenceOther,
        top_performing_content_type_other: otherInputs.topPerformingContentTypeOther
      }

      if (isEditMode) {
        // Update existing profile
        await onboardingAPI.updateProfile(submissionData)
        if (onSuccess) onSuccess()
      } else {
        // Create new profile
        await onboardingAPI.submitOnboarding(submissionData)
        if (onSuccess) onSuccess()
      }
    } catch (err) {
      setError(err.message || 'Failed to save profile')
    } finally {
      setIsSubmitting(false)
    }
  }

  // This is a placeholder - I'll need to copy the complete renderStep function from the original Onboarding component
  const renderStep = () => {
    // For now, return a simple message indicating this needs to be completed
    return (
      <div className="text-center py-8">
        <p className="text-gray-600">Step {currentStep + 1} - {steps[currentStep]}</p>
        <p className="text-sm text-gray-500 mt-2">This step needs to be implemented with the complete form fields.</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-lg p-8">
      {/* Header */}
      {showHeader && (
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-semibold text-gray-800">
              {isEditMode ? 'Edit Profile' : 'Complete Your Profile'}
            </h2>
            <p className="text-gray-600">
              {isEditMode ? 'Update your business information' : 'Let\'s get to know your business better'}
            </p>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <X className="w-5 h-5 text-gray-500" />
            </button>
          )}
        </div>
      )}

      {/* Progress Bar */}
      {showProgress && (
        <div className="mb-8">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">
              Step {currentStep + 1} of {steps.length}
            </span>
            <span className="text-sm text-gray-500">
              {Math.round(((currentStep + 1) / steps.length) * 100)}% Complete
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div 
              className="bg-gradient-to-r from-pink-500 to-purple-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }}
            ></div>
          </div>
        </div>
      )}

      {/* Step Content */}
      <div className="mb-6">
        <h3 className="text-xl font-semibold text-gray-800 mb-2">
          {steps[currentStep]}
        </h3>
        <p className="text-gray-600">
          {currentStep === 0 && "Tell us about your business basics"}
          {currentStep === 1 && "Help us understand what you do"}
          {currentStep === 2 && "How should we represent your brand?"}
          {currentStep === 3 && "What are your social media goals?"}
          {currentStep === 4 && "What's your content strategy?"}
          {currentStep === 5 && "How do you fit in the market?"}
          {currentStep === 6 && "What campaigns are you planning?"}
          {currentStep === 7 && "What's worked well for you?"}
          {currentStep === 8 && "How automated should your marketing be?"}
          {currentStep === 9 && "Review everything before we start"}
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      {renderStep()}

      {/* Navigation */}
      <div className="flex justify-between">
        <button
          onClick={prevStep}
          disabled={currentStep === 0}
          className="flex items-center px-6 py-3 bg-gray-500 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-600 transition-colors"
        >
          <ArrowLeft className="w-4 h-4 mr-2" />
          Previous
        </button>

        {currentStep === steps.length - 1 ? (
          <button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="flex items-center px-6 py-3 bg-gradient-to-r from-pink-500 to-purple-600 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:from-pink-600 hover:to-purple-700 transition-all"
          >
            {isSubmitting ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                {isEditMode ? 'Updating...' : 'Submitting...'}
              </>
            ) : (
              <>
                <Check className="w-4 h-4 mr-2" />
                {isEditMode ? 'Update Profile' : 'Complete Onboarding'}
              </>
            )}
          </button>
        ) : (
          <button
            onClick={nextStep}
            className="flex items-center px-6 py-3 bg-gradient-to-r from-pink-500 to-purple-600 text-white rounded-lg hover:from-pink-600 hover:to-purple-700 transition-all"
          >
            Next
            <ArrowRight className="w-4 h-4 ml-2" />
          </button>
        )}
      </div>
    </div>
  )
}

export default OnboardingForm
