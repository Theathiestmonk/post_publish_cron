import React, { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import SideNavbar from './SideNavbar'
import MobileNavigation from './MobileNavigation'
import EditProfileModal from './EditProfileModal'
import LogoUpload from './LogoUpload'
import ImageShowcaseModal from './ImageShowcaseModal'
import { User, Mail, Phone, MapPin, Calendar, Edit, Save, X, Loader2, Building2, Globe, Target, BarChart3, Megaphone, Settings, Image as ImageIcon } from 'lucide-react'

const Profile = () => {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editForm, setEditForm] = useState({})
  const [error, setError] = useState(null)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [logoUrl, setLogoUrl] = useState('')
  const [logoError, setLogoError] = useState('')
  const [isLogoModalOpen, setIsLogoModalOpen] = useState(false)

  useEffect(() => {
    fetchProfile()
  }, [])

  const fetchProfile = async () => {
    try {
      setLoading(true)
      const { data: { user } } = await supabase.auth.getUser()
      
      if (!user) {
        setError('User not authenticated')
        return
      }

      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', user.id)
        .single()

      if (error) {
        console.error('Error fetching profile:', error)
        setError('Failed to load profile')
        return
      }

      setProfile(data)
      setLogoUrl(data?.logo_url || '')
      setEditForm({
        // Basic Information
        name: data?.name || '',
        business_name: data?.business_name || '',
        business_type: data?.business_type || [],
        industry: data?.industry || [],
        business_description: data?.business_description || '',
        logo_url: data?.logo_url || '',
        target_audience: data?.target_audience || [],
        unique_value_proposition: data?.unique_value_proposition || '',
        
        // Detailed Target Audience
        target_audience_age_groups: data?.target_audience_age_groups || [],
        target_audience_life_stages: data?.target_audience_life_stages || [],
        target_audience_professional_types: data?.target_audience_professional_types || [],
        target_audience_lifestyle_interests: data?.target_audience_lifestyle_interests || [],
        target_audience_buyer_behavior: data?.target_audience_buyer_behavior || [],
        target_audience_other: data?.target_audience_other || '',
        
        // Brand & Contact
        brand_voice: data?.brand_voice || '',
        brand_tone: data?.brand_tone || '',
        primary_color: data?.primary_color || '',
        secondary_color: data?.secondary_color || '',
        additional_colors: Array.isArray(data?.additional_colors) ? data.additional_colors : [],
        website_url: data?.website_url || '',
        phone_number: data?.phone_number || '',
        street_address: data?.street_address || '',
        city: data?.city || '',
        state: data?.state || '',
        country: data?.country || '',
        timezone: data?.timezone || '',
        
        // Digital Marketing & Goals
        social_media_platforms: data?.social_media_platforms || [],
        primary_goals: data?.primary_goals || [],
        key_metrics_to_track: data?.key_metrics_to_track || [],
        
        // Content Strategy
        monthly_budget_range: data?.monthly_budget_range || '',
        preferred_content_types: data?.preferred_content_types || [],
        content_themes: data?.content_themes || [],
        
        // Market & Competition
        main_competitors: data?.main_competitors || '',
        market_position: data?.market_position || '',
        products_or_services: data?.products_or_services || '',
        
        // Campaign Planning
        important_launch_dates: data?.important_launch_dates || '',
        planned_promotions_or_campaigns: data?.planned_promotions_or_campaigns || '',
        top_performing_content_types: data?.top_performing_content_types || [],
        best_time_to_post: data?.best_time_to_post || [],
        
        // Performance & Customer
        successful_campaigns: data?.successful_campaigns || '',
        hashtags_that_work_well: data?.hashtags_that_work_well || '',
        customer_pain_points: data?.customer_pain_points || '',
        typical_customer_journey: data?.typical_customer_journey || '',
        
        // Automation & Platform
        automation_level: data?.automation_level || '',
        platform_specific_tone: data?.platform_specific_tone || {},
        current_presence: data?.current_presence || [],
        focus_areas: data?.focus_areas || [],
        platform_details: data?.platform_details || {},
        
        // Platform Links
        facebook_page_name: data?.facebook_page_name || '',
        instagram_profile_link: data?.instagram_profile_link || '',
        linkedin_company_link: data?.linkedin_company_link || '',
        youtube_channel_link: data?.youtube_channel_link || '',
        google_business_profile: data?.google_business_profile || '',
        
        // Platform-specific tone settings
        platform_tone_instagram: data?.platform_tone_instagram || [],
        platform_tone_facebook: data?.platform_tone_facebook || [],
        platform_tone_linkedin: data?.platform_tone_linkedin || [],
        platform_tone_youtube: data?.platform_tone_youtube || [],
        
        // "Other" Input Fields
        business_type_other: data?.business_type_other || '',
        industry_other: data?.industry_other || '',
        social_platform_other: data?.social_platform_other || '',
        goal_other: data?.goal_other || '',
        metric_other: data?.metric_other || '',
        content_type_other: data?.content_type_other || '',
        content_theme_other: data?.content_theme_other || '',
        posting_time_other: data?.posting_time_other || '',
        current_presence_other: data?.current_presence_other || '',
        top_performing_content_type_other: data?.top_performing_content_type_other || ''
      })
    } catch (err) {
      console.error('Error fetching profile:', err)
      setError('Failed to load profile')
    } finally {
      setLoading(false)
    }
  }

  const handleEdit = () => {
    setIsEditModalOpen(true)
  }

  const handleModalClose = () => {
    setIsEditModalOpen(false)
  }

  const handleModalSuccess = () => {
    setIsEditModalOpen(false)
    fetchProfile() // Refresh the profile data
  }

  const handleLogoUpload = (url) => {
    setLogoUrl(url)
    setLogoError('')
  }

  const handleLogoError = (error) => {
    setLogoError(error)
  }


  const handleCancel = () => {
    setEditing(false)
    setEditForm({
      // Basic Information
      name: profile?.name || '',
      business_name: profile?.business_name || '',
      business_type: profile?.business_type || [],
      industry: profile?.industry || [],
      business_description: profile?.business_description || '',
      target_audience: profile?.target_audience || [],
      unique_value_proposition: profile?.unique_value_proposition || '',
      
      // Detailed Target Audience
      target_audience_age_groups: profile?.target_audience_age_groups || [],
      target_audience_life_stages: profile?.target_audience_life_stages || [],
      target_audience_professional_types: profile?.target_audience_professional_types || [],
      target_audience_lifestyle_interests: profile?.target_audience_lifestyle_interests || [],
      target_audience_buyer_behavior: profile?.target_audience_buyer_behavior || [],
      target_audience_other: profile?.target_audience_other || '',
      
      // Brand & Contact
      brand_voice: profile?.brand_voice || '',
      brand_tone: profile?.brand_tone || '',
      website_url: profile?.website_url || '',
      phone_number: profile?.phone_number || '',
      street_address: profile?.street_address || '',
      city: profile?.city || '',
      state: profile?.state || '',
      country: profile?.country || '',
      timezone: profile?.timezone || '',
      
      // Digital Marketing & Goals
      social_media_platforms: profile?.social_media_platforms || [],
      primary_goals: profile?.primary_goals || [],
      key_metrics_to_track: profile?.key_metrics_to_track || [],
      
      // Content Strategy
      monthly_budget_range: profile?.monthly_budget_range || '',
      preferred_content_types: profile?.preferred_content_types || [],
      content_themes: profile?.content_themes || [],
      
      // Market & Competition
      main_competitors: profile?.main_competitors || '',
      market_position: profile?.market_position || '',
      products_or_services: profile?.products_or_services || '',
      
      // Campaign Planning
      important_launch_dates: profile?.important_launch_dates || '',
      planned_promotions_or_campaigns: profile?.planned_promotions_or_campaigns || '',
      top_performing_content_types: profile?.top_performing_content_types || [],
      best_time_to_post: profile?.best_time_to_post || [],
      
      // Performance & Customer
      successful_campaigns: profile?.successful_campaigns || '',
      hashtags_that_work_well: profile?.hashtags_that_work_well || '',
      customer_pain_points: profile?.customer_pain_points || '',
      typical_customer_journey: profile?.typical_customer_journey || '',
      
      // Automation & Platform
      automation_level: profile?.automation_level || '',
      platform_specific_tone: profile?.platform_specific_tone || {},
      current_presence: profile?.current_presence || [],
      focus_areas: profile?.focus_areas || [],
      platform_details: profile?.platform_details || {},
      
      // Platform Tone Settings
      platform_tone_instagram: profile?.platform_tone_instagram || [],
      platform_tone_facebook: profile?.platform_tone_facebook || [],
      platform_tone_linkedin: profile?.platform_tone_linkedin || [],
      platform_tone_youtube: profile?.platform_tone_youtube || [],

      // Platform Links
      facebook_page_name: profile?.facebook_page_name || '',
      instagram_profile_link: profile?.instagram_profile_link || '',
      linkedin_company_link: profile?.linkedin_company_link || '',
      youtube_channel_link: profile?.youtube_channel_link || '',
      google_business_profile: profile?.google_business_profile || '',
      
      // "Other" Input Fields
      business_type_other: profile?.business_type_other || '',
      industry_other: profile?.industry_other || '',
      social_platform_other: profile?.social_platform_other || '',
      goal_other: profile?.goal_other || '',
      metric_other: profile?.metric_other || '',
      content_type_other: profile?.content_type_other || '',
      content_theme_other: profile?.content_theme_other || '',
      posting_time_other: profile?.posting_time_other || '',
      current_presence_other: profile?.current_presence_other || '',
      top_performing_content_type_other: profile?.top_performing_content_type_other || ''
    })
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null) // Clear any previous errors
      
      const { data: { user } } = await supabase.auth.getUser()
      
      if (!user) {
        setError('User not authenticated')
        return
      }

      console.log('Saving profile data:', editForm) // Debug log
      console.log('User ID:', user.id) // Debug log

      // Check if profile exists first
      const { data: existingProfile, error: fetchError } = await supabase
        .from('profiles')
        .select('id')
        .eq('id', user.id)
        .single()

      console.log('Existing profile check:', { existingProfile, fetchError })

      // First, let's try to update the existing record
      const { data: updateData, error: updateError } = await supabase
        .from('profiles')
        .update({
          ...editForm,
          logo_url: logoUrl, // Include the logo URL
          updated_at: new Date().toISOString()
        })
        .eq('id', user.id)
        .select()

      if (updateError) {
        console.error('Update error:', updateError)
        
        // If update fails, try upsert as fallback
        console.log('Update failed, trying upsert...')
        const { data: upsertData, error: upsertError } = await supabase
          .from('profiles')
          .upsert({
            id: user.id,
            ...editForm,
            logo_url: logoUrl, // Include the logo URL
            updated_at: new Date().toISOString()
          })
          .select()

        if (upsertError) {
          console.error('Upsert error:', upsertError)
          setError(`Failed to update profile: ${upsertError.message}`)
          return
        }
        
        console.log('Profile upserted successfully:', upsertData)
      } else {
        console.log('Profile updated successfully:', updateData)
      }

      // Refresh the profile data from database
      await fetchProfile()
      setEditing(false)
      
      // Show success message
      alert('Profile updated successfully!')
    } catch (err) {
      console.error('Error updating profile:', err)
      setError(`Failed to update profile: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  const handleInputChange = (field, value) => {
    setEditForm(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const handleArrayInputChange = (field, value) => {
    const array = value.split(',').map(item => item.trim()).filter(item => item)
    setEditForm(prev => ({
      ...prev,
      [field]: array
    }))
  }

  const renderArrayField = (label, field, icon) => {
    const value = Array.isArray(editForm[field]) ? editForm[field].join(', ') : editForm[field]
    return (
      <div className="group">
        <label className="block text-xs sm:text-sm font-semibold text-gray-800 mb-2 sm:mb-3">
          {label}
        </label>
        {editing ? (
          <input
            type="text"
            value={value}
            onChange={(e) => handleArrayInputChange(field, e.target.value)}
            className="w-full px-3 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm border border-gray-200 rounded-lg sm:rounded-xl focus:ring-2 focus:ring-pink-500 focus:border-pink-500 transition-all duration-200 bg-white/50 backdrop-blur-sm shadow-sm hover:shadow-md"
            placeholder="Enter values separated by commas"
          />
        ) : (
          <div className="flex flex-wrap gap-1.5 sm:gap-2">
            {Array.isArray(profile?.[field]) && profile[field].length > 0 ? (
              profile[field].map((item, index) => (
                <span
                  key={index}
                  className="px-2 sm:px-3 md:px-4 py-1 sm:py-1.5 md:py-2 bg-gradient-to-r from-pink-100 to-purple-100 text-pink-700 rounded-full text-[10px] sm:text-xs md:text-sm font-medium shadow-sm hover:shadow-md transition-all duration-200 border border-pink-200"
                >
                  {item}
                </span>
              ))
            ) : (
              <div className="bg-gradient-to-r from-gray-50 to-white p-3 sm:p-4 rounded-lg sm:rounded-xl border border-gray-100 shadow-sm">
                <p className="text-xs sm:text-sm text-gray-500 font-medium">Not specified</p>
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  const renderCurrentPresenceField = () => {
    // Use profile data for display, editForm for editing
    const currentPresence = editing ? (editForm.current_presence || []) : (profile?.current_presence || [])
    const metaAdsFacebook = editing ? (editForm.meta_ads_facebook || false) : (profile?.meta_ads_facebook || false)
    const metaAdsInstagram = editing ? (editForm.meta_ads_instagram || false) : (profile?.meta_ads_instagram || false)
    
    // Debug logging
    console.log('Current Presence Debug:', {
      currentPresence,
      metaAdsFacebook,
      metaAdsInstagram,
      editing,
      profile: profile?.meta_ads_facebook,
      editForm: editForm?.meta_ads_facebook,
      fullProfile: profile,
      fullEditForm: editForm
    })
    
    // Process current presence to show field:value format for ALL fields
    const processedPresence = currentPresence.map(presence => {
      // For Website, show the actual URL
      if (presence === 'Website') {
        const websiteUrl = editing ? (editForm.website_url || '') : (profile?.website_url || '')
        return websiteUrl ? `Website: ${websiteUrl}` : 'Website: URL not provided'
      }

      // For other fields, show in "field: value" format
      return `${presence}: Active`
    })

    return (
      <div>
        <label className="block text-xs sm:text-sm font-medium text-gray-700 mb-2">
          Current Presence
        </label>
        {editing ? (
          <div className="text-xs sm:text-sm text-gray-900 bg-gray-50 px-2 sm:px-3 py-1.5 sm:py-2 rounded-lg min-h-[36px] sm:min-h-[40px] flex items-center">
            {processedPresence.join(', ') || 'Not specified'}
          </div>
        ) : (
          <div className="flex flex-wrap gap-1.5 sm:gap-2">
            {processedPresence.length > 0 ? (
              processedPresence.map((item, index) => (
                <span
                  key={index}
                  className="px-2 sm:px-3 py-0.5 sm:py-1 bg-purple-100 text-purple-800 rounded-full text-[10px] sm:text-xs md:text-sm"
                >
                  {item}
                </span>
              ))
            ) : (
              <p className="text-xs sm:text-sm text-gray-500">Not specified</p>
            )}
          </div>
        )}
      </div>
    )
  }

  const renderTextField = (label, field, icon, type = 'text', placeholder = '') => {
    return (
      <div className="group">
        <label className="block text-xs sm:text-sm font-semibold text-gray-800 mb-2 sm:mb-3">
          {label}
        </label>
        {editing ? (
          type === 'textarea' ? (
            <textarea
              value={editForm[field]}
              onChange={(e) => handleInputChange(field, e.target.value)}
              rows={3}
              className="w-full px-3 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm border border-gray-200 rounded-lg sm:rounded-xl focus:ring-2 focus:ring-pink-500 focus:border-pink-500 transition-all duration-200 bg-white/50 backdrop-blur-sm shadow-sm hover:shadow-md"
              placeholder={placeholder}
            />
          ) : (
            <input
              type={type}
              value={editForm[field]}
              onChange={(e) => handleInputChange(field, e.target.value)}
              className="w-full px-3 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm border border-gray-200 rounded-lg sm:rounded-xl focus:ring-2 focus:ring-pink-500 focus:border-pink-500 transition-all duration-200 bg-white/50 backdrop-blur-sm shadow-sm hover:shadow-md"
              placeholder={placeholder}
            />
          )
        ) : (
          <div className="bg-gradient-to-r from-gray-50 to-white p-3 sm:p-4 rounded-lg sm:rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-all duration-200">
            <p className="text-xs sm:text-sm text-gray-800 flex items-center font-medium">
              {icon && <span className="mr-2 sm:mr-3 text-gray-400">{icon}</span>}
              {profile?.[field] || 'Not provided'}
            </p>
          </div>
        )}
      </div>
    )
  }

  const renderBrandColors = () => {
    return (
      <div className="group col-span-1 md:col-span-2">
        <label className="block text-xs sm:text-sm font-semibold text-gray-800 mb-2 sm:mb-3">
          Brand Colors
        </label>
        {editing ? (
          <div className="space-y-4">
            {/* Primary Color */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-2">Primary Color</label>
              <div className="flex items-center space-x-2">
                <input
                  type="color"
                  value={editForm.primary_color || '#000000'}
                  onChange={(e) => handleInputChange('primary_color', e.target.value)}
                  className="w-16 h-10 border border-gray-300 rounded-lg cursor-pointer"
                />
                <input
                  type="text"
                  value={editForm.primary_color || ''}
                  onChange={(e) => handleInputChange('primary_color', e.target.value)}
                  className="flex-1 px-3 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm border border-gray-200 rounded-lg sm:rounded-xl focus:ring-2 focus:ring-pink-500 focus:border-pink-500 transition-all duration-200 bg-white/50 backdrop-blur-sm shadow-sm"
                  placeholder="#000000"
                  pattern="^#[0-9A-Fa-f]{6}$"
                />
              </div>
            </div>

            {/* Secondary Color */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-2">Secondary Color</label>
              <div className="flex items-center space-x-2">
                <input
                  type="color"
                  value={editForm.secondary_color || '#000000'}
                  onChange={(e) => handleInputChange('secondary_color', e.target.value)}
                  className="w-16 h-10 border border-gray-300 rounded-lg cursor-pointer"
                />
                <input
                  type="text"
                  value={editForm.secondary_color || ''}
                  onChange={(e) => handleInputChange('secondary_color', e.target.value)}
                  className="flex-1 px-3 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm border border-gray-200 rounded-lg sm:rounded-xl focus:ring-2 focus:ring-pink-500 focus:border-pink-500 transition-all duration-200 bg-white/50 backdrop-blur-sm shadow-sm"
                  placeholder="#000000"
                  pattern="^#[0-9A-Fa-f]{6}$"
                />
              </div>
            </div>

            {/* Additional Colors */}
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-2">Additional Colors</label>
              <div className="space-y-2">
                {(editForm.additional_colors || []).map((color, index) => (
                  <div key={index} className="flex items-center space-x-2">
                    <input
                      type="color"
                      value={color || '#000000'}
                      onChange={(e) => {
                        const newColors = [...(editForm.additional_colors || [])]
                        newColors[index] = e.target.value
                        handleInputChange('additional_colors', newColors)
                      }}
                      className="w-16 h-10 border border-gray-300 rounded-lg cursor-pointer"
                    />
                    <input
                      type="text"
                      value={color || ''}
                      onChange={(e) => {
                        const newColors = [...(editForm.additional_colors || [])]
                        newColors[index] = e.target.value
                        handleInputChange('additional_colors', newColors)
                      }}
                      className="flex-1 px-3 sm:px-4 py-2 sm:py-3 text-xs sm:text-sm border border-gray-200 rounded-lg sm:rounded-xl focus:ring-2 focus:ring-pink-500 focus:border-pink-500 transition-all duration-200 bg-white/50 backdrop-blur-sm shadow-sm"
                      placeholder="#000000"
                      pattern="^#[0-9A-Fa-f]{6}$"
                    />
                    <button
                      type="button"
                      onClick={() => {
                        const newColors = (editForm.additional_colors || []).filter((_, i) => i !== index)
                        handleInputChange('additional_colors', newColors)
                      }}
                      className="px-3 py-2 text-red-600 hover:text-red-800 border border-red-300 rounded-lg hover:bg-red-50 transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={() => {
                    handleInputChange('additional_colors', [...(editForm.additional_colors || []), ''])
                  }}
                  className="text-xs sm:text-sm text-pink-600 hover:text-pink-800 font-medium flex items-center space-x-1"
                >
                  <span>+ Add Color</span>
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="bg-gradient-to-r from-gray-50 to-white p-3 sm:p-4 rounded-lg sm:rounded-xl border border-gray-100 shadow-sm hover:shadow-md transition-all duration-200">
            <div className="space-y-3">
              {profile?.primary_color && (
                <div className="flex items-center space-x-3">
                  <div 
                    className="w-12 h-12 rounded-lg border border-gray-300 shadow-sm"
                    style={{ backgroundColor: profile.primary_color }}
                  />
                  <div>
                    <p className="text-xs font-medium text-gray-600">Primary</p>
                    <p className="text-xs sm:text-sm text-gray-800 font-medium">{profile.primary_color}</p>
                  </div>
                </div>
              )}
              {profile?.secondary_color && (
                <div className="flex items-center space-x-3">
                  <div 
                    className="w-12 h-12 rounded-lg border border-gray-300 shadow-sm"
                    style={{ backgroundColor: profile.secondary_color }}
                  />
                  <div>
                    <p className="text-xs font-medium text-gray-600">Secondary</p>
                    <p className="text-xs sm:text-sm text-gray-800 font-medium">{profile.secondary_color}</p>
                  </div>
                </div>
              )}
              {profile?.additional_colors && Array.isArray(profile.additional_colors) && profile.additional_colors.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-600 mb-2">Additional Colors</p>
                  <div className="flex flex-wrap gap-2">
                    {profile.additional_colors.map((color, index) => (
                      <div key={index} className="flex items-center space-x-2">
                        <div 
                          className="w-10 h-10 rounded-lg border border-gray-300 shadow-sm"
                          style={{ backgroundColor: color }}
                        />
                        <span className="text-xs text-gray-800">{color}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {!profile?.primary_color && !profile?.secondary_color && (!profile?.additional_colors || profile.additional_colors.length === 0) && (
                <p className="text-xs sm:text-sm text-gray-500">No brand colors set</p>
              )}
            </div>
          </div>
        )}
      </div>
    )
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-100 flex">
        <SideNavbar />
        <MobileNavigation />
        <div className="flex-1 ml-0 md:ml-48 xl:ml-64 flex items-center justify-center p-4">
          <div className="bg-white/70 backdrop-blur-sm rounded-2xl shadow-xl border border-gray-200/50 p-8">
            <div className="flex items-center space-x-4">
              <div className="w-12 h-12 bg-gradient-to-r from-pink-500 to-purple-600 rounded-xl flex items-center justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-white" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-gray-900">Loading Profile</h3>
                <p className="text-gray-600">Please wait while we fetch your information...</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-100 flex">
        <SideNavbar />
        <MobileNavigation />
        <div className="flex-1 ml-0 md:ml-48 xl:ml-64 flex items-center justify-center p-4">
          <div className="bg-white/70 backdrop-blur-sm rounded-2xl shadow-xl border border-gray-200/50 p-8 text-center max-w-md">
            <div className="w-16 h-16 bg-gradient-to-r from-red-500 to-pink-500 rounded-2xl flex items-center justify-center mx-auto mb-6">
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Error Loading Profile</h2>
            <p className="text-gray-600 mb-6">{error}</p>
            <button
              onClick={fetchProfile}
              className="px-6 py-3 bg-gradient-to-r from-pink-500 to-purple-600 text-white rounded-xl hover:from-pink-600 hover:to-purple-700 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 font-medium"
            >
              Try Again
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 via-white to-gray-100">
      {/* Sidebar */}
      <SideNavbar />
      
      {/* Mobile Navigation */}
      <MobileNavigation />
      
      {/* Main Content */}
      <div className="flex-1 ml-0 md:ml-48 xl:ml-64 pt-16 md:pt-0">
        {/* Header */}
        <div className="bg-white/80 backdrop-blur-sm shadow-lg border-b border-gray-200/50">
          <div className="max-w-7xl mx-auto px-3 sm:px-4 md:px-6 lg:px-8">
            <div className="flex justify-between items-center py-3 md:py-4 lg:py-8 gap-2 md:gap-0">
              <div className="flex items-center space-x-2 md:space-x-3 lg:space-x-6 min-w-0 flex-1 pr-2">
                <div className="w-10 h-10 sm:w-12 sm:h-12 md:w-16 md:h-16 rounded-lg sm:rounded-xl md:rounded-2xl flex items-center justify-center shadow-lg overflow-hidden flex-shrink-0">
                  {profile?.logo_url ? (
                    <img 
                      src={profile.logo_url} 
                      alt="Profile" 
                      className="w-10 h-10 sm:w-12 sm:h-12 md:w-16 md:h-16 object-cover rounded-lg sm:rounded-xl md:rounded-2xl"
                    />
                  ) : (
                    <div className="w-10 h-10 sm:w-12 sm:h-12 md:w-16 md:h-16 bg-gradient-to-r from-pink-500 to-purple-600 rounded-lg sm:rounded-xl md:rounded-2xl flex items-center justify-center">
                      <User className="w-5 h-5 sm:w-6 sm:h-6 md:w-8 md:h-8 text-white" />
                    </div>
                  )}
                </div>
                <div className="min-w-0">
                  <h1 className="text-base sm:text-lg md:text-xl lg:text-2xl xl:text-3xl font-bold bg-gradient-to-r from-gray-900 to-gray-700 bg-clip-text text-transparent truncate">
                    {profile?.name || 'Your Profile'}
                  </h1>
                  <p className="text-gray-600 text-xs sm:text-sm md:text-base lg:text-lg hidden md:block">Manage your account and business information</p>
                  <div className="flex items-center space-x-1.5 sm:space-x-2 md:space-x-4 mt-1 md:mt-2 flex-wrap gap-1 sm:gap-2">
                    <span className="px-1.5 sm:px-2 md:px-3 py-0.5 sm:py-1 bg-gradient-to-r from-pink-100 to-purple-100 text-pink-700 rounded-full text-[10px] sm:text-xs md:text-sm font-medium truncate max-w-[150px] sm:max-w-none">
                      {profile?.business_name || 'Business Account'}
                    </span>
                    <span className="px-1.5 sm:px-2 md:px-3 py-0.5 sm:py-1 bg-green-100 text-green-700 rounded-full text-[10px] sm:text-xs md:text-sm font-medium whitespace-nowrap">
                      Active
                    </span>
                  </div>
                </div>
              </div>
              <div className="flex items-center space-x-2 md:space-x-3 flex-shrink-0">
                {!editing ? (
                  <button
                    onClick={handleEdit}
                    className="group flex items-center space-x-1 px-2 sm:px-3 md:px-4 lg:px-6 py-1.5 sm:py-2 md:py-2.5 lg:py-3 bg-gradient-to-r from-pink-500 to-purple-600 text-white rounded-md sm:rounded-lg md:rounded-xl hover:from-pink-600 hover:to-purple-700 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 text-xs sm:text-sm md:text-base whitespace-nowrap"
                  >
                    <Edit className="w-3.5 h-3.5 sm:w-4 sm:h-4 md:w-5 md:h-5 group-hover:rotate-12 transition-transform" />
                    <span className="font-medium hidden lg:inline">Edit Profile</span>
                    <span className="font-medium hidden sm:inline lg:hidden">Edit</span>
                    <span className="font-medium sm:hidden">Edit</span>
                  </button>
                ) : (
                  <div className="flex items-center space-x-1 sm:space-x-2 md:space-x-3">
                    <button
                      onClick={handleCancel}
                      className="flex items-center space-x-1 px-2 sm:px-3 md:px-4 lg:px-6 py-1.5 sm:py-2 md:py-2.5 lg:py-3 bg-gray-100 text-gray-700 rounded-md sm:rounded-lg md:rounded-xl hover:bg-gray-200 transition-all duration-200 border border-gray-200 text-xs sm:text-sm md:text-base whitespace-nowrap"
                    >
                      <X className="w-3.5 h-3.5 sm:w-4 sm:h-4 md:w-5 md:h-5" />
                      <span className="font-medium hidden md:inline">Cancel</span>
                    </button>
                    <button
                      onClick={handleSave}
                      disabled={saving}
                      className="group flex items-center space-x-1 px-2 sm:px-3 md:px-4 lg:px-6 py-1.5 sm:py-2 md:py-2.5 lg:py-3 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-md sm:rounded-lg md:rounded-xl hover:from-green-600 hover:to-emerald-700 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:-translate-y-0.5 disabled:opacity-50 disabled:transform-none text-xs sm:text-sm md:text-base whitespace-nowrap"
                    >
                      {saving ? (
                        <Loader2 className="w-3.5 h-3.5 sm:w-4 sm:h-4 md:w-5 md:h-5 animate-spin" />
                      ) : (
                        <Save className="w-3.5 h-3.5 sm:w-4 sm:h-4 md:w-5 md:h-5 group-hover:scale-110 transition-transform" />
                      )}
                      <span className="font-medium hidden lg:inline">{saving ? 'Saving...' : 'Save Changes'}</span>
                      <span className="font-medium hidden sm:inline lg:hidden">{saving ? 'Saving...' : 'Save'}</span>
                      <span className="font-medium sm:hidden">{saving ? 'Saving...' : 'Save'}</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Main Content */}
        <div className="max-w-7xl mx-auto px-3 sm:px-4 md:px-6 lg:px-8 py-4 md:py-8">
          {/* Error Message */}
          {error && (
            <div className="mb-8 bg-gradient-to-r from-red-50 to-pink-50 border border-red-200 rounded-2xl p-6 shadow-sm">
              <div className="flex">
                <div className="flex-shrink-0">
                  <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center">
                    <svg className="h-6 w-6 text-red-500" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                  </div>
                </div>
                <div className="ml-4">
                  <h3 className="text-lg font-semibold text-red-800">Error</h3>
                  <div className="mt-2 text-red-700">
                    <p>{error}</p>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          <div className="space-y-4 md:space-y-8">
            {/* Basic Business Information */}
            <div className="bg-white/70 backdrop-blur-sm rounded-xl md:rounded-2xl shadow-xl border border-gray-200/50 p-4 md:p-6 lg:p-8 hover:shadow-2xl transition-all duration-300">
              <div className="flex items-center mb-4 md:mb-8">
                <div className="w-10 h-10 md:w-12 md:h-12 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg md:rounded-xl flex items-center justify-center shadow-lg flex-shrink-0">
                  <Building2 className="w-5 h-5 md:w-6 md:h-6 text-white" />
                </div>
                <div className="ml-3 md:ml-4">
                  <h2 className="text-base sm:text-lg md:text-xl lg:text-2xl font-bold text-gray-900">Basic Business Information</h2>
                  <p className="text-xs sm:text-sm md:text-base text-gray-600 hidden md:block">Your core business details and branding</p>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
                {renderTextField('Name', 'name', <User className="w-4 h-4 text-gray-400" />)}
                {renderTextField('Business Name', 'business_name', <Building2 className="w-4 h-4 text-gray-400" />)}
                {renderArrayField('Business Type', 'business_type')}
                {renderArrayField('Industry', 'industry')}
                {renderTextField('Business Description', 'business_description', null, 'textarea', 'Describe your business...')}
                
                {/* Logo Display/Upload */}
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Business Logo
                  </label>
                  {editing ? (
                    <div className="space-y-4">
                      <LogoUpload
                        onUploadSuccess={handleLogoUpload}
                        onError={handleLogoError}
                        className="max-w-md"
                      />
                      {logoError && (
                        <div className="text-red-600 text-sm">{logoError}</div>
                      )}
                    </div>
                  ) : (
                    <div className="flex items-center space-x-4">
                      {logoUrl ? (
                        <div className="flex items-center space-x-3">
                          <img
                            src={logoUrl}
                            alt="Business Logo"
                            className="w-16 h-16 object-contain rounded-lg border border-gray-200 cursor-pointer hover:shadow-md transition-shadow"
                            onClick={() => setIsLogoModalOpen(true)}
                          />
                          <div>
                            <p className="text-sm text-gray-600">Logo uploaded</p>
                            <button
                              onClick={() => setIsLogoModalOpen(true)}
                              className="text-sm text-purple-600 hover:text-purple-700 hover:underline"
                            >
                              View full size
                            </button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center space-x-2 text-gray-400">
                          <ImageIcon className="w-5 h-5" />
                          <span className="text-sm">No logo uploaded</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
                
                {renderArrayField('Target Audience', 'target_audience')}
                {renderTextField('Unique Value Proposition', 'unique_value_proposition', null, 'textarea', 'What makes your business unique?')}
              </div>
            </div>

            {/* Brand & Contact Information */}
            <div className="bg-white/70 backdrop-blur-sm rounded-xl md:rounded-2xl shadow-xl border border-gray-200/50 p-4 md:p-6 lg:p-8 hover:shadow-2xl transition-all duration-300">
              <div className="flex items-center mb-4 md:mb-8">
                <div className="w-10 h-10 md:w-12 md:h-12 bg-gradient-to-r from-blue-500 to-cyan-500 rounded-lg md:rounded-xl flex items-center justify-center shadow-lg flex-shrink-0">
                  <Globe className="w-5 h-5 md:w-6 md:h-6 text-white" />
                </div>
                <div className="ml-3 md:ml-4">
                  <h2 className="text-lg md:text-xl lg:text-2xl font-bold text-gray-900">Brand & Contact Information</h2>
                  <p className="text-xs md:text-sm text-gray-600 hidden md:block">Your brand voice and contact details</p>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
                {renderTextField('Brand Voice', 'brand_voice', null, 'textarea', 'How does your brand communicate?')}
                {renderTextField('Brand Tone', 'brand_tone', null, 'textarea', 'What tone does your brand use?')}
                {renderBrandColors()}
                {renderTextField('Website URL', 'website_url', <Globe className="w-4 h-4 text-gray-400" />, 'url')}
                {renderTextField('Phone Number', 'phone_number', <Phone className="w-4 h-4 text-gray-400" />, 'tel')}
                {renderTextField('Street Address', 'street_address', <MapPin className="w-4 h-4 text-gray-400" />)}
                {renderTextField('City', 'city', <MapPin className="w-4 h-4 text-gray-400" />)}
                {renderTextField('State', 'state', <MapPin className="w-4 h-4 text-gray-400" />)}
                {renderTextField('Country', 'country', <MapPin className="w-4 h-4 text-gray-400" />)}
                {renderTextField('Timezone', 'timezone', <Calendar className="w-4 h-4 text-gray-400" />)}
              </div>
            </div>

            {/* Digital Marketing & Goals */}
            <div className="bg-white/70 backdrop-blur-sm rounded-xl md:rounded-2xl shadow-xl border border-gray-200/50 p-4 md:p-6 lg:p-8 hover:shadow-2xl transition-all duration-300">
              <div className="flex items-center mb-4 md:mb-8">
                <div className="w-10 h-10 md:w-12 md:h-12 bg-gradient-to-r from-green-500 to-emerald-500 rounded-lg md:rounded-xl flex items-center justify-center shadow-lg flex-shrink-0">
                  <Target className="w-5 h-5 md:w-6 md:h-6 text-white" />
                </div>
                <div className="ml-3 md:ml-4">
                  <h2 className="text-lg md:text-xl lg:text-2xl font-bold text-gray-900">Digital Marketing & Goals</h2>
                  <p className="text-xs md:text-sm text-gray-600 hidden md:block">Your social presence and objectives</p>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
                {renderArrayField('Social Media Platforms', 'social_media_platforms')}
                {renderArrayField('Primary Goals', 'primary_goals')}
                {renderArrayField('Key Metrics to Track', 'key_metrics_to_track')}
              </div>
            </div>

            {/* Content Strategy */}
            <div className="bg-white/70 backdrop-blur-sm rounded-xl md:rounded-2xl shadow-xl border border-gray-200/50 p-4 md:p-6 lg:p-8 hover:shadow-2xl transition-all duration-300">
              <div className="flex items-center mb-4 md:mb-8">
                <div className="w-10 h-10 md:w-12 md:h-12 bg-gradient-to-r from-orange-500 to-red-500 rounded-lg md:rounded-xl flex items-center justify-center shadow-lg flex-shrink-0">
                  <BarChart3 className="w-5 h-5 md:w-6 md:h-6 text-white" />
                </div>
                <div className="ml-3 md:ml-4">
                  <h2 className="text-lg md:text-xl lg:text-2xl font-bold text-gray-900">Content Strategy</h2>
                  <p className="text-xs md:text-sm text-gray-600 hidden md:block">Your content planning and preferences</p>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
                {renderTextField('Monthly Marketing Budget', 'monthly_budget_range', null, 'text', 'e.g., ₹500-₹1000')}
                {renderArrayField('Preferred Content Types', 'preferred_content_types')}
                {renderArrayField('Content Themes', 'content_themes')}
              </div>
            </div>

            {/* Market & Competition */}
            <div className="bg-white/70 backdrop-blur-sm rounded-xl md:rounded-2xl shadow-xl border border-gray-200/50 p-4 md:p-6 lg:p-8 hover:shadow-2xl transition-all duration-300">
              <div className="flex items-center mb-4 md:mb-8">
                <div className="w-10 h-10 md:w-12 md:h-12 bg-gradient-to-r from-red-500 to-pink-500 rounded-lg md:rounded-xl flex items-center justify-center shadow-lg flex-shrink-0">
                  <Target className="w-5 h-5 md:w-6 md:h-6 text-white" />
                </div>
                <div className="ml-3 md:ml-4">
                  <h2 className="text-lg md:text-xl lg:text-2xl font-bold text-gray-900">Market & Competition</h2>
                  <p className="text-xs md:text-sm text-gray-600 hidden md:block">Your market position and competitors</p>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
                {renderTextField('Main Competitors', 'main_competitors', null, 'textarea', 'List your main competitors')}
                {renderTextField('Market Position', 'market_position', null, 'textarea', 'How do you position yourself in the market?')}
                {renderTextField('Products or Services', 'products_or_services', null, 'textarea', 'Describe your products or services')}
              </div>
            </div>

            {/* Campaign Planning */}
            <div className="bg-white/70 backdrop-blur-sm rounded-xl md:rounded-2xl shadow-xl border border-gray-200/50 p-4 md:p-6 lg:p-8 hover:shadow-2xl transition-all duration-300">
              <div className="flex items-center mb-4 md:mb-8">
                <div className="w-10 h-10 md:w-12 md:h-12 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-lg md:rounded-xl flex items-center justify-center shadow-lg flex-shrink-0">
                  <Calendar className="w-5 h-5 md:w-6 md:h-6 text-white" />
                </div>
                <div className="ml-3 md:ml-4">
                  <h2 className="text-lg md:text-xl lg:text-2xl font-bold text-gray-900">Campaign Planning</h2>
                  <p className="text-xs md:text-sm text-gray-600 hidden md:block">Your campaign strategy and timing</p>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
                {renderTextField('Important Launch Dates', 'important_launch_dates', null, 'textarea', 'Key dates for your business')}
                {renderTextField('Planned Promotions or Campaigns', 'planned_promotions_or_campaigns', null, 'textarea', 'Upcoming campaigns')}
                {renderArrayField('Top Performing Content Types', 'top_performing_content_types')}
                {renderArrayField('Best Time to Post', 'best_time_to_post')}
              </div>
            </div>

            {/* Performance & Customer */}
            <div className="bg-white/70 backdrop-blur-sm rounded-xl md:rounded-2xl shadow-xl border border-gray-200/50 p-4 md:p-6 lg:p-8 hover:shadow-2xl transition-all duration-300">
              <div className="flex items-center mb-4 md:mb-8">
                <div className="w-10 h-10 md:w-12 md:h-12 bg-gradient-to-r from-pink-500 to-rose-500 rounded-lg md:rounded-xl flex items-center justify-center shadow-lg flex-shrink-0">
                  <BarChart3 className="w-5 h-5 md:w-6 md:h-6 text-white" />
                </div>
                <div className="ml-3 md:ml-4">
                  <h2 className="text-lg md:text-xl lg:text-2xl font-bold text-gray-900">Performance & Customer</h2>
                  <p className="text-xs md:text-sm text-gray-600 hidden md:block">Your success metrics and customer insights</p>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
                {renderTextField('Successful Campaigns', 'successful_campaigns', null, 'textarea', 'Describe your successful campaigns')}
                {renderTextField('Hashtags That Work Well', 'hashtags_that_work_well', null, 'textarea', 'List effective hashtags')}
                {renderTextField('Customer Pain Points', 'customer_pain_points', null, 'textarea', 'What problems do your customers face?')}
                {renderTextField('Typical Customer Journey', 'typical_customer_journey', null, 'textarea', 'Describe your customer journey')}
              </div>
            </div>

            {/* Automation & Platform */}
            <div className="bg-white/70 backdrop-blur-sm rounded-xl md:rounded-2xl shadow-xl border border-gray-200/50 p-4 md:p-6 lg:p-8 hover:shadow-2xl transition-all duration-300">
              <div className="flex items-center mb-4 md:mb-8">
                <div className="w-10 h-10 md:w-12 md:h-12 bg-gradient-to-r from-teal-500 to-cyan-500 rounded-lg md:rounded-xl flex items-center justify-center shadow-lg flex-shrink-0">
                  <Settings className="w-5 h-5 md:w-6 md:h-6 text-white" />
                </div>
                <div className="ml-3 md:ml-4">
                  <h2 className="text-lg md:text-xl lg:text-2xl font-bold text-gray-900">Automation & Platform</h2>
                  <p className="text-xs md:text-sm text-gray-600 hidden md:block">Your automation preferences and platform settings</p>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
                {renderTextField('Automation Level', 'automation_level', null, 'text', 'e.g., Beginner, Intermediate, Advanced')}
                {renderCurrentPresenceField()}
                {renderArrayField('Focus Areas', 'focus_areas')}
              </div>
            </div>

            {/* Platform Links */}
            <div className="bg-white/70 backdrop-blur-sm rounded-xl md:rounded-2xl shadow-xl border border-gray-200/50 p-4 md:p-6 lg:p-8 hover:shadow-2xl transition-all duration-300">
              <div className="flex items-center mb-4 md:mb-8">
                <div className="w-10 h-10 md:w-12 md:h-12 bg-gradient-to-r from-purple-500 to-pink-500 rounded-lg md:rounded-xl flex items-center justify-center shadow-lg flex-shrink-0">
                  <Megaphone className="w-5 h-5 md:w-6 md:h-6 text-white" />
                </div>
                <div className="ml-3 md:ml-4">
                  <h2 className="text-lg md:text-xl lg:text-2xl font-bold text-gray-900">Platform Links & Accounts</h2>
                  <p className="text-xs md:text-sm text-gray-600 hidden md:block">Your social media and platform connections</p>
                </div>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
                {renderTextField('Facebook Page/Profile Link', 'facebook_page_name', null, 'url')}
                {renderTextField('Instagram Profile Link', 'instagram_profile_link', null, 'url')}
                {renderTextField('LinkedIn Company Link', 'linkedin_company_link', null, 'url')}
                {renderTextField('YouTube Channel Link', 'youtube_channel_link', null, 'url')}
                {renderTextField('Google Business Profile', 'google_business_profile', null, 'url')}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Edit Profile Modal */}
      <EditProfileModal
        isOpen={isEditModalOpen}
        onClose={handleModalClose}
        onSuccess={handleModalSuccess}
      />

      {/* Logo Showcase Modal */}
      <ImageShowcaseModal
        isOpen={isLogoModalOpen}
        onClose={() => setIsLogoModalOpen(false)}
        imageUrl={logoUrl}
        imageAlt="Business Logo"
      />
    </div>
  )
}

export default Profile