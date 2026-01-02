import React, { useState, useEffect, forwardRef, useImperativeHandle } from 'react'
import { onboardingAPI } from '../services/onboarding'
import { ArrowLeft, ArrowRight, Check, X, Save } from 'lucide-react'
import LogoUpload from './LogoUpload'
import MediaUpload from './MediaUpload'
import MultiMediaUpload from './MultiMediaUpload'
import InfoTooltip from './InfoTooltip'
import DualRangeSlider from './DualRangeSlider'

const OnboardingForm = forwardRef(({ 
  initialData = null, 
  isEditMode = false, 
  onClose = null, 
  onSuccess = null,
  showHeader = true,
  showProgress = true,
  onStepChange = null,
  onFormChange = null,
  onStepComplete = null
}, ref) => {
  const [currentStep, setCurrentStep] = useState(0)
  const [completedSteps, setCompletedSteps] = useState(new Set())
  const [formData, setFormData] = useState({
    business_name: '',
    business_type: [],
    industry: [],
    business_description: '',
    logo_url: '',
    target_audience: [],
    unique_value_proposition: '',
    brand_voice: '',
    brand_tone: '',
    primary_color: '',
    secondary_color: '',
    additional_colors: [],
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
    successful_content_url: '',
    successful_content_urls: [],
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
     meta_ads_facebook: false,
     meta_ads_instagram: false,
    // New fields for comprehensive onboarding
    target_audience_age_groups: [],
    target_audience_age_min: 16,
    target_audience_age_max: 90,
    target_audience_gender: 'all',
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
  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [logoUrl, setLogoUrl] = useState('')
  const [logoError, setLogoError] = useState('')
  const [mediaUrl, setMediaUrl] = useState('')
  const [mediaError, setMediaError] = useState('')
  const [extractedColors, setExtractedColors] = useState([])

  // Logo handling functions
  const handleLogoUpload = (url) => {
    setLogoUrl(url)
    setLogoError('')
    handleInputChange('logo_url', url)
  }

  const handleLogoError = (error) => {
    setLogoError(error)
  }

  const handleColorsExtracted = (colors) => {
    console.log('handleColorsExtracted called with:', colors)
    if (Array.isArray(colors) && colors.length > 0) {
      // Ensure colors are in hex format
      const hexColors = colors.map(color => {
        if (color.startsWith('#')) {
          return color
        } else if (color.startsWith('rgb')) {
          // Convert RGB to hex if needed
          const rgb = color.match(/\d+/g)
          if (rgb && rgb.length >= 3) {
            return '#' + rgb.slice(0, 3).map(x => {
              const hex = parseInt(x).toString(16)
              return hex.length === 1 ? '0' + hex : hex
            }).join('')
          }
        }
        return color
      })
      setExtractedColors(hexColors)
      console.log('Set extractedColors to:', hexColors)
    } else {
      console.warn('Invalid colors received:', colors)
      setExtractedColors([])
    }
  }

  const handleColorSuggestionClick = (color, type) => {
    handleInputChange(type === 'primary' ? 'primary_color' : 'secondary_color', color)
  }

  // Media upload handling functions
  const handleMediaUpload = (files) => {
    // files is an array of objects with url property
    if (Array.isArray(files)) {
      const urls = files.map(file => file.url || file).filter(Boolean)
      handleInputChange('successful_content_urls', urls)
    setMediaError('')
      // Also update single URL for backward compatibility
      if (urls.length > 0) {
        handleInputChange('successful_content_url', urls[0])
        setMediaUrl(urls[0])
      }
    } else if (files && files.url) {
      // Single file object
      handleInputChange('successful_content_urls', [files.url])
      handleInputChange('successful_content_url', files.url)
      setMediaUrl(files.url)
      setMediaError('')
    }
  }

  const handleMediaError = (error) => {
    setMediaError(error || '')
  }
  
  // Steps array - must be defined before useEffect hooks
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
    topPerformingContentTypeOther: '',
    lifeStagesOther: '',
    professionalTypesOther: '',
    lifestyleInterestsOther: '',
    buyerBehaviorOther: ''
  })

  // State for expandable cards
  const [expandedCards, setExpandedCards] = useState({
    ageGroups: false,
    lifeStages: false,
    professionalTypes: false,
    lifestyleInterests: false,
    buyerBehavior: false
  })

  // Expose methods to parent component
  useImperativeHandle(ref, () => ({
    goToStep: (stepIndex) => {
      if (stepIndex >= 0 && stepIndex < steps.length) {
        // In edit mode, allow navigation to any step without restrictions
        if (isEditMode) {
          setCurrentStep(stepIndex)
          if (onStepChange) {
            onStepChange(stepIndex)
          }
        } else {
          // Check if user can navigate to this step (only for onboarding mode)
          if (stepIndex === 0 || stepIndex <= Math.max(...completedSteps) + 1) {
            setCurrentStep(stepIndex)
            if (onStepChange) {
              onStepChange(stepIndex)
            }
          } else {
            setError(`Please complete the previous steps before accessing step ${stepIndex + 1}.`)
          }
        }
      }
    },
    getCurrentStep: () => currentStep,
    resetForm: () => {
      setFormData({
        business_name: '',
        business_type: [],
        industry: [],
        business_description: '',
        target_audience: [],
        unique_value_proposition: '',
        brand_voice: '',
        brand_tone: '',
        primary_color: '',
        secondary_color: '',
        additional_colors: [],
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
        successful_content_url: '',
        successful_content_urls: [],
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
        meta_ads_facebook: false,
        meta_ads_instagram: false,
        target_audience_age_groups: [],
        target_audience_age_min: 16,
        target_audience_age_max: 90,
        target_audience_gender: 'all',
        target_audience_life_stages: [],
        target_audience_professional_types: [],
        target_audience_lifestyle_interests: [],
        target_audience_buyer_behavior: [],
        platform_tone_instagram: [],
        platform_tone_facebook: [],
        platform_tone_linkedin: [],
        platform_tone_youtube: [],
      })
      setCurrentStep(0)
      setCompletedSteps(new Set())
      localStorage.removeItem('onboarding_form_data')
      localStorage.removeItem('onboarding_current_step')
      localStorage.removeItem('onboarding_completed_steps')
    }
  }))

  // Load initial data if provided
  useEffect(() => {
    if (initialData) {
      setFormData(prev => {
        const updatedData = { ...prev, ...initialData }
        
        // Ensure all array fields are arrays
        const arrayFields = [
          'business_type', 'industry', 'target_audience', 'social_media_platforms',
          'primary_goals', 'key_metrics_to_track', 'preferred_content_types',
          'content_themes', 'top_performing_content_types', 'best_time_to_post',
          'current_presence', 'focus_areas', 'target_audience_age_groups',
          'target_audience_life_stages', 'target_audience_professional_types',
          'target_audience_lifestyle_interests', 'target_audience_buyer_behavior',
          'platform_tone_instagram', 'platform_tone_facebook', 'platform_tone_linkedin',
          'platform_tone_youtube', 'additional_colors', 'successful_content_urls'
        ]
        
        // Handle age range and gender defaults
        if (!updatedData.target_audience_age_min) {
          updatedData.target_audience_age_min = 16
        }
        if (!updatedData.target_audience_age_max) {
          updatedData.target_audience_age_max = 90
        }
        if (!updatedData.target_audience_gender) {
          updatedData.target_audience_gender = 'all'
        }
        
        // Handle successful_content_urls - convert single URL to array if needed
        if (updatedData.successful_content_url && !updatedData.successful_content_urls) {
          updatedData.successful_content_urls = [updatedData.successful_content_url]
        } else if (!updatedData.successful_content_urls) {
          updatedData.successful_content_urls = []
        }
        
        arrayFields.forEach(field => {
          if (!Array.isArray(updatedData[field])) {
            updatedData[field] = []
          }
        })
        
        return updatedData
      })
      
      // Set logo URL if it exists in initial data
      if (initialData.logo_url) {
        setLogoUrl(initialData.logo_url)
      }
      
      // Set media URL if it exists in initial data
      if (initialData.successful_content_url) {
        setMediaUrl(initialData.successful_content_url)
      }
      // Handle successful_content_urls array
      if (initialData.successful_content_urls && Array.isArray(initialData.successful_content_urls) && initialData.successful_content_urls.length > 0) {
        setMediaUrl(initialData.successful_content_urls[0])
      }
    }
  }, [initialData])

  // Extract colors from logo if logo already exists
  useEffect(() => {
    const extractColorsFromExistingLogo = async () => {
      if (formData.logo_url && formData.logo_url.trim() && extractedColors.length === 0) {
        try {
          console.log('Extracting colors from existing logo:', formData.logo_url)
          const { mediaAPI } = await import('../services/api')
          const colorResponse = await mediaAPI.extractColorsFromLogo(formData.logo_url)
          console.log('Color extraction response:', colorResponse.data)
          if (colorResponse.data && colorResponse.data.colors) {
            handleColorsExtracted(colorResponse.data.colors)
          }
        } catch (error) {
          console.warn('Failed to extract colors from existing logo:', error)
        }
      }
    }
    extractColorsFromExistingLogo()
  }, [formData.logo_url])

  // Notify parent of step changes
  useEffect(() => {
    if (onStepChange) {
      onStepChange(currentStep)
    }
  }, [currentStep, onStepChange])

  // Load saved data from localStorage on component mount
  useEffect(() => {
    if (!isEditMode) {
      const savedFormData = localStorage.getItem('onboarding_form_data')
      const savedCurrentStep = localStorage.getItem('onboarding_current_step')
      const savedCompletedSteps = localStorage.getItem('onboarding_completed_steps')
      
      if (savedFormData) {
        try {
          const parsedData = JSON.parse(savedFormData)
          setFormData(prev => ({ ...prev, ...parsedData }))
        } catch (error) {
          console.error('Error parsing saved form data:', error)
        }
      }
      
      if (savedCurrentStep) {
        const step = parseInt(savedCurrentStep, 10)
        if (step >= 0 && step < steps.length) {
          setCurrentStep(step)
        }
      }
      
      if (savedCompletedSteps) {
        try {
          const parsedSteps = JSON.parse(savedCompletedSteps)
          setCompletedSteps(new Set(parsedSteps))
        } catch (error) {
          console.error('Error parsing completed steps:', error)
        }
      }
    }
  }, [isEditMode, steps.length])

  // Save form data to localStorage whenever it changes
  useEffect(() => {
    if (!isEditMode) {
      localStorage.setItem('onboarding_form_data', JSON.stringify(formData))
    }
  }, [formData, isEditMode])

  // Save current step to localStorage whenever it changes
  useEffect(() => {
    if (!isEditMode) {
      localStorage.setItem('onboarding_current_step', currentStep.toString())
    }
  }, [currentStep, isEditMode])

  // Save completed steps to localStorage whenever it changes
  useEffect(() => {
    if (!isEditMode) {
      localStorage.setItem('onboarding_completed_steps', JSON.stringify([...completedSteps]))
    }
  }, [completedSteps, isEditMode])


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
    'Instagram', 'Facebook', 'LinkedIn', 'YouTube', 'Google', 'Website'
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
    'Fun', 'Professional', 'Casual', 'Humorous', 'Bold', 'Neutral'
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
    'Website', 'Facebook', 'Instagram', 'LinkedIn (Personal)', 'YouTube'
  ]

  const focusAreas = [
    'SEO', 'Blog/Article Writing', 'Website Optimization/Copywriting', 
    'Digital Marketing (Organic Growth)', 'Paid Advertising', 
    'Email Marketing & Campaigns', 'YouTube/Video Marketing', 'Influencer Marketing', 
    'PPC', 'Lead Generation Campaigns', 'Brand Awareness', 'Local SEO/Maps Presence', 
    'Customer Retargeting', 'Not Sure – Let Emily suggest the best path'
  ]

  const targetAudienceCategories = {
    lifeStages: [
      'Students', 'Parents/Families', 'Newlyweds/Couples', 'Homeowners/Renters', 'Retired Individuals', 'Other (please specify)'
    ],
    professionalTypes: [
      'Business Owners/Entrepreneurs', 'Corporate Clients/B2B Buyers', 'Freelancers/Creators', 
      'Government Employees', 'Educators/Trainers', 'Job Seekers/Career Switchers', 'Writers and Journalists', 'Other (please specify)'
    ],
    lifestyleInterests: [
      'Fitness Enthusiasts', 'Outdoor/Adventure Lovers', 'Fashion/Beauty Conscious', 
      'Health-Conscious/Wellness Seekers', 'Pet Owners', 'Tech Enthusiasts/Gamers', 'Travelers/Digital Nomads', 'Other (please specify)'
    ],
    buyerBehavior: [
      'Premium Buyers/High-Income Consumers', 'Budget-Conscious Shoppers', 'Impulse Buyers', 
      'Ethical/Sustainable Shoppers', 'Frequent Online Buyers', 'Other (please specify)'
    ]
  }

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }))
    setError('')
    
    // Notify parent of form changes
    if (onFormChange) {
      onFormChange()
    }
  }

  const handleArrayChange = (field, value, checked) => {
    setFormData(prev => ({
      ...prev,
      [field]: checked 
        ? [...(prev[field] || []), value]
        : (prev[field] || []).filter(item => item !== value)
    }))
    
    // Notify parent of form changes
    if (onFormChange) {
      onFormChange()
    }
  }

  const handleOtherInputChange = (field, value) => {
    setOtherInputs(prev => ({
      ...prev,
      [field]: value
    }))
    
    // Notify parent of form changes
    if (onFormChange) {
      onFormChange()
    }
  }

  const toggleCard = (cardName) => {
    setExpandedCards(prev => ({
      ...prev,
      [cardName]: !prev[cardName]
    }))
  }

  const getSelectedCount = (field) => {
    return formData[field] ? formData[field].length : 0
  }

  const validateCurrentStep = () => {
    switch (currentStep) {
      case 0: // Basic Business Info
        return formData.business_name && 
               (formData.business_type && formData.business_type.length > 0) && 
               (formData.industry && formData.industry.length > 0)
      case 1: // Business Description
        const ageMin = Number(formData.target_audience_age_min) || 0
        const ageMax = Number(formData.target_audience_age_max) || 0
        const hasAgeRange = ageMin >= 16 && ageMax >= ageMin && ageMax <= 90 && ageMin > 0 && ageMax > 0
        const hasGender = formData.target_audience_gender && ['all', 'men', 'women'].includes(formData.target_audience_gender)
        const hasBusinessDesc = formData.business_description && String(formData.business_description).trim().length > 0
        const hasUVP = formData.unique_value_proposition && String(formData.unique_value_proposition).trim().length > 0
        
        return hasBusinessDesc && hasUVP && hasAgeRange && hasGender
      case 2: // Brand & Contact
        return formData.brand_voice && formData.brand_tone && formData.phone_number && 
               formData.street_address && formData.city && formData.state && formData.country
      case 3: // Current Presence & Focus Areas
        // This step is optional - no required fields
        return true
      case 4: // Digital Marketing & Goals
        return (formData.social_media_platforms && formData.social_media_platforms.length > 0) && 
               (formData.primary_goals && formData.primary_goals.length > 0) && 
               (formData.key_metrics_to_track && formData.key_metrics_to_track.length > 0)
      case 5: // Content Strategy
        return (formData.preferred_content_types && formData.preferred_content_types.length > 0) && 
               (formData.content_themes && formData.content_themes.length > 0)
      case 6: // Market & Competition
        return formData.market_position && formData.products_or_services
      case 7: // Campaign Planning
        return (formData.top_performing_content_types && formData.top_performing_content_types.length > 0) && 
               (formData.best_time_to_post && formData.best_time_to_post.length > 0)
      case 8: // Performance & Customer
        return formData.hashtags_that_work_well && 
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
      // Mark current step as completed
      setCompletedSteps(prev => new Set([...prev, currentStep]))
      
      if (onStepComplete) {
        onStepComplete(currentStep)
      }
      
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

  // Check if a step is accessible
  const isStepAccessible = (stepIndex) => {
    // In edit mode, all steps are accessible
    if (isEditMode) return true
    
    if (stepIndex === 0) return true
    if (stepIndex <= Math.max(...completedSteps) + 1) return true
    return false
  }

  // Check if a step is completed
  const isStepCompleted = (stepIndex) => {
    return completedSteps.has(stepIndex)
  }

  const handleSaveStep = async () => {
    setIsSaving(true)
    setError('')
    setSaveSuccess(false)
    
    try {
      // Prepare the data for submission
      const submissionData = {
        ...formData,
        // Mark onboarding as completed when saving in edit mode
        onboarding_completed: true,
        // Include new fields explicitly to ensure they are saved
        target_audience_age_min: formData.target_audience_age_min,
        target_audience_age_max: formData.target_audience_age_max,
        target_audience_gender: formData.target_audience_gender,
        target_audience_life_stages: formData.target_audience_life_stages || [],
        target_audience_professional_types: formData.target_audience_professional_types || [],
        target_audience_lifestyle_interests: formData.target_audience_lifestyle_interests || [],
        target_audience_buyer_behavior: formData.target_audience_buyer_behavior || [],
        successful_content_urls: formData.successful_content_urls || [],
        primary_color: formData.primary_color,
        secondary_color: formData.secondary_color,
        // Include platform tone fields explicitly
        platform_tone_instagram: formData.platform_tone_instagram || [],
        platform_tone_facebook: formData.platform_tone_facebook || [],
        platform_tone_linkedin: formData.platform_tone_linkedin || [],
        platform_tone_youtube: formData.platform_tone_youtube || [],
        // Populate the general target_audience field with all selected target audience details
        target_audience: [
          ...(formData.target_audience_age_min && formData.target_audience_age_max ? [`${formData.target_audience_age_min}-${formData.target_audience_age_max} years`] : []),
          ...(formData.target_audience_gender ? [formData.target_audience_gender] : []),
          ...(formData.target_audience_life_stages || []).filter(item => item !== 'Other (please specify)'),
          ...(formData.target_audience_life_stages && formData.target_audience_life_stages.includes('Other (please specify)') && otherInputs.lifeStagesOther ? [otherInputs.lifeStagesOther] : []),
          ...(formData.target_audience_professional_types || []).filter(item => item !== 'Other (please specify)'),
          ...(formData.target_audience_professional_types && formData.target_audience_professional_types.includes('Other (please specify)') && otherInputs.professionalTypesOther ? [otherInputs.professionalTypesOther] : []),
          ...(formData.target_audience_lifestyle_interests || []).filter(item => item !== 'Other (please specify)'),
          ...(formData.target_audience_lifestyle_interests && formData.target_audience_lifestyle_interests.includes('Other (please specify)') && otherInputs.lifestyleInterestsOther ? [otherInputs.lifestyleInterestsOther] : []),
          ...(formData.target_audience_buyer_behavior || []).filter(item => item !== 'Other (please specify)'),
          ...(formData.target_audience_buyer_behavior && formData.target_audience_buyer_behavior.includes('Other (please specify)') && otherInputs.buyerBehaviorOther ? [otherInputs.buyerBehaviorOther] : [])
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

      console.log('Saving step data:', submissionData)
      console.log('Current step:', currentStep)
      console.log('API call starting...')

      // Update existing profile with onboarding completed
      const result = await onboardingAPI.updateProfile(submissionData)
      console.log('Save result:', result)
      console.log('API call completed successfully')
      
      // Mark current step as completed
      setCompletedSteps(prev => new Set([...prev, currentStep]))
      if (onStepComplete) {
        onStepComplete(currentStep)
      }
      
      // Show success indicator
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
      
      // Notify parent component of successful save
      if (onSuccess) {
        onSuccess()
      }
      
    } catch (err) {
      console.error('Error saving step:', err)
      console.error('Error details:', err.response || err.message)
      setError(err.message || 'Failed to save changes')
    } finally {
      setIsSaving(false)
    }
  }

  const handleSubmit = async () => {
    setIsSubmitting(true)
    setError('')

    try {
      // Prepare the data for submission
      const submissionData = {
        ...formData,
        onboarding_type: 'business',
        // Populate the general target_audience field with all selected target audience details
        target_audience: [
          ...(formData.target_audience_age_min && formData.target_audience_age_max ? [`${formData.target_audience_age_min}-${formData.target_audience_age_max} years`] : []),
          ...(formData.target_audience_gender ? [formData.target_audience_gender] : []),
          ...(formData.target_audience_life_stages || []).filter(item => item !== 'Other (please specify)'),
          ...(formData.target_audience_life_stages && formData.target_audience_life_stages.includes('Other (please specify)') && otherInputs.lifeStagesOther ? [otherInputs.lifeStagesOther] : []),
          ...(formData.target_audience_professional_types || []).filter(item => item !== 'Other (please specify)'),
          ...(formData.target_audience_professional_types && formData.target_audience_professional_types.includes('Other (please specify)') && otherInputs.professionalTypesOther ? [otherInputs.professionalTypesOther] : []),
          ...(formData.target_audience_lifestyle_interests || []).filter(item => item !== 'Other (please specify)'),
          ...(formData.target_audience_lifestyle_interests && formData.target_audience_lifestyle_interests.includes('Other (please specify)') && otherInputs.lifestyleInterestsOther ? [otherInputs.lifestyleInterestsOther] : []),
          ...(formData.target_audience_buyer_behavior || []).filter(item => item !== 'Other (please specify)'),
          ...(formData.target_audience_buyer_behavior && formData.target_audience_buyer_behavior.includes('Other (please specify)') && otherInputs.buyerBehaviorOther ? [otherInputs.buyerBehaviorOther] : [])
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

      console.log('Submitting profile data:', submissionData)
      console.log('Is edit mode:', isEditMode)

      if (isEditMode) {
        // Update existing profile
        console.log('Calling updateProfile API...')
        const result = await onboardingAPI.updateProfile(submissionData)
        console.log('Update result:', result)
        if (onSuccess) onSuccess()
      } else {
        // Create new profile
        console.log('Calling submitOnboarding API...')
        const result = await onboardingAPI.submitOnboarding(submissionData)
        console.log('Submit result:', result)
        // Clear localStorage after successful submission
        localStorage.removeItem('onboarding_form_data')
        localStorage.removeItem('onboarding_current_step')
        localStorage.removeItem('onboarding_completed_steps')
        if (onSuccess) onSuccess()
      }
    } catch (err) {
      console.error('Error submitting profile:', err)
      setError(err.message || 'Failed to save profile')
    } finally {
      setIsSubmitting(false)
    }
  }

  const renderStep = () => {
    switch (currentStep) {
      case 0:
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Business Name *</label>
              <input
                type="text"
                value={formData.business_name}
                onChange={(e) => handleInputChange('business_name', e.target.value)}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="Enter business name"
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Business Type *</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {businessTypes.map(type => (
                  <label key={type} className="flex items-center space-x-1.5 sm:space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.business_type && formData.business_type.includes(type)}
                      onChange={(e) => handleArrayChange('business_type', type, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500 flex-shrink-0"
                    />
                    <span className="text-xs sm:text-sm text-gray-700 break-words">{type}</span>
                  </label>
                ))}
              </div>
              {formData.business_type && formData.business_type.includes('Other') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.businessTypeOther}
                    onChange={(e) => handleOtherInputChange('businessTypeOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify your business type"
                  />
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Industry *</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-2">
                {industries.map(industry => (
                  <label key={industry} className="flex items-center space-x-1.5 sm:space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.industry && formData.industry.includes(industry)}
                      onChange={(e) => handleArrayChange('industry', industry, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500 flex-shrink-0"
                    />
                    <span className="text-xs sm:text-sm text-gray-700 break-words">{industry}</span>
                  </label>
                ))}
              </div>
              {formData.industry && formData.industry.includes('Others') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.industryOther}
                    onChange={(e) => handleOtherInputChange('industryOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify your industry"
                  />
                </div>
              )}
            </div>
          </div>
        )

      case 1:
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">
                Business Description *
                <InfoTooltip 
                  content="Describe your business in detail - what you offer, who your customers are, and how your products or services work. This helps Emily understand your brand and create tailored marketing content."
                  className="ml-0.5 sm:ml-1 md:ml-2"
                />
              </label>
              <textarea
                value={formData.business_description}
                onChange={(e) => handleInputChange('business_description', e.target.value)}
                rows={3}
                className="w-full px-2 sm:px-3 md:px-4 py-1.5 sm:py-2 md:py-2.5 lg:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="Describe what your business does..."
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">
                Business Logo (Optional)
                <InfoTooltip 
                  content="Uploading your company logo is optional, but it helps the AI create branded visuals and maintain a consistent look across campaigns, making your marketing more professional and recognizable."
                  className="ml-0.5 sm:ml-1 md:ml-2"
                />
              </label>
              <LogoUpload
                value={formData.logo_url}
                onUploadSuccess={handleLogoUpload}
                onError={handleLogoError}
                onColorsExtracted={handleColorsExtracted}
                className="max-w-md"
              />
              {logoError && (
                <div className="text-red-600 text-sm mt-2">{logoError}</div>
              )}
            </div>


            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Target Audience *</label>
              <div className="space-y-4">
                {/* Age Range Card */}
                <div className="border border-gray-200 rounded-lg p-4">
                  <label className="block text-sm font-medium text-gray-700 mb-4">
                    Age Range <span className="text-black">*</span>
                  </label>
                  <DualRangeSlider
                    min={16}
                    max={90}
                    minValue={formData.target_audience_age_min}
                    maxValue={formData.target_audience_age_max}
                    onChange={({ min, max }) => {
                      handleInputChange('target_audience_age_min', min !== null ? Number(min) : null)
                      handleInputChange('target_audience_age_max', max !== null ? Number(max) : null)
                    }}
                  />
                    </div>

                {/* Gender Selection */}
                <div className="border border-gray-200 rounded-lg p-4">
                  <label className="block text-sm font-medium text-gray-700 mb-4">
                    Gender <span className="text-black">*</span>
                  </label>
                  <div className="flex flex-col space-y-2">
                    {['all', 'men', 'women'].map((gender) => (
                      <label key={gender} className="flex items-center space-x-2 cursor-pointer">
                              <input
                          type="radio"
                          name="target_audience_gender"
                          value={gender}
                          checked={formData.target_audience_gender === gender}
                          onChange={(e) => handleInputChange('target_audience_gender', e.target.value)}
                          className="text-pink-600 focus:ring-pink-500"
                              />
                        <span className="text-sm text-gray-700 capitalize">{gender === 'all' ? 'All' : gender === 'men' ? 'Men' : 'Women'}</span>
                            </label>
                        ))}
                      </div>
                </div>

                {/* Life Stage / Roles Card */}
                <div className="border border-gray-200 rounded-lg">
                  <button
                    type="button"
                    onClick={() => toggleCard('lifeStages')}
                    className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors relative"
                  >
                    <span className="text-sm font-medium text-gray-700">Life Stage / Roles</span>
                    <div className="flex items-center space-x-2">
                      <span className="w-6 h-6 bg-pink-100 text-pink-600 rounded-full flex items-center justify-center text-xs font-medium">
                        {getSelectedCount('target_audience_life_stages')}
                      </span>
                      <svg 
                        className={`w-4 h-4 text-gray-400 transition-transform ${expandedCards.lifeStages ? 'rotate-180' : ''}`}
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </button>
                  {expandedCards.lifeStages && (
                    <div className="px-4 pb-4 border-t border-gray-100">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-3">
                        {targetAudienceCategories.lifeStages.map(stage => (
                           <label key={stage} className="flex items-center space-x-1.5 sm:space-x-2">
                              <input
                                type="checkbox"
                                checked={formData.target_audience_life_stages && formData.target_audience_life_stages.includes(stage)}
                                onChange={(e) => handleArrayChange('target_audience_life_stages', stage, e.target.checked)}
                                className="rounded border-gray-300 text-pink-600 focus:ring-pink-500 flex-shrink-0"
                              />
                             <span className="text-xs sm:text-sm text-gray-700 break-words">{stage}</span>
                            </label>
                        ))}
                      </div>
                      {formData.target_audience_life_stages && formData.target_audience_life_stages.includes('Other (please specify)') && (
                        <div className="mt-3">
                          <input
                            type="text"
                            value={otherInputs.lifeStagesOther}
                            onChange={(e) => handleOtherInputChange('lifeStagesOther', e.target.value)}
                            className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                            placeholder="Please specify your target audience life stage"
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Professional / Business Type Card */}
                <div className="border border-gray-200 rounded-lg">
                  <button
                    type="button"
                    onClick={() => toggleCard('professionalTypes')}
                    className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors relative"
                  >
                    <span className="text-sm font-medium text-gray-700">Professional / Business Type <span className="text-gray-500 text-xs">(Optional)</span></span>
                    <div className="flex items-center space-x-2">
                      <span className="w-6 h-6 bg-pink-100 text-pink-600 rounded-full flex items-center justify-center text-xs font-medium">
                        {getSelectedCount('target_audience_professional_types')}
                      </span>
                      <svg 
                        className={`w-4 h-4 text-gray-400 transition-transform ${expandedCards.professionalTypes ? 'rotate-180' : ''}`}
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </button>
                  {expandedCards.professionalTypes && (
                    <div className="px-4 pb-4 border-t border-gray-100">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-3">
                        {targetAudienceCategories.professionalTypes.map(type => (
                          <label key={type} className="flex items-center space-x-1.5 sm:space-x-2">
                            <input
                              type="checkbox"
                              checked={formData.target_audience_professional_types && formData.target_audience_professional_types.includes(type)}
                              onChange={(e) => handleArrayChange('target_audience_professional_types', type, e.target.checked)}
                              className="rounded border-gray-300 text-pink-600 focus:ring-pink-500"
                            />
                            <span className="text-xs sm:text-sm text-gray-700 break-words">{type}</span>
                          </label>
                        ))}
                      </div>
                      {formData.target_audience_professional_types && formData.target_audience_professional_types.includes('Other (please specify)') && (
                        <div className="mt-3">
                          <input
                            type="text"
                            value={otherInputs.professionalTypesOther}
                            onChange={(e) => handleOtherInputChange('professionalTypesOther', e.target.value)}
                            className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                            placeholder="Please specify your target audience professional type"
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Lifestyle & Interests Card */}
                <div className="border border-gray-200 rounded-lg">
                  <button
                    type="button"
                    onClick={() => toggleCard('lifestyleInterests')}
                    className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors relative"
                  >
                    <span className="text-sm font-medium text-gray-700">Lifestyle & Interests <span className="text-gray-500 text-xs">(Optional)</span></span>
                    <div className="flex items-center space-x-2">
                      <span className="w-6 h-6 bg-pink-100 text-pink-600 rounded-full flex items-center justify-center text-xs font-medium">
                        {getSelectedCount('target_audience_lifestyle_interests')}
                      </span>
                      <svg 
                        className={`w-4 h-4 text-gray-400 transition-transform ${expandedCards.lifestyleInterests ? 'rotate-180' : ''}`}
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </button>
                  {expandedCards.lifestyleInterests && (
                    <div className="px-4 pb-4 border-t border-gray-100">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-3">
                        {targetAudienceCategories.lifestyleInterests.map(interest => (
                           <label key={interest} className="flex items-center space-x-1.5 sm:space-x-2">
                              <input
                                type="checkbox"
                                checked={formData.target_audience_lifestyle_interests && formData.target_audience_lifestyle_interests.includes(interest)}
                                onChange={(e) => handleArrayChange('target_audience_lifestyle_interests', interest, e.target.checked)}
                                className="rounded border-gray-300 text-pink-600 focus:ring-pink-500 flex-shrink-0"
                              />
                             <span className="text-xs sm:text-sm text-gray-700 break-words">{interest}</span>
                            </label>
                        ))}
                      </div>
                      {formData.target_audience_lifestyle_interests && formData.target_audience_lifestyle_interests.includes('Other (please specify)') && (
                        <div className="mt-3">
                          <input
                            type="text"
                            value={otherInputs.lifestyleInterestsOther}
                            onChange={(e) => handleOtherInputChange('lifestyleInterestsOther', e.target.value)}
                            className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                            placeholder="Please specify your target audience lifestyle interest"
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Buyer Behavior Card */}
                <div className="border border-gray-200 rounded-lg">
                  <button
                    type="button"
                    onClick={() => toggleCard('buyerBehavior')}
                    className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 transition-colors relative"
                  >
                    <span className="text-sm font-medium text-gray-700">Buyer Behavior</span>
                    <div className="flex items-center space-x-2">
                      <span className="w-6 h-6 bg-pink-100 text-pink-600 rounded-full flex items-center justify-center text-xs font-medium">
                        {getSelectedCount('target_audience_buyer_behavior')}
                      </span>
                      <svg 
                        className={`w-4 h-4 text-gray-400 transition-transform ${expandedCards.buyerBehavior ? 'rotate-180' : ''}`}
                        fill="none" 
                        stroke="currentColor" 
                        viewBox="0 0 24 24"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                      </svg>
                    </div>
                  </button>
                  {expandedCards.buyerBehavior && (
                    <div className="px-4 pb-4 border-t border-gray-100">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-3">
                        {targetAudienceCategories.buyerBehavior.map(behavior => (
                           <label key={behavior} className="flex items-center space-x-1.5 sm:space-x-2">
                              <input
                                type="checkbox"
                                checked={formData.target_audience_buyer_behavior && formData.target_audience_buyer_behavior.includes(behavior)}
                                onChange={(e) => handleArrayChange('target_audience_buyer_behavior', behavior, e.target.checked)}
                                className="rounded border-gray-300 text-pink-600 focus:ring-pink-500 flex-shrink-0"
                              />
                             <span className="text-xs sm:text-sm text-gray-700 break-words">{behavior}</span>
                            </label>
                        ))}
                      </div>
                      {formData.target_audience_buyer_behavior && formData.target_audience_buyer_behavior.includes('Other (please specify)') && (
                        <div className="mt-3">
                          <input
                            type="text"
                            value={otherInputs.buyerBehaviorOther}
                            onChange={(e) => handleOtherInputChange('buyerBehaviorOther', e.target.value)}
                            className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                            placeholder="Please specify your target audience buyer behavior"
                          />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">
                Unique Value Proposition *
                <InfoTooltip 
                  content="Highlight your business's main strength or advantage that sets you apart. This helps the AI emphasize your key value in marketing content."
                  className="ml-0.5 sm:ml-1 md:ml-2"
                />
              </label>
              <textarea
                value={formData.unique_value_proposition}
                onChange={(e) => handleInputChange('unique_value_proposition', e.target.value)}
                rows={3}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="What makes your business unique?"
              />
            </div>
          </div>
        )

      case 2:
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Brand Voice *</label>
                <select
                  value={formData.brand_voice}
                  onChange={(e) => handleInputChange('brand_voice', e.target.value)}
                  className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                >
                  <option value="">Select your brand voice</option>
                  {brandVoices.map(voice => (
                    <option key={voice} value={voice}>{voice}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Brand Tone *</label>
                <select
                  value={formData.brand_tone}
                  onChange={(e) => handleInputChange('brand_tone', e.target.value)}
                  className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                >
                  <option value="">Select your brand tone</option>
                  {brandTones.map(tone => (
                    <option key={tone} value={tone}>{tone}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Brand Colors Section */}
            <div className="border-t border-gray-200 pt-6 mt-6">
              <h4 className="text-sm font-semibold text-gray-800 mb-4">Brand Colors</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">Primary Color</label>
                    {extractedColors && extractedColors.length > 0 && (
                      <div className="flex items-center space-x-1.5">
                        <span className="text-xs text-gray-500">Suggested:</span>
                        {extractedColors.slice(0, 4).map((color, index) => (
                          <button
                            key={index}
                            type="button"
                            onClick={() => handleColorSuggestionClick(color, 'primary')}
                            className="w-6 h-6 rounded border-2 border-gray-300 hover:border-pink-500 hover:scale-110 transition-all cursor-pointer shadow-sm"
                            style={{ backgroundColor: color }}
                            title={color}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center space-x-2">
                    <input
                      type="color"
                      value={formData.primary_color || '#000000'}
                      onChange={(e) => handleInputChange('primary_color', e.target.value)}
                      className="w-16 h-10 border border-gray-300 rounded-md cursor-pointer"
                    />
                    <input
                      type="text"
                      value={formData.primary_color || ''}
                      onChange={(e) => handleInputChange('primary_color', e.target.value)}
                      className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                      placeholder="#000000"
                      pattern="^#[0-9A-Fa-f]{6}$"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">Secondary Color</label>
                    {extractedColors && extractedColors.length > 0 && (
                      <div className="flex items-center space-x-1.5">
                        <span className="text-xs text-gray-500">Suggested:</span>
                        {extractedColors.slice(0, 4).map((color, index) => (
                          <button
                            key={index}
                            type="button"
                            onClick={() => handleColorSuggestionClick(color, 'secondary')}
                            className="w-6 h-6 rounded border-2 border-gray-300 hover:border-pink-500 hover:scale-110 transition-all cursor-pointer shadow-sm"
                            style={{ backgroundColor: color }}
                            title={color}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center space-x-2">
                    <input
                      type="color"
                      value={formData.secondary_color || '#000000'}
                      onChange={(e) => handleInputChange('secondary_color', e.target.value)}
                      className="w-16 h-10 border border-gray-300 rounded-md cursor-pointer"
                    />
                    <input
                      type="text"
                      value={formData.secondary_color || ''}
                      onChange={(e) => handleInputChange('secondary_color', e.target.value)}
                      className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                      placeholder="#000000"
                      pattern="^#[0-9A-Fa-f]{6}$"
                    />
                  </div>
                </div>
              </div>

              {/* Additional Colors */}
              <div>
                <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Additional Colors</label>
                <div className="space-y-2">
                  {formData.additional_colors && formData.additional_colors.map((color, index) => (
                    <div key={index} className="flex items-center space-x-2">
                      <input
                        type="color"
                        value={color || '#000000'}
                        onChange={(e) => {
                          const newColors = [...formData.additional_colors]
                          newColors[index] = e.target.value
                          handleInputChange('additional_colors', newColors)
                        }}
                        className="w-16 h-10 border border-gray-300 rounded-md cursor-pointer"
                      />
                      <input
                        type="text"
                        value={color}
                        onChange={(e) => {
                          const newColors = [...formData.additional_colors]
                          newColors[index] = e.target.value
                          handleInputChange('additional_colors', newColors)
                        }}
                        className="flex-1 px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                        placeholder="#000000"
                        pattern="^#[0-9A-Fa-f]{6}$"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          const newColors = formData.additional_colors.filter((_, i) => i !== index)
                          handleInputChange('additional_colors', newColors)
                        }}
                        className="px-3 py-2 text-red-600 hover:text-red-800 border border-red-300 rounded-md hover:bg-red-50 transition-colors"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() => {
                      handleInputChange('additional_colors', [...(formData.additional_colors || []), ''])
                    }}
                    className="text-xs sm:text-sm text-pink-600 hover:text-pink-800 font-medium flex items-center space-x-1"
                  >
                    <span>+ Add Color</span>
                  </button>
                </div>
              </div>
            </div>


            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Phone Number *</label>
              <input
                type="tel"
                value={formData.phone_number}
                onChange={(e) => handleInputChange('phone_number', e.target.value)}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="+1 (555) 123-4567"
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Street Address *</label>
              <input
                type="text"
                value={formData.street_address}
                onChange={(e) => handleInputChange('street_address', e.target.value)}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="123 Main Street"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">City *</label>
                <input
                  type="text"
                  value={formData.city}
                  onChange={(e) => handleInputChange('city', e.target.value)}
                  className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                  placeholder="New York"
                />
              </div>

              <div>
                <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">State/Province *</label>
                <input
                  type="text"
                  value={formData.state}
                  onChange={(e) => handleInputChange('state', e.target.value)}
                  className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                  placeholder="NY"
                />
              </div>

              <div>
                <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Country *</label>
                <input
                  type="text"
                  value={formData.country}
                  onChange={(e) => handleInputChange('country', e.target.value)}
                  className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                  placeholder="United States"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Timezone</label>
              <select
                value={formData.timezone}
                onChange={(e) => handleInputChange('timezone', e.target.value)}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
              >
                <option value="">Select your timezone</option>
                {timezones.map(tz => (
                  <option key={tz} value={tz}>{tz}</option>
                ))}
              </select>
            </div>
          </div>
        )

      case 3:
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Current Online Presence (Select all that apply)</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {currentPresenceOptions.map(option => (
                  <label key={option} className="flex items-center space-x-1.5 sm:space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.current_presence && formData.current_presence.includes(option)}
                      onChange={(e) => handleArrayChange('current_presence', option, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500 flex-shrink-0"
                    />
                    <span className="text-xs sm:text-sm text-gray-700 break-words">{option}</span>
                  </label>
                ))}
              </div>
              {formData.current_presence && formData.current_presence.includes('Other') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.currentPresenceOther}
                    onChange={(e) => handleOtherInputChange('currentPresenceOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify your other online presence"
                  />
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Focus Areas (Select all that apply)</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {focusAreas.map(area => (
                  <label key={area} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.focus_areas && formData.focus_areas.includes(area)}
                      onChange={(e) => handleArrayChange('focus_areas', area, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500"
                    />
                    <span className="text-sm text-gray-700">{area}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Platform-specific details - Only show if user has selected platforms */}
            {formData.current_presence && formData.current_presence.length > 0 && (
              <div className="space-y-4">
                <h4 className="text-lg font-medium text-gray-800">Platform Details</h4>
                <p className="text-sm text-gray-600">Please provide details for the platforms you selected above.</p>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Website */}
                  {formData.current_presence.includes('Website') && (
                    <div>
                      <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Website URL *</label>
                      <input
                        type="url"
                        value={formData.website_url}
                        onChange={(e) => handleInputChange('website_url', e.target.value)}
                        className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                        placeholder="https://your-website.com"
                        required
                      />
                      <p className="text-xs text-gray-500 mt-1">Must start with https://</p>
                    </div>
                  )}

                  {/* Facebook */}
                  {formData.current_presence.includes('Facebook') && (
                    <div>
                      <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Facebook Page/Profile Link</label>
                      <input
                        type="url"
                        value={formData.facebook_page_name}
                        onChange={(e) => handleInputChange('facebook_page_name', e.target.value)}
                        className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                        placeholder="https://facebook.com/yourpage"
                      />
                    </div>
                  )}

                  {/* Instagram */}
                  {formData.current_presence.includes('Instagram') && (
                    <div>
                      <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Instagram Profile Link</label>
                      <input
                        type="url"
                        value={formData.instagram_profile_link}
                        onChange={(e) => handleInputChange('instagram_profile_link', e.target.value)}
                        className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                        placeholder="https://instagram.com/yourprofile"
                      />
                    </div>
                  )}

                  {/* LinkedIn */}
                  {formData.current_presence.includes('LinkedIn (Personal)') && (
                    <div>
                      <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">LinkedIn Company Link</label>
                      <input
                        type="url"
                        value={formData.linkedin_company_link}
                        onChange={(e) => handleInputChange('linkedin_company_link', e.target.value)}
                        className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                        placeholder="https://linkedin.com/company/yourcompany"
                      />
                    </div>
                  )}

                  {/* YouTube */}
                  {formData.current_presence.includes('YouTube') && (
                    <div>
                      <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">YouTube Channel Link</label>
                      <input
                        type="url"
                        value={formData.youtube_channel_link}
                        onChange={(e) => handleInputChange('youtube_channel_link', e.target.value)}
                        className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                        placeholder="https://youtube.com/@yourchannel"
                      />
                    </div>
                  )}


                </div>

              </div>
            )}
          </div>
        )

      case 4:
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Digital Marketing Platforms (Select all that apply) *</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {socialPlatforms.map(platform => (
                  <label key={platform} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.social_media_platforms && formData.social_media_platforms.includes(platform)}
                      onChange={(e) => handleArrayChange('social_media_platforms', platform, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500"
                    />
                    <span className="text-sm text-gray-700">{platform}</span>
                  </label>
                ))}
              </div>
              {formData.social_media_platforms && formData.social_media_platforms.includes('Other') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.socialPlatformOther}
                    onChange={(e) => handleOtherInputChange('socialPlatformOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify your other digital marketing platform"
                  />
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Primary Goals (Select all that apply) *</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {goals.map(goal => (
                  <label key={goal} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.primary_goals && formData.primary_goals.includes(goal)}
                      onChange={(e) => handleArrayChange('primary_goals', goal, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500"
                    />
                    <span className="text-sm text-gray-700">{goal}</span>
                  </label>
                ))}
              </div>
              {formData.primary_goals && formData.primary_goals.includes('Other') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.goalOther}
                    onChange={(e) => handleOtherInputChange('goalOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify your other goal"
                  />
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Key Metrics to Track (Select all that apply) *</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {metrics.map(metric => (
                  <label key={metric} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.key_metrics_to_track && formData.key_metrics_to_track.includes(metric)}
                      onChange={(e) => handleArrayChange('key_metrics_to_track', metric, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500"
                    />
                    <span className="text-sm text-gray-700">{metric}</span>
                  </label>
                ))}
              </div>
              {formData.key_metrics_to_track && formData.key_metrics_to_track.includes('Other') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.metricOther}
                    onChange={(e) => handleOtherInputChange('metricOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify your other metric"
                  />
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">
                  Monthly Marketing Budget
                  <InfoTooltip 
                    content="Enter the approximate amount you plan to spend on marketing each month. This helps Emily create campaigns that fit your budget."
                    className="ml-0.5 sm:ml-1 md:ml-2"
                  />
                </label>
                <select
                  value={formData.monthly_budget_range}
                  onChange={(e) => handleInputChange('monthly_budget_range', e.target.value)}
                  className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                >
                  <option value="">Select budget range</option>
                  {budgetRanges.map(range => (
                    <option key={range} value={range}>{range}</option>
                  ))}
                </select>
              </div>

            </div>
          </div>
        )

      case 5:
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Preferred Content Types (Select all that apply) *</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {contentTypes.map(type => (
                  <label key={type} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.preferred_content_types && formData.preferred_content_types.includes(type)}
                      onChange={(e) => handleArrayChange('preferred_content_types', type, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500"
                    />
                    <span className="text-xs sm:text-sm text-gray-700 break-words">{type}</span>
                  </label>
                ))}
              </div>
              {formData.preferred_content_types && formData.preferred_content_types.includes('Other') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.contentTypeOther}
                    onChange={(e) => handleOtherInputChange('contentTypeOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify your other content type"
                  />
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Content Themes (Select all that apply) *</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {contentThemes.map(theme => (
                  <label key={theme} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.content_themes && formData.content_themes.includes(theme)}
                      onChange={(e) => handleArrayChange('content_themes', theme, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500"
                    />
                    <span className="text-sm text-gray-700">{theme}</span>
                  </label>
                ))}
              </div>
              {formData.content_themes && formData.content_themes.includes('Others') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.contentThemeOther}
                    onChange={(e) => handleOtherInputChange('contentThemeOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify your other content theme"
                  />
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Best Time to Post (Select all that apply)</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {postingTimes.map(time => (
                  <label key={time} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.best_time_to_post && formData.best_time_to_post.includes(time)}
                      onChange={(e) => handleArrayChange('best_time_to_post', time, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500"
                    />
                    <span className="text-sm text-gray-700">{time}</span>
                  </label>
                ))}
              </div>
              {formData.best_time_to_post && formData.best_time_to_post.includes('Other') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.postingTimeOther}
                    onChange={(e) => handleOtherInputChange('postingTimeOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify your other posting time"
                  />
                </div>
              )}
            </div>
          </div>
        )

      case 6:
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Market Position *</label>
              <select
                value={formData.market_position}
                onChange={(e) => handleInputChange('market_position', e.target.value)}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                required
              >
                <option value="">Select your market position</option>
                {marketPositions.map(position => (
                  <option key={position.value} value={position.value}>
                    {position.label} - {position.description}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">
                Products or Services *
                <InfoTooltip 
                  content="Provide a detailed description of one product or service you want to promote with this AI. Include features, benefits, and target customers so the AI can craft accurate content."
                  className="ml-2"
                />
              </label>
              <textarea
                value={formData.products_or_services}
                onChange={(e) => handleInputChange('products_or_services', e.target.value)}
                rows={4}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="Describe your main products or services..."
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Main Competitors</label>
              <textarea
                value={formData.main_competitors}
                onChange={(e) => handleInputChange('main_competitors', e.target.value)}
                rows={3}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="List your main competitors and what makes them successful..."
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Important Launch Dates</label>
              <input
                type="date"
                value={formData.important_launch_dates}
                onChange={(e) => handleInputChange('important_launch_dates', e.target.value)}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="Select launch date"
              />
              <p className="text-xs text-gray-500 mt-1">Select the date for your important product launch or event</p>
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">
                Planned Promotions or Campaigns
                <InfoTooltip 
                  content="Share any upcoming promotions or campaigns you're planning. This helps Emily align content and strategy with your marketing goals."
                  className="ml-0.5 sm:ml-1 md:ml-2"
                />
              </label>
              <textarea
                value={formData.planned_promotions_or_campaigns}
                onChange={(e) => handleInputChange('planned_promotions_or_campaigns', e.target.value)}
                rows={3}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="Any upcoming promotions, sales, or marketing campaigns..."
              />
            </div>
          </div>
        )

      case 7:
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Top Performing Content Types (Select all that apply) *</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {contentTypes.map(type => (
                  <label key={type} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.top_performing_content_types && formData.top_performing_content_types.includes(type)}
                      onChange={(e) => handleArrayChange('top_performing_content_types', type, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500"
                    />
                    <span className="text-xs sm:text-sm text-gray-700 break-words">{type}</span>
                  </label>
                ))}
              </div>
              {formData.top_performing_content_types && formData.top_performing_content_types.includes('Other') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.topPerformingContentTypeOther}
                    onChange={(e) => handleOtherInputChange('topPerformingContentTypeOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify your other top performing content type"
                  />
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Best Time to Post (Select all that apply) *</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {postingTimes.map(time => (
                  <label key={time} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.best_time_to_post && formData.best_time_to_post.includes(time)}
                      onChange={(e) => handleArrayChange('best_time_to_post', time, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500"
                    />
                    <span className="text-sm text-gray-700">{time}</span>
                  </label>
                ))}
              </div>
              {formData.best_time_to_post && formData.best_time_to_post.includes('Other') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.postingTimeOther}
                    onChange={(e) => handleOtherInputChange('postingTimeOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify your other posting time"
                  />
                </div>
              )}
            </div>
          </div>
        )

      case 8:
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">
                Most Successful Campaigns
                <InfoTooltip 
                  content="Mention past campaigns that performed well. This helps the AI understand what works best for your audience and replicate success."
                  className="ml-0.5 sm:ml-1 md:ml-2"
                />
              </label>
              <textarea
                value={formData.successful_campaigns}
                onChange={(e) => handleInputChange('successful_campaigns', e.target.value)}
                rows={4}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="Describe any successful marketing campaigns you've run in the past..."
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">
                Upload Post Media That Worked Well (Optional - Max 4)
                <InfoTooltip 
                  content="Upload up to 4 post media files from past campaigns that performed well. This helps Emily understand what visual content resonates with your audience."
                  className="ml-0.5 sm:ml-1 md:ml-2"
                />
              </label>
              <MultiMediaUpload
                value={formData.successful_content_urls || []}
                onUploadSuccess={handleMediaUpload}
                onError={handleMediaError}
                className="max-w-2xl"
                maxFiles={4}
              />
              {mediaError && (
                <div className="text-red-600 text-xs sm:text-sm mt-2">{mediaError}</div>
              )}
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Hashtags That Work Well *</label>
              <textarea
                value={formData.hashtags_that_work_well}
                onChange={(e) => handleInputChange('hashtags_that_work_well', e.target.value)}
                rows={3}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="List hashtags that have performed well for your brand..."
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Customer Pain Points *</label>
              <textarea
                value={formData.customer_pain_points}
                onChange={(e) => handleInputChange('customer_pain_points', e.target.value)}
                rows={4}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="What problems or pain points do your customers face that your business solves?"
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Typical Customer Journey *</label>
              <textarea
                value={formData.typical_customer_journey}
                onChange={(e) => handleInputChange('typical_customer_journey', e.target.value)}
                rows={4}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="Describe how customers typically discover, evaluate, and purchase from your business..."
              />
            </div>
          </div>
        )

      case 9:
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Automation Level *</label>
              <select
                value={formData.automation_level}
                onChange={(e) => handleInputChange('automation_level', e.target.value)}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                required
              >
                <option value="">Select your automation level</option>
                {automationLevels.map(level => (
                  <option key={level.value} value={level.value}>
                    {level.label} - {level.description}
                  </option>
                ))}
              </select>
            </div>

            {/* Platform-specific tone settings as table */}
            <div className="space-y-4">
              <h4 className="text-lg font-medium text-gray-800">Platform-Specific Tone Settings</h4>
              <p className="text-sm text-gray-600">Customize your brand tone for different platforms</p>
              
              <div className="overflow-x-auto">
                <table className="min-w-full border border-gray-200 rounded-lg">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Platform</th>
                      <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Tone</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {['Instagram', 'Facebook', 'LinkedIn (Personal)', 'YouTube'].map(platform => (
                      <tr key={platform}>
                        <td className="px-4 py-2 text-sm text-gray-700">{platform}</td>
                        <td className="px-4 py-2">
                          <div className="flex flex-wrap gap-4">
                          {brandTones.map(tone => (
                              <label key={`${platform.toLowerCase()}-${tone}`} className="flex items-center space-x-2 cursor-pointer hover:bg-gray-50 px-2 py-1 rounded">
                              <input
                                type="checkbox"
                                  value={tone}
                                  checked={formData[`platform_tone_${platform.toLowerCase()}`]?.includes(tone) || false}
                                  onChange={(e) => {
                                    const currentTones = formData[`platform_tone_${platform.toLowerCase()}`] || []
                                    if (e.target.checked) {
                                      // Add tone if checked
                                      const newTones = [...currentTones, tone]
                                      handleInputChange(`platform_tone_${platform.toLowerCase()}`, newTones)
                                    } else {
                                      // Remove tone if unchecked
                                      const newTones = currentTones.filter(t => t !== tone)
                                      handleInputChange(`platform_tone_${platform.toLowerCase()}`, newTones)
                                    }
                                  }}
                                  className="text-pink-600 focus:ring-pink-500 rounded"
                              />
                              <span className="text-sm text-gray-700">{tone}</span>
                            </label>
                          ))}
                        </div>
                      </td>
                    </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )

      case 10:
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <p className="text-gray-600">Please review all your information before submitting your profile.</p>
            
            <div className="bg-gray-50 p-6 rounded-lg">
              <h4 className="text-lg font-medium text-gray-800 mb-4">Profile Summary</h4>
              <div className="space-y-2 text-sm">
                <div><span className="font-medium">Business Name:</span> {formData.business_name || 'Not provided'}</div>
                <div><span className="font-medium">Business Type:</span> {formData.business_type?.join(', ') || 'Not provided'}</div>
                <div><span className="font-medium">Industry:</span> {formData.industry?.join(', ') || 'Not provided'}</div>
                <div><span className="font-medium">Brand Voice:</span> {formData.brand_voice || 'Not provided'}</div>
                <div><span className="font-medium">Brand Tone:</span> {formData.brand_tone || 'Not provided'}</div>
                <div><span className="font-medium">Social Platforms:</span> {formData.social_media_platforms?.join(', ') || 'Not provided'}</div>
                <div><span className="font-medium">Primary Goals:</span> {formData.primary_goals?.join(', ') || 'Not provided'}</div>
                <div><span className="font-medium">Content Types:</span> {formData.preferred_content_types?.join(', ') || 'Not provided'}</div>
                <div><span className="font-medium">Market Position:</span> {formData.market_position || 'Not provided'}</div>
                <div><span className="font-medium">Automation Level:</span> {formData.automation_level || 'Not provided'}</div>
              </div>
            </div>
          </div>
        )

      default:
        return (
          <div className="text-center py-8">
            <p className="text-gray-600">Step {currentStep + 1} - {steps[currentStep]}</p>
            <p className="text-sm text-gray-500 mt-2">This step is being implemented. Please check back soon!</p>
          </div>
        )
    }
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
          
          {/* Step Indicators - Hidden in edit mode */}
          {!isEditMode && (
            <div className="flex justify-between mt-4">
              {steps.map((step, index) => (
                <div key={index} className="flex flex-col items-center">
                  <div 
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-all duration-200 ${
                      index === currentStep
                        ? 'bg-pink-600 text-white shadow-lg'
                        : isStepCompleted(index)
                        ? 'bg-green-500 text-white'
                        : isStepAccessible(index)
                        ? 'bg-gray-300 text-gray-600 hover:bg-gray-400 cursor-pointer'
                        : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    }`}
                    title={
                      index === currentStep
                        ? `Current: ${step}`
                        : isStepCompleted(index)
                        ? `Completed: ${step}`
                        : isStepAccessible(index)
                        ? `Click to go to: ${step}`
                        : `Locked: Complete previous steps to unlock ${step}`
                    }
                    onClick={() => {
                      if (isStepAccessible(index)) {
                        setCurrentStep(index)
                        if (onStepChange) {
                          onStepChange(index)
                        }
                      }
                    }}
                  >
                    {isStepCompleted(index) ? (
                      <Check className="w-4 h-4" />
                    ) : (
                      index + 1
                    )}
                  </div>
                  <span className={`text-xs mt-1 text-center max-w-16 ${
                    index === currentStep
                      ? 'text-pink-600 font-medium'
                      : isStepCompleted(index)
                      ? 'text-green-600'
                      : isStepAccessible(index)
                      ? 'text-gray-600'
                      : 'text-gray-400'
                  }`}>
                    {step.split(' ')[0]}
                  </span>
                </div>
              ))}
            </div>
          )}
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
          {currentStep === 3 && "What's your current online presence?"}
          {currentStep === 4 && "What are your digital marketing goals?"}
          {currentStep === 5 && "What's your content strategy?"}
          {currentStep === 6 && "How do you fit in the market?"}
          {currentStep === 7 && "What campaigns are you planning?"}
          {currentStep === 8 && "What's worked well for you?"}
          {currentStep === 9 && "How automated should your marketing be?"}
          {currentStep === 10 && "Review everything before we start"}
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      {/* Step Lock Warning */}
      {!isEditMode && !isStepAccessible(currentStep) && (
        <div className="bg-amber-50 border border-amber-200 text-amber-600 px-4 py-3 rounded-lg mb-6">
          <div className="flex items-center">
            <X className="w-5 h-5 text-amber-400 mr-2" />
            <p>
              This step is locked. Please complete the previous steps to continue.
            </p>
          </div>
        </div>
      )}

      <div className="mb-8 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100 hover:scrollbar-thumb-gray-400">
      {renderStep()}
      </div>

      {/* Navigation */}
      <div className="flex justify-between items-center pt-3 sm:pt-4 md:pt-6 mt-4 sm:mt-6 md:mt-8 border-t border-gray-200 bg-white sticky bottom-0">
        <div className="flex items-center space-x-2 sm:space-x-3 md:space-x-4">
        <button
          onClick={prevStep}
          disabled={currentStep === 0}
          className="flex items-center px-3 sm:px-4 md:px-6 py-2 sm:py-2.5 md:py-3 bg-gray-500 text-white rounded-md sm:rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-600 transition-colors text-xs sm:text-sm md:text-base"
        >
          <ArrowLeft className="w-3 h-3 sm:w-3.5 sm:h-3.5 md:w-4 md:h-4 mr-1 sm:mr-1.5 md:mr-2" />
          <span className="hidden sm:inline">Previous</span>
          <span className="sm:hidden">Prev</span>
        </button>
          
          {/* Data Persistence Indicator */}
          {!isEditMode && (
            <div className="flex items-center text-[10px] sm:text-xs md:text-sm text-gray-500">
              <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 bg-green-500 rounded-full mr-1 sm:mr-1.5 md:mr-2 animate-pulse"></div>
              <span className="hidden sm:inline">Auto-saved</span>
              <span className="sm:hidden">Saved</span>
            </div>
          )}
        </div>

        <div className="flex items-center space-x-2 sm:space-x-3 md:space-x-4">
          {/* Step Status - Hidden in edit mode */}
          {!isEditMode && (
            <div className="text-xs sm:text-sm text-gray-600">
              {isStepCompleted(currentStep) ? (
                <span className="flex items-center text-green-600">
                  <Check className="w-3 h-3 sm:w-3.5 sm:h-3.5 md:w-4 md:h-4 mr-0.5 sm:mr-1" />
                  <span className="hidden sm:inline">Step Complete</span>
                  <span className="sm:hidden">✓</span>
                </span>
              ) : (
                <span className="text-amber-600 hidden sm:inline">Step Incomplete</span>
              )}
            </div>
          )}

          {/* Save Success Indicator - Only in edit mode */}
          {isEditMode && saveSuccess && (
            <div className="text-xs sm:text-sm text-green-600 flex items-center">
              <Check className="w-3 h-3 sm:w-3.5 sm:h-3.5 md:w-4 md:h-4 mr-0.5 sm:mr-1" />
              <span className="hidden sm:inline">Changes Saved Successfully!</span>
              <span className="sm:hidden">Saved!</span>
            </div>
          )}

        {currentStep === steps.length - 1 ? (
          <button
            onClick={handleSubmit}
              disabled={isSubmitting || (!isEditMode && !isStepCompleted(currentStep))}
            className="flex items-center px-3 sm:px-4 md:px-6 py-2 sm:py-2.5 md:py-3 bg-gradient-to-r from-pink-500 to-purple-600 text-white rounded-md sm:rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:from-pink-600 hover:to-purple-700 transition-all text-xs sm:text-sm md:text-base"
          >
            {isSubmitting ? (
              <>
                <div className="animate-spin rounded-full h-3 w-3 sm:h-3.5 sm:w-3.5 md:h-4 md:w-4 border-b-2 border-white mr-1 sm:mr-1.5 md:mr-2"></div>
                <span className="hidden sm:inline">{isEditMode ? 'Updating...' : 'Submitting...'}</span>
                <span className="sm:hidden">{isEditMode ? 'Updating' : 'Submitting'}</span>
              </>
            ) : (
              <>
                <Check className="w-3 h-3 sm:w-3.5 sm:h-3.5 md:w-4 md:h-4 mr-1 sm:mr-1.5 md:mr-2" />
                <span className="hidden lg:inline">{isEditMode ? 'Update Profile' : 'Complete Onboarding'}</span>
                <span className="hidden sm:inline lg:hidden">{isEditMode ? 'Update' : 'Complete'}</span>
                <span className="sm:hidden">Done</span>
              </>
            )}
          </button>
        ) : isEditMode ? (
          // In edit mode, show Save button for each step
          <div className="flex items-center space-x-1.5 sm:space-x-2 md:space-x-3">
            <button
              onClick={handleSaveStep}
              disabled={isSaving}
              className="flex items-center px-3 sm:px-4 md:px-6 py-2 sm:py-2.5 md:py-3 bg-gradient-to-r from-pink-500 to-purple-600 text-white rounded-md sm:rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:from-pink-600 hover:to-purple-700 transition-all text-xs sm:text-sm md:text-base"
            >
              {isSaving ? (
                <>
                  <div className="animate-spin rounded-full h-3 w-3 sm:h-3.5 sm:w-3.5 md:h-4 md:w-4 border-b-2 border-white mr-1 sm:mr-1.5 md:mr-2"></div>
                  <span className="hidden sm:inline">Saving...</span>
                  <span className="sm:hidden">Saving</span>
                </>
              ) : (
                <>
                  <Save className="w-3 h-3 sm:w-3.5 sm:h-3.5 md:w-4 md:h-4 mr-1 sm:mr-1.5 md:mr-2" />
                  <span className="hidden sm:inline">Save</span>
                  <span className="sm:hidden">Save</span>
                </>
              )}
            </button>
            <button
              onClick={nextStep}
              className="flex items-center px-3 sm:px-4 md:px-6 py-2 sm:py-2.5 md:py-3 bg-gradient-to-r from-pink-500 to-purple-600 text-white rounded-md sm:rounded-lg hover:from-pink-600 hover:to-purple-700 transition-all text-xs sm:text-sm md:text-base"
            >
              <span className="hidden sm:inline">Next</span>
              <span className="sm:hidden">Next</span>
              <ArrowRight className="w-3 h-3 sm:w-3.5 sm:h-3.5 md:w-4 md:h-4 ml-1 sm:ml-1.5 md:ml-2" />
            </button>
          </div>
        ) : (
          <button
            onClick={nextStep}
              disabled={!isEditMode && !isStepAccessible(currentStep + 1)}
              className="flex items-center px-3 sm:px-4 md:px-6 py-2 sm:py-2.5 md:py-3 bg-gradient-to-r from-pink-500 to-purple-600 text-white rounded-md sm:rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:from-pink-600 hover:to-purple-700 transition-all text-xs sm:text-sm md:text-base"
          >
            <span className="hidden sm:inline">Next</span>
            <span className="sm:hidden">Next</span>
            <ArrowRight className="w-3 h-3 sm:w-3.5 sm:h-3.5 md:w-4 md:h-4 ml-1 sm:ml-1.5 md:ml-2" />
          </button>
        )}
        </div>
      </div>
    </div>
  )
})

export default OnboardingForm
