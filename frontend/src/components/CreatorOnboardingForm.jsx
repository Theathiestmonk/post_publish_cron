import React, { useState, useEffect, forwardRef, useImperativeHandle } from 'react'
import { onboardingAPI } from '../services/onboarding'
import { ArrowLeft, ArrowRight, Check, X, Save } from 'lucide-react'
import LogoUpload from './LogoUpload'
import MediaUpload from './MediaUpload'
import MultiMediaUpload from './MultiMediaUpload'
import InfoTooltip from './InfoTooltip'
import DualRangeSlider from './DualRangeSlider'

const CreatorOnboardingForm = forwardRef(({ 
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
    // Step 1: Creator Basics
    creator_name: '',
    creator_type: '',
    primary_niche: '',
    
    // Step 2: Brand & Contact
    profile_photo_url: '',
    brand_tone: '',
    brand_colors: [],
    primary_color: '',
    secondary_color: '',
    location_city: '',
    location_state: '',
    location_country: '',
    phone_number: '',
    
    // Step 3: Audience & Brand Story
    creator_bio: '',
    unique_value_proposition: '',
    target_audience_age_groups: [],
    target_audience_age_min: 16,
    target_audience_age_max: 90,
    target_audience_gender: 'all',
    audience_lifestyle_interests: [],
    audience_behavior: [],
    
    // Step 4: Platforms & Current Presence
    active_platforms: [],
    current_online_presence_status: '',
    
    // Step 5: Content Strategy & Goals
    primary_goals: [],
    preferred_content_types: [],
    content_themes: [],
    best_time_to_post: [],
    
    // Step 6: Performance Insights & Competition
    best_performing_content_urls: [],
    hashtags_that_work_well: '',
    competitors: '',
    biggest_challenges: [],
    
    // Step 7: Monetization, Workflow & Automation
    monetization_sources: [],
    automation_level: '',
    platform_specific_tone: {},
    
    // Metadata
    onboarding_type: 'creator'
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)
  const [profilePhotoUrl, setProfilePhotoUrl] = useState('')
  const [profilePhotoError, setProfilePhotoError] = useState('')
  const [mediaUrl, setMediaUrl] = useState('')
  const [mediaError, setMediaError] = useState('')
  const [extractedColors, setExtractedColors] = useState([])
  const [dataLoaded, setDataLoaded] = useState(false) // Track if localStorage data has been loaded

  // Steps array
  const steps = [
    'Creator Basics',
    'Brand & Contact',
    'Audience & Brand Story',
    'Platforms & Current Presence',
    'Content Strategy & Goals',
    'Performance Insights & Competition',
    'Monetization, Workflow & Automation',
    'Review & Submit'
  ]

  // Creator types
  const creatorTypes = [
    'Fashion & Beauty',
    'Lifestyle & Wellness',
    'Fitness & Sports',
    'Entertainment & Comedy',
    'Tech & Gadgets',
    'Business, Finance & Entrepreneurship',
    'Food & Cooking',
    'Travel & Adventure',
    'Gaming & Esports',
    'Art, Design & Creativity',
    'Parenting & Family',
    'Other / Unique Category',
    'Not Sure Yet'
  ]

  // Brand tones for creators
  const brandTones = [
    'Friendly',
    'Bold',
    'Professional',
    'Humorous',
    'Inspirational',
    'Relatable',
    'Luxury',
    'Minimalist',
    'High-Energy'
  ]

  // Audience lifestyle interests
  const audienceLifestyleInterests = [
    'Students',
    'Working Professionals',
    'Parents & Family Audience',
    'Fitness & Wellness Enthusiasts',
    'Tech Lovers',
    'Fashion & Beauty Audience',
    'Small Business Owners / Entrepreneurs',
    'Creatives & Artists',
    'Gamers & Entertainment Audience',
    'Travel & Adventure Seekers',
    'Lifestyle Audience (General)',
    'Creators / Influencers',
    'Other / Mixed Audience'
  ]

  // Audience behavior
  const audienceBehavior = [
    'Trend-Followers',
    'Knowledge Seekers',
    'Entertainment-First Viewers',
    'Short-Form Consumers',
    'Long-Form Consumers',
    'Community-Driven Audiences',
    'Casual Scrollers',
    'Value Hunters',
    'Not Sure',
    'Other'
  ]

  // Active platforms
  const activePlatforms = [
    'Instagram',
    'YouTube',
    'LinkedIn (Personal)',
    'Facebook',
    'Google',
    'Website'
  ]

  // Current online presence status
  const currentPresenceStatus = [
    'Growing rapidly',
    'Stable',
    'Needs improvement',
    'Starting out'
  ]

  // Primary goals
  const primaryGoals = [
    'Grow followers',
    'Increase engagement',
    'Build a personal brand',
    'Monetize content',
    'Sell digital products',
    'Get brand deals',
    'Drive traffic to YouTube',
    'Community building'
  ]

  // Preferred content types
  const preferredContentTypes = [
    'Short videos',
    'Reels/Shorts',
    'Long-form video',
    'Photo posts',
    'Carousels',
    'Podcast clips',
    'Memes',
    'Educational posts',
    'Stories'
  ]

  // Content themes
  const contentThemes = [
    'Educational / How-To',
    'Entertainment / Fun',
    'Lifestyle / Daily Life',
    'Motivation / Inspiration',
    'Product / Service Reviews',
    'Behind the Scenes',
    'Trends / Viral Content',
    'Community / Collaboration',
    'Tips / Hacks / Quick Wins',
    'Other'
  ]


  // Best time to post
  const postingTimes = [
    'Early Morning (6 AM – 9 AM)',
    'Mid-Morning (9 AM – 12 PM)',
    'Afternoon (12 PM – 3 PM)',
    'Late Afternoon (3 PM – 6 PM)',
    'Evening (6 PM – 9 PM)',
    'Late Night (9 PM – 12 AM)',
    'Weekdays',
    'Weekends',
    'Not sure — let Emily analyze and suggest',
    'Other'
  ]

  // Biggest challenges
  const biggestChallenges = [
    'Low engagement',
    'Inconsistent posting',
    'No content ideas',
    'Poor editing',
    'Not growing audience',
    'Weak personal branding',
    'Finding collaborations'
  ]

  // Monetization sources
  const monetizationSources = [
    'Brand deals',
    'Affiliate marketing',
    'Courses/eBooks',
    'YouTube earnings',
    'Coaching',
    'Not monetizing yet'
  ]

  // Automation levels
  const automationLevels = [
    { 
      value: 'Fully automated content + posting', 
      label: 'Fully Automated', 
      description: 'Emily handles everything automatically' 
    },
    { 
      value: 'Content ideas + scripts only', 
      label: 'Content Ideas Only', 
      description: 'Emily suggests content ideas and scripts' 
    },
    { 
      value: 'Caption writing only', 
      label: 'Caption Writing', 
      description: 'Emily writes captions only' 
    },
    { 
      value: 'Hashtag + SEO optimization', 
      label: 'Hashtag & SEO', 
      description: 'Emily optimizes hashtags and SEO' 
    },
    { 
      value: 'Full AI teammate mode (Emily handles everything)', 
      label: 'Full AI Teammate', 
      description: 'Emily handles everything as your AI teammate' 
    }
  ]

  // State for "Other" input fields
  const [otherInputs, setOtherInputs] = useState({
    creatorTypeOther: '',
    primaryNicheOther: '',
    activePlatformOther: '',
    goalOther: '',
    contentTypeOther: '',
    contentThemeOther: '',
    postingTimeOther: '',
    challengeOther: '',
    monetizationOther: '',
    audienceLifestyleOther: '',
    audienceBehaviorOther: ''
  })

  // State for expandable cards
  const [expandedCards, setExpandedCards] = useState({
    lifestyleInterests: false,
    audienceBehavior: false
  })

  // Expose methods to parent component
  useImperativeHandle(ref, () => ({
    goToStep: (stepIndex) => {
      if (stepIndex >= 0 && stepIndex < steps.length) {
        if (isEditMode) {
          setCurrentStep(stepIndex)
          if (onStepChange) {
            onStepChange(stepIndex)
          }
        } else {
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
        creator_name: '',
        creator_type: '',
        primary_niche: '',
        profile_photo_url: '',
        brand_tone: [],
        brand_colors: [],
        primary_color: '',
        secondary_color: '',
        location_city: '',
        location_state: '',
        location_country: '',
        phone_number: '',
        creator_bio: '',
        unique_value_proposition: '',
        target_audience_age_groups: [],
        target_audience_age_min: 16,
        target_audience_age_max: 90,
        target_audience_gender: 'all',
        audience_lifestyle_interests: [],
        audience_behavior: [],
        active_platforms: [],
        current_online_presence_status: '',
        primary_goals: [],
        preferred_content_types: [],
        content_themes: [],
        best_time_to_post: [],
        best_performing_content_urls: [],
        hashtags_that_work_well: '',
        competitors: '',
        biggest_challenges: [],
        monetization_sources: [],
        automation_level: '',
        platform_specific_tone: {},
        onboarding_type: 'creator'
      })
      setCurrentStep(0)
      setCompletedSteps(new Set())
      localStorage.removeItem('creator_onboarding_form_data')
      localStorage.removeItem('creator_onboarding_current_step')
      localStorage.removeItem('creator_onboarding_completed_steps')
    }
  }))

  // Load saved data from localStorage on component mount - MUST run first
  useEffect(() => {
    if (!isEditMode) {
      console.log('Loading creator form data from localStorage...')
      const savedFormData = localStorage.getItem('creator_onboarding_form_data')
      const savedCurrentStep = localStorage.getItem('creator_onboarding_current_step')
      const savedCompletedSteps = localStorage.getItem('creator_onboarding_completed_steps')
      
      if (savedFormData) {
        try {
          const parsedData = JSON.parse(savedFormData)
          console.log('Loaded saved form data from localStorage:', parsedData)
          setFormData(prev => {
            // Merge with defaults to ensure all fields exist
            const merged = { ...prev, ...parsedData }
            
            // Ensure all array fields are arrays (brand_tone is now a string, not an array)
            const arrayFields = [
              'brand_colors', 'target_audience_age_groups',
              'audience_lifestyle_interests', 'audience_behavior', 'active_platforms',
              'primary_goals', 'preferred_content_types', 'content_themes',
              'best_time_to_post', 'best_performing_content_urls', 'biggest_challenges',
              'monetization_sources'
            ]
            
            arrayFields.forEach(field => {
              if (!Array.isArray(merged[field])) {
                merged[field] = []
              }
            })
            
            // Ensure default values for age and gender
            if (!merged.target_audience_age_min) {
              merged.target_audience_age_min = 16
            }
            if (!merged.target_audience_age_max) {
              merged.target_audience_age_max = 90
            }
            if (!merged.target_audience_gender) {
              merged.target_audience_gender = 'all'
            }
            
            // Migrate brand_tone from array to string (for backward compatibility)
            if (Array.isArray(merged.brand_tone)) {
              // If it's an array, take the first value or convert to empty string
              merged.brand_tone = merged.brand_tone.length > 0 ? merged.brand_tone[0] : ''
            } else if (merged.brand_tone === null || merged.brand_tone === undefined) {
              merged.brand_tone = ''
            }
            
            return merged
          })
          
          // Set profile photo if exists
          if (parsedData.profile_photo_url) {
            setProfilePhotoUrl(parsedData.profile_photo_url)
          }
          
          // Set media URL if exists
          if (parsedData.best_performing_content_urls && Array.isArray(parsedData.best_performing_content_urls) && parsedData.best_performing_content_urls.length > 0) {
            setMediaUrl(parsedData.best_performing_content_urls[0])
          }
        } catch (error) {
          console.error('Error parsing saved form data:', error)
        }
      } else {
        console.log('No saved form data found in localStorage')
      }
      
      if (savedCurrentStep) {
        const step = parseInt(savedCurrentStep, 10)
        console.log('Loaded saved current step:', step)
        if (step >= 0 && step < steps.length) {
          setCurrentStep(step)
        }
      }
      
      if (savedCompletedSteps) {
        try {
          const parsedSteps = JSON.parse(savedCompletedSteps)
          console.log('Loaded completed steps:', parsedSteps)
          setCompletedSteps(new Set(parsedSteps))
        } catch (error) {
          console.error('Error parsing completed steps:', error)
        }
      }
      
      // Mark data as loaded
      setDataLoaded(true)
    } else {
      // In edit mode, mark as loaded immediately
      setDataLoaded(true)
    }
  }, [isEditMode, steps.length]) // Run on mount and when isEditMode or steps.length changes

  // Load initial data if provided (only in edit mode or if no localStorage data exists)
  useEffect(() => {
    if (initialData && isEditMode) {
      console.log('Loading initial data in edit mode:', initialData)
      setFormData(prev => {
        const updatedData = { ...prev, ...initialData }
        
        // Ensure all array fields are arrays (brand_tone is now a string, not an array)
        const arrayFields = [
          'brand_colors', 'target_audience_age_groups',
          'audience_lifestyle_interests', 'audience_behavior', 'active_platforms',
          'primary_goals', 'preferred_content_types', 'content_themes',
          'best_time_to_post', 'best_performing_content_urls', 'biggest_challenges',
          'monetization_sources'
        ]
        
        // Migrate brand_tone from array to string (for backward compatibility)
        if (Array.isArray(updatedData.brand_tone)) {
          updatedData.brand_tone = updatedData.brand_tone.length > 0 ? updatedData.brand_tone[0] : ''
        } else if (updatedData.brand_tone === null || updatedData.brand_tone === undefined) {
          updatedData.brand_tone = ''
        }
        
        if (!updatedData.target_audience_age_min) {
          updatedData.target_audience_age_min = 16
        }
        if (!updatedData.target_audience_age_max) {
          updatedData.target_audience_age_max = 90
        }
        if (!updatedData.target_audience_gender) {
          updatedData.target_audience_gender = 'all'
        }
        
        arrayFields.forEach(field => {
          if (!Array.isArray(updatedData[field])) {
            updatedData[field] = []
          }
        })
        
        return updatedData
      })
      
      if (initialData.profile_photo_url) {
        setProfilePhotoUrl(initialData.profile_photo_url)
      }
      
      if (initialData.best_performing_content_urls && Array.isArray(initialData.best_performing_content_urls) && initialData.best_performing_content_urls.length > 0) {
        setMediaUrl(initialData.best_performing_content_urls[0])
      }
    }
  }, [initialData, isEditMode])

  // Notify parent of step changes
  useEffect(() => {
    if (onStepChange) {
      onStepChange(currentStep)
    }
    
    // Automatically mark review step (last step) as complete when reached
    if (currentStep === steps.length - 1) {
      setCompletedSteps(prev => new Set([...prev, currentStep]))
    }
  }, [currentStep, onStepChange, steps.length])

  // Save form data to localStorage whenever it changes (only after data is loaded)
  useEffect(() => {
    if (!isEditMode && dataLoaded) {
      console.log('Saving creator form data to localStorage:', formData)
      localStorage.setItem('creator_onboarding_form_data', JSON.stringify(formData))
    }
  }, [formData, isEditMode, dataLoaded])

  // Save current step to localStorage whenever it changes (only after data is loaded)
  useEffect(() => {
    if (!isEditMode && dataLoaded) {
      console.log('Saving creator current step to localStorage:', currentStep)
      localStorage.setItem('creator_onboarding_current_step', currentStep.toString())
    }
  }, [currentStep, isEditMode, dataLoaded])

  // Save completed steps to localStorage whenever it changes (only after data is loaded)
  useEffect(() => {
    if (!isEditMode && dataLoaded) {
      console.log('Saving creator completed steps to localStorage:', [...completedSteps])
      localStorage.setItem('creator_onboarding_completed_steps', JSON.stringify([...completedSteps]))
    }
  }, [completedSteps, isEditMode, dataLoaded])

  // Color extraction handling
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

  // Extract colors from profile photo if it already exists
  useEffect(() => {
    const extractColorsFromExistingPhoto = async () => {
      if (formData.profile_photo_url && formData.profile_photo_url.trim() && extractedColors.length === 0) {
        try {
          console.log('Extracting colors from existing profile photo:', formData.profile_photo_url)
          const { mediaAPI } = await import('../services/api')
          const colorResponse = await mediaAPI.extractColorsFromLogo(formData.profile_photo_url)
          console.log('Color extraction response:', colorResponse.data)
          if (colorResponse.data && colorResponse.data.colors) {
            handleColorsExtracted(colorResponse.data.colors)
          }
        } catch (error) {
          console.warn('Failed to extract colors from existing profile photo:', error)
        }
      }
    }
    extractColorsFromExistingPhoto()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData.profile_photo_url])

  // Profile photo handling
  const handleProfilePhotoUpload = (url) => {
    setProfilePhotoUrl(url)
    setProfilePhotoError('')
    handleInputChange('profile_photo_url', url)
  }

  const handleProfilePhotoError = (error) => {
    setProfilePhotoError(error)
  }

  // Media upload handling
  const handleMediaUpload = (files) => {
    if (Array.isArray(files)) {
      const urls = files.map(file => file.url || file).filter(Boolean)
      handleInputChange('best_performing_content_urls', urls)
      setMediaError('')
      if (urls.length > 0) {
        setMediaUrl(urls[0])
      }
    } else if (files && files.url) {
      handleInputChange('best_performing_content_urls', [files.url])
      setMediaUrl(files.url)
      setMediaError('')
    }
  }

  const handleMediaError = (error) => {
    setMediaError(error || '')
  }

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }))
    setError('')
    
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
    
    if (onFormChange) {
      onFormChange()
    }
  }

  const handleOtherInputChange = (field, value) => {
    setOtherInputs(prev => ({
      ...prev,
      [field]: value
    }))
    
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
      case 0: // Creator Basics
        const nameValid = formData.creator_name && String(formData.creator_name).trim().length > 0
        let typeValid = formData.creator_type && String(formData.creator_type).trim().length > 0
        // If "Other" is selected, also check if the "Other" input is filled
        if (formData.creator_type === 'Other / Unique Category') {
          typeValid = typeValid && otherInputs.creatorTypeOther && String(otherInputs.creatorTypeOther).trim().length > 0
        }
        const nicheValid = formData.primary_niche && String(formData.primary_niche).trim().length > 0
        console.log('Step 0 validation:', { 
          nameValid, 
          typeValid, 
          nicheValid, 
          creator_name: formData.creator_name, 
          creator_type: formData.creator_type, 
          primary_niche: formData.primary_niche,
          creatorTypeOther: otherInputs.creatorTypeOther
        })
        return nameValid && typeValid && nicheValid
      case 1: // Brand & Contact
        return formData.brand_tone && String(formData.brand_tone).trim().length > 0
      case 2: // Audience & Brand Story
        const ageMin = Number(formData.target_audience_age_min) || 0
        const ageMax = Number(formData.target_audience_age_max) || 0
        const hasAgeRange = ageMin >= 16 && ageMax >= ageMin && ageMax <= 90 && ageMin > 0 && ageMax > 0
        const hasGender = formData.target_audience_gender && ['all', 'men', 'women'].includes(formData.target_audience_gender)
        const hasBio = formData.creator_bio && String(formData.creator_bio).trim().length > 0
        const hasUVP = formData.unique_value_proposition && String(formData.unique_value_proposition).trim().length > 0
        
        return hasBio && hasUVP && hasAgeRange && hasGender
      case 3: // Platforms & Current Presence
        return true // Optional step
      case 4: // Content Strategy & Goals
        return (formData.primary_goals && formData.primary_goals.length > 0) &&
               (formData.preferred_content_types && formData.preferred_content_types.length > 0) &&
               (formData.content_themes && formData.content_themes.length > 0)
      case 5: // Performance Insights & Competition
        return true // Optional step
      case 6: // Monetization, Workflow & Automation
        return formData.automation_level
      case 7: // Review & Submit
        return true
      default:
        return true
    }
  }

  const nextStep = () => {
    console.log('Next button clicked, current step:', currentStep)
    console.log('Form data:', formData)
    const isValid = validateCurrentStep()
    console.log('Validation result:', isValid)
    
    if (isValid) {
      setCompletedSteps(prev => new Set([...prev, currentStep]))
      
      if (onStepComplete) {
        onStepComplete(currentStep)
      }
      
      setCurrentStep(prev => {
        const nextStep = Math.min(prev + 1, steps.length - 1)
        console.log('Moving to step:', nextStep)
        return nextStep
      })
      setError('')
    } else {
      console.log('Validation failed for step:', currentStep)
      setError('Please fill in all required fields before proceeding.')
    }
  }

  const prevStep = () => {
    setCurrentStep(prev => Math.max(prev - 1, 0))
    setError('')
  }

  const isStepAccessible = (stepIndex) => {
    if (isEditMode) return true
    
    if (stepIndex === 0) return true
    if (stepIndex <= Math.max(...completedSteps) + 1) return true
    return false
  }

  const isStepCompleted = (stepIndex) => {
    // Review step (last step) is always considered complete when reached
    if (stepIndex === steps.length - 1) {
      return true
    }
    return completedSteps.has(stepIndex)
  }

  const handleSaveStep = async () => {
    setIsSaving(true)
    setError('')
    setSaveSuccess(false)
    
    try {
      const submissionData = {
        ...formData,
        onboarding_completed: true,
        onboarding_type: 'creator'
      }

      console.log('Saving creator step data:', submissionData)
      const result = await onboardingAPI.updateProfile(submissionData)
      console.log('Save result:', result)
      
      setCompletedSteps(prev => new Set([...prev, currentStep]))
      if (onStepComplete) {
        onStepComplete(currentStep)
      }
      
      setSaveSuccess(true)
      setTimeout(() => setSaveSuccess(false), 2000)
      
      if (onSuccess) {
        onSuccess()
      }
      
    } catch (err) {
      console.error('Error saving step:', err)
      setError(err.message || 'Failed to save changes')
    } finally {
      setIsSaving(false)
    }
  }

  const handleSubmit = async () => {
    setIsSubmitting(true)
    setError('')

    try {
      // List of valid database fields for creator onboarding (based on migration)
      const validCreatorFields = [
        'onboarding_type',
        'onboarding_completed',
        // Step 1: Creator Basics
        'creator_name',
        'creator_type',
        'primary_niche',
        // Step 2: Brand & Contact
        'profile_photo_url',
        'brand_tone',
        'brand_colors',
        'primary_color',
        'secondary_color',
        'location_city',
        'location_state',
        'location_country',
        'phone_number',
        // Step 3: Audience & Brand Story
        'creator_bio',
        'unique_value_proposition',
        'target_audience_age_groups',
        'target_audience_age_min',
        'target_audience_age_max',
        'target_audience_gender',
        'audience_lifestyle_interests',
        'audience_behavior',
        // Step 4: Platforms & Current Presence
        'active_platforms',
        'current_online_presence_status',
        // Step 5: Content Strategy & Goals
        'primary_goals',
        'preferred_content_types',
        'content_themes',
        'best_time_to_post',
        // Step 6: Performance Insights & Competition
        'best_performing_content_urls',
        'hashtags_that_work_well',
        'competitors',
        'biggest_challenges',
        // Step 7: Monetization, Workflow & Automation
        'monetization_sources',
        'automation_level',
        'platform_specific_tone'
      ]

      // Filter formData to only include valid database fields
      const filteredFormData = Object.keys(formData)
        .filter(key => validCreatorFields.includes(key))
        .reduce((obj, key) => {
          // Only include non-empty values (except for arrays and objects which can be empty)
          const value = formData[key]
          if (value !== undefined && value !== null && value !== '') {
            obj[key] = value
          } else if (Array.isArray(value) || typeof value === 'object') {
            obj[key] = value
          }
          return obj
        }, {})

      // Prepare submission data with only valid fields
      const submissionData = {
        ...filteredFormData,
        onboarding_type: 'creator',
        onboarding_completed: true
      }

      console.log('Submitting creator profile data:', submissionData)

      if (isEditMode) {
        const result = await onboardingAPI.updateProfile(submissionData)
        console.log('Update result:', result)
        if (onSuccess) onSuccess()
      } else {
        const result = await onboardingAPI.submitOnboarding(submissionData)
        console.log('Submit result:', result)
        // Clear localStorage after successful submission
        localStorage.removeItem('creator_onboarding_form_data')
        localStorage.removeItem('creator_onboarding_current_step')
        localStorage.removeItem('creator_onboarding_completed_steps')
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
      case 0: // Creator Basics
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Creator/Brand Name *</label>
              <input
                type="text"
                value={formData.creator_name}
                onChange={(e) => handleInputChange('creator_name', e.target.value)}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="Enter your creator or brand name"
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Creator Type *</label>
              <select
                value={formData.creator_type}
                onChange={(e) => handleInputChange('creator_type', e.target.value)}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
              >
                <option value="">Select creator type</option>
                {creatorTypes.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
              {formData.creator_type === 'Other / Unique Category' && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.creatorTypeOther}
                    onChange={(e) => handleOtherInputChange('creatorTypeOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify your creator type"
                  />
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">
                Primary Niche *
                <InfoTooltip 
                  content="Describe your niche in 1–2 lines - the topic you create content around. Examples: tech reviews, beauty tips, fitness routines, travel content, comedy skits, finance education."
                  className="ml-0.5 sm:ml-1 md:ml-2"
                />
              </label>
              <textarea
                value={formData.primary_niche}
                onChange={(e) => handleInputChange('primary_niche', e.target.value)}
                rows={3}
                className="w-full px-2 sm:px-3 md:px-4 py-1.5 sm:py-2 md:py-2.5 lg:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="Describe your primary niche..."
              />
            </div>
          </div>
        )

      case 1: // Brand & Contact
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">
                Upload Profile Photo / Brand Logo (Optional)
              </label>
              <LogoUpload
                value={formData.profile_photo_url}
                onUploadSuccess={handleProfilePhotoUpload}
                onError={handleProfilePhotoError}
                onColorsExtracted={handleColorsExtracted}
                className="max-w-md"
              />
              {profilePhotoError && (
                <div className="text-red-600 text-sm mt-2">{profilePhotoError}</div>
              )}
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Brand Tone *</label>
              <select
                value={formData.brand_tone || ''}
                onChange={(e) => handleInputChange('brand_tone', e.target.value)}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
              >
                <option value="">Select brand tone</option>
                {brandTones.map(tone => (
                  <option key={tone} value={tone}>{tone}</option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <div className="flex items-center justify-between mb-1.5 sm:mb-2">
                  <label className="block text-xs sm:text-sm font-medium text-gray-700">Primary Color (Optional)</label>
                  {extractedColors && extractedColors.length > 0 && (
                    <div className="flex items-center space-x-1.5">
                      <span className="text-xs text-gray-500">Suggested:</span>
                      {extractedColors.slice(0, 4).map((color, index) => (
                        <button
                          key={index}
                          type="button"
                          onClick={() => handleColorSuggestionClick(color, 'primary')}
                          className="w-5 h-5 sm:w-6 sm:h-6 rounded border-2 border-gray-300 hover:border-pink-500 hover:scale-110 transition-all cursor-pointer shadow-sm"
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
                    className="w-12 sm:w-16 h-8 sm:h-10 border border-gray-300 rounded-md cursor-pointer"
                  />
                  <input
                    type="text"
                    value={formData.primary_color || ''}
                    onChange={(e) => handleInputChange('primary_color', e.target.value)}
                    className="flex-1 px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="#000000"
                  />
                </div>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1.5 sm:mb-2">
                  <label className="block text-xs sm:text-sm font-medium text-gray-700">Secondary Color (Optional)</label>
                  {extractedColors && extractedColors.length > 0 && (
                    <div className="flex items-center space-x-1.5">
                      <span className="text-xs text-gray-500">Suggested:</span>
                      {extractedColors.slice(0, 4).map((color, index) => (
                        <button
                          key={index}
                          type="button"
                          onClick={() => handleColorSuggestionClick(color, 'secondary')}
                          className="w-5 h-5 sm:w-6 sm:h-6 rounded border-2 border-gray-300 hover:border-pink-500 hover:scale-110 transition-all cursor-pointer shadow-sm"
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
                    className="w-12 sm:w-16 h-8 sm:h-10 border border-gray-300 rounded-md cursor-pointer"
                  />
                  <input
                    type="text"
                    value={formData.secondary_color || ''}
                    onChange={(e) => handleInputChange('secondary_color', e.target.value)}
                    className="flex-1 px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="#000000"
                  />
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">City</label>
                <input
                  type="text"
                  value={formData.location_city}
                  onChange={(e) => handleInputChange('location_city', e.target.value)}
                  className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                  placeholder="City"
                />
              </div>
              <div>
                <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">State</label>
                <input
                  type="text"
                  value={formData.location_state}
                  onChange={(e) => handleInputChange('location_state', e.target.value)}
                  className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                  placeholder="State"
                />
              </div>
              <div>
                <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Country</label>
                <input
                  type="text"
                  value={formData.location_country}
                  onChange={(e) => handleInputChange('location_country', e.target.value)}
                  className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                  placeholder="Country"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Phone Number (Optional)</label>
              <input
                type="tel"
                value={formData.phone_number}
                onChange={(e) => handleInputChange('phone_number', e.target.value)}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="Enter phone number"
              />
            </div>
          </div>
        )

      case 2: // Audience & Brand Story
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">
                Creator Bio / Description *
                <InfoTooltip 
                  content="Write a detailed intro about who you are, what kind of content you create, and what makes your style unique."
                  className="ml-0.5 sm:ml-1 md:ml-2"
                />
              </label>
              <textarea
                value={formData.creator_bio}
                onChange={(e) => handleInputChange('creator_bio', e.target.value)}
                rows={4}
                className="w-full px-2 sm:px-3 md:px-4 py-1.5 sm:py-2 md:py-2.5 lg:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="Tell us about yourself and your content..."
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">
                What makes you unique? *
                <InfoTooltip 
                  content="Describe your Unique Value Proposition"
                  className="ml-0.5 sm:ml-1 md:ml-2"
                />
              </label>
              <textarea
                value={formData.unique_value_proposition}
                onChange={(e) => handleInputChange('unique_value_proposition', e.target.value)}
                rows={3}
                className="w-full px-2 sm:px-3 md:px-4 py-1.5 sm:py-2 md:py-2.5 lg:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="What makes you unique?"
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Target Audience - Age Group *</label>
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

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Target Audience - Gender *</label>
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

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Audience Lifestyle and Interests</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {audienceLifestyleInterests.map(interest => (
                  <label key={interest} className="flex items-center space-x-1.5 sm:space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.audience_lifestyle_interests && formData.audience_lifestyle_interests.includes(interest)}
                      onChange={(e) => handleArrayChange('audience_lifestyle_interests', interest, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500 flex-shrink-0"
                    />
                    <span className="text-xs sm:text-sm text-gray-700 break-words">{interest}</span>
                  </label>
                ))}
              </div>
              {formData.audience_lifestyle_interests && formData.audience_lifestyle_interests.includes('Other / Mixed Audience') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.audienceLifestyleOther}
                    onChange={(e) => handleOtherInputChange('audienceLifestyleOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify"
                  />
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Audience Behavior</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {audienceBehavior.map(behavior => (
                  <label key={behavior} className="flex items-center space-x-1.5 sm:space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.audience_behavior && formData.audience_behavior.includes(behavior)}
                      onChange={(e) => handleArrayChange('audience_behavior', behavior, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500 flex-shrink-0"
                    />
                    <span className="text-xs sm:text-sm text-gray-700 break-words">{behavior}</span>
                  </label>
                ))}
              </div>
              {formData.audience_behavior && formData.audience_behavior.includes('Other') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.audienceBehaviorOther}
                    onChange={(e) => handleOtherInputChange('audienceBehaviorOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify"
                  />
                </div>
              )}
            </div>
          </div>
        )

      case 3: // Platforms & Current Presence
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Which platforms do you actively use?</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {activePlatforms.map(platform => (
                  <label key={platform} className="flex items-center space-x-1.5 sm:space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.active_platforms && formData.active_platforms.includes(platform)}
                      onChange={(e) => handleArrayChange('active_platforms', platform, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500 flex-shrink-0"
                    />
                    <span className="text-xs sm:text-sm text-gray-700 break-words">{platform}</span>
                  </label>
                ))}
              </div>
              {formData.active_platforms && formData.active_platforms.includes('Others') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.activePlatformOther}
                    onChange={(e) => handleOtherInputChange('activePlatformOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify"
                  />
                </div>
              )}
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Current Online Presence Status</label>
              <select
                value={formData.current_online_presence_status}
                onChange={(e) => handleInputChange('current_online_presence_status', e.target.value)}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
              >
                <option value="">Select status</option>
                {currentPresenceStatus.map(status => (
                  <option key={status} value={status}>{status}</option>
                ))}
              </select>
            </div>
          </div>
        )

      case 4: // Content Strategy & Goals
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Your primary goals as a creator (Select all that apply) *</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {primaryGoals.map(goal => (
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
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Preferred Content Types (Select all that apply) *</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {preferredContentTypes.map(type => (
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
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Content Themes (Select multiple) *</label>
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
              {formData.content_themes && formData.content_themes.includes('Other') && (
                <div className="mt-3">
                  <input
                    type="text"
                    value={otherInputs.contentThemeOther}
                    onChange={(e) => handleOtherInputChange('contentThemeOther', e.target.value)}
                    className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                    placeholder="Please specify"
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
                    placeholder="Please specify"
                  />
                </div>
              )}
            </div>
          </div>
        )

      case 5: // Performance Insights & Competition
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">
                Upload examples of your best-performing content (Optional)
              </label>
              <MultiMediaUpload
                value={formData.best_performing_content_urls || []}
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
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Hashtags that work well</label>
              <textarea
                value={formData.hashtags_that_work_well}
                onChange={(e) => handleInputChange('hashtags_that_work_well', e.target.value)}
                rows={3}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="List hashtags that have performed well..."
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Competitors (optional)</label>
              <textarea
                value={formData.competitors}
                onChange={(e) => handleInputChange('competitors', e.target.value)}
                rows={3}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                placeholder="List your main competitors..."
              />
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Biggest challenges you face as a creator</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {biggestChallenges.map(challenge => (
                  <label key={challenge} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.biggest_challenges && formData.biggest_challenges.includes(challenge)}
                      onChange={(e) => handleArrayChange('biggest_challenges', challenge, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500"
                    />
                    <span className="text-sm text-gray-700">{challenge}</span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )

      case 6: // Monetization, Workflow & Automation
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">Current monetization sources</label>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {monetizationSources.map(source => (
                  <label key={source} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={formData.monetization_sources && formData.monetization_sources.includes(source)}
                      onChange={(e) => handleArrayChange('monetization_sources', source, e.target.checked)}
                      className="rounded border-gray-300 text-pink-600 focus:ring-pink-500"
                    />
                    <span className="text-sm text-gray-700">{source}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-1.5 sm:mb-2">What level of automation do you want? *</label>
              <select
                value={formData.automation_level}
                onChange={(e) => handleInputChange('automation_level', e.target.value)}
                className="w-full px-2 sm:px-3 md:px-4 py-2 sm:py-2.5 md:py-3 text-xs sm:text-sm md:text-base border border-gray-300 rounded-md sm:rounded-lg focus:ring-2 focus:ring-pink-500 focus:border-transparent"
                required
              >
                <option value="">Select automation level</option>
                {automationLevels.map(level => (
                  <option key={level.value} value={level.value}>
                    {level.label} - {level.description}
                  </option>
                ))}
              </select>
            </div>
          </div>
        )

      case 7: // Review & Submit
        return (
          <div className="space-y-2.5 sm:space-y-3 md:space-y-4 lg:space-y-6">
            <p className="text-gray-600">Please review all your information before submitting your profile.</p>
            
            <div className="bg-gray-50 p-6 rounded-lg">
              <h4 className="text-lg font-medium text-gray-800 mb-4">Profile Summary</h4>
              <div className="space-y-2 text-sm">
                <div><span className="font-medium">Creator Name:</span> {formData.creator_name || 'Not provided'}</div>
                <div><span className="font-medium">Creator Type:</span> {formData.creator_type || 'Not provided'}</div>
                <div><span className="font-medium">Primary Niche:</span> {formData.primary_niche || 'Not provided'}</div>
                <div><span className="font-medium">Brand Tone:</span> {formData.brand_tone || 'Not provided'}</div>
                <div><span className="font-medium">Active Platforms:</span> {formData.active_platforms?.join(', ') || 'Not provided'}</div>
                <div><span className="font-medium">Primary Goals:</span> {formData.primary_goals?.join(', ') || 'Not provided'}</div>
                <div><span className="font-medium">Content Types:</span> {formData.preferred_content_types?.join(', ') || 'Not provided'}</div>
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
              {isEditMode ? 'Edit Creator Profile' : 'Complete Your Creator Profile'}
            </h2>
            <p className="text-gray-600">
              {isEditMode ? 'Update your creator information' : 'Let\'s get to know you better'}
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
          
          {/* Step Indicators */}
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
                    title={step}
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
          {currentStep === 0 && "Tell us about your creator basics"}
          {currentStep === 1 && "How should we represent your brand?"}
          {currentStep === 2 && "Who is your audience?"}
          {currentStep === 3 && "What platforms are you on?"}
          {currentStep === 4 && "What's your content strategy?"}
          {currentStep === 5 && "What's worked well for you?"}
          {currentStep === 6 && "How automated should your content be?"}
          {currentStep === 7 && "Review everything before we start"}
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-lg mb-6">
          {error}
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
          
          {!isEditMode && (
            <div className="flex items-center text-[10px] sm:text-xs md:text-sm text-gray-500">
              <div className="w-1.5 h-1.5 sm:w-2 sm:h-2 bg-green-500 rounded-full mr-1 sm:mr-1.5 md:mr-2 animate-pulse"></div>
              <span className="hidden sm:inline">Auto-saved</span>
              <span className="sm:hidden">Saved</span>
            </div>
          )}
        </div>

        <div className="flex items-center space-x-2 sm:space-x-3 md:space-x-4">
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
              type="button"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                console.log('Next button clicked')
                nextStep()
              }}
              className="flex items-center px-3 sm:px-4 md:px-6 py-2 sm:py-2.5 md:py-3 bg-gradient-to-r from-pink-500 to-purple-600 text-white rounded-md sm:rounded-lg hover:from-pink-600 hover:to-purple-700 transition-all text-xs sm:text-sm md:text-base cursor-pointer"
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

export default CreatorOnboardingForm

