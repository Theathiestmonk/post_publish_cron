import React, { useState, useEffect } from 'react'
import { X, Hash, Edit, Check, X as XIcon, Sparkles, RefreshCw } from 'lucide-react'
import { Instagram, Facebook, MessageCircle } from 'lucide-react'
import { supabase } from '../lib/supabase'

// Get API URL
const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

// Get dark mode state from localStorage or default to light mode
const getDarkModePreference = () => {
  return localStorage.getItem('darkMode') === 'true'
}

// Listen for storage changes to sync dark mode across components
const useStorageListener = (key, callback) => {
  useEffect(() => {
    const handleStorageChange = (e) => {
      if (e.key === key) {
        callback(e.newValue === 'true')
      }
    }

    const handleCustomChange = (e) => {
      if (e.detail.key === key) {
        callback(e.detail.value === 'true')
      }
    }

    window.addEventListener('storage', handleStorageChange)
    window.addEventListener('localStorageChange', handleCustomChange)

    return () => {
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('localStorageChange', handleCustomChange)
    }
  }, [key, callback])
}

const ATSNContentModal = ({ content, onClose }) => {
  const [profileData, setProfileData] = useState(null)
  const [isEditing, setIsEditing] = useState(false)
  const [editTitleValue, setEditTitleValue] = useState('')
  const [editContentValue, setEditContentValue] = useState('')
  const [editHashtagsValue, setEditHashtagsValue] = useState('')
  const [showAIEditModal, setShowAIEditModal] = useState(false)
  const [aiEditType, setAiEditType] = useState('')
  const [aiEditInstruction, setAiEditInstruction] = useState('')
  const [aiEditing, setAiEditing] = useState(false)
  const [aiEditedContent, setAiEditedContent] = useState('')
  const [showAIResult, setShowAIResult] = useState(false)
  const [isDarkMode, setIsDarkMode] = useState(getDarkModePreference)

  // Listen for dark mode changes from other components
  useStorageListener('darkMode', setIsDarkMode)

  // Fetch profile data when content changes
  useEffect(() => {
    const fetchProfileData = async () => {
      try {
        const { data: { user } } = await supabase.auth.getUser()
        if (!user) return

        const { data, error } = await supabase
          .from('profiles')
          .select('logo_url, business_name, business_type, name')
          .eq('id', user.id)
          .single()

        if (error) {
          console.error('Error fetching profile:', error)
          return
        }

        setProfileData(data)
      } catch (error) {
        console.error('Error loading profile:', error)
      }
    }

    if (content) {
      fetchProfileData()
    }
  }, [content])

  // Edit handlers
  const handleEdit = () => {
    setEditTitleValue(content.title || '')
    setEditContentValue(content.content || '')
    setEditHashtagsValue(content.hashtags ? content.hashtags.join(' ') : '')
    setIsEditing(true)
  }

  const handleSave = () => {
    // Here you could add API call to save the edited content
    console.log('Saving title:', editTitleValue)
    console.log('Saving content:', editContentValue)
    console.log('Saving hashtags:', editHashtagsValue)
    setIsEditing(false)
    // Update the content object (this is just local for now)
    content.title = editTitleValue
    content.content = editContentValue
    content.hashtags = editHashtagsValue ? editHashtagsValue.split(' ').filter(tag => tag.trim()) : []
  }

  const handleCancelEdit = () => {
    setIsEditing(false)
  }

  const handleAIEdit = (field) => {
    setAiEditType(field)
    setShowAIEditModal(true)
    setAiEditInstruction('')
  }

  const handleAISaveEdit = async () => {
    if (!aiEditInstruction.trim()) return

    // Validate instruction length
    if (aiEditInstruction.length > 500) {
      console.error('Instruction too long - please keep under 500 characters')
      return
    }

    try {
      setAiEditing(true)

      // Get the current text based on type
      const currentText = aiEditType === 'title'
        ? editTitleValue
        : aiEditType === 'content'
        ? editContentValue
        : editHashtagsValue

      // Get auth token
      const { data: { session } } = await supabase.auth.getSession()
      if (!session?.access_token) {
        console.error('No auth token available')
        return
      }

      // Call AI service to edit content
      const response = await fetch(`${API_BASE_URL}/content/ai/edit-content`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${session.access_token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content: currentText,
          instruction: aiEditInstruction
        })
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`HTTP error! status: ${response.status}: ${errorText}`)
      }

      const result = await response.json()

      if (result.success) {
        // Show the AI result in the modal instead of directly updating
        setAiEditedContent(result.edited_content)
        setShowAIResult(true)
        console.log(`AI edited ${aiEditType}:`, result.edited_content)
      } else {
        throw new Error(result.error || result.detail || 'Failed to edit content with AI')
      }

    } catch (error) {
      console.error('AI edit failed:', error)
      // Show error but don't fall back to simple enhancement
      alert(`Failed to edit content with AI: ${error.message}`)
    } finally {
      setAiEditing(false)
    }
  }


  const handleSaveAIResult = () => {
    // Apply the AI-edited content to the form
    if (aiEditType === 'title') {
      setEditTitleValue(aiEditedContent)
    } else if (aiEditType === 'content') {
      setEditContentValue(aiEditedContent)
    } else if (aiEditType === 'hashtags') {
      setEditHashtagsValue(aiEditedContent)
    }

    // Close the modal and reset state
    setShowAIEditModal(false)
    setShowAIResult(false)
    setAiEditedContent('')
    setAiEditInstruction('')
  }

  const handleCancelAIEdit = () => {
    setShowAIEditModal(false)
    setShowAIResult(false)
    setAiEditedContent('')
    setAiEditInstruction('')
  }

  if (!content) return null

  // Platform icons
  const getPlatformIcon = (platformName) => {
    switch (platformName?.toLowerCase()) {
      case 'instagram':
        return <Instagram className="w-6 h-6 text-pink-500" />
      case 'facebook':
        return <Facebook className="w-6 h-6 text-blue-600" />
      case 'linkedin':
        return <div className="w-6 h-6 bg-blue-700 rounded-sm flex items-center justify-center text-white text-xs font-bold">in</div>
      case 'twitter':
        return <div className="w-6 h-6 bg-blue-400 rounded-full flex items-center justify-center text-white text-xs">𝕏</div>
      case 'tiktok':
        return <div className="w-6 h-6 bg-black rounded-sm flex items-center justify-center text-white text-xs">TT</div>
      default:
        return <MessageCircle className={`w-6 h-6 ${
          isDarkMode ? 'text-gray-400' : 'text-gray-500'
        }`} />
    }
  }

  // Platform display name
  const getPlatformDisplayName = (platformName) => {
    switch (platformName?.toLowerCase()) {
      case 'whatsapp business':
        return 'WhatsApp'
      case 'gmail':
        return 'Email'
      default:
        return platformName?.charAt(0).toUpperCase() + platformName?.slice(1)
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-75 z-30"
      onClick={onClose}
    >
      <div
        className="fixed inset-0 flex items-center justify-center p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className={`relative max-w-6xl w-full rounded-2xl shadow-2xl overflow-hidden ${
          isDarkMode ? 'bg-gray-800' : 'bg-white'
        }`}>
          {/* Header */}
          <div className={`flex items-center justify-between p-6 border-b ${
            isDarkMode
              ? 'border-gray-700 bg-gradient-to-r from-gray-700 to-gray-600'
              : 'border-gray-200 bg-gradient-to-r from-purple-50 to-pink-50'
          }`}>
            <div className="flex items-center gap-3">
              {getPlatformIcon(content.platform)}
              <span className={`font-semibold ${
                isDarkMode ? 'text-gray-100' : 'text-gray-900'
              }`}>
                {getPlatformDisplayName(content.platform)}
              </span>
            </div>
            <button
              onClick={onClose}
              className={`w-8 h-8 rounded-lg flex items-center justify-center transition-colors ${
                isDarkMode
                  ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                  : 'bg-gray-100 hover:bg-gray-200 text-gray-500'
              }`}
              title="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Content - Two Column Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-6 min-h-[400px]">
            {/* Left Column - Image */}
            <div className="space-y-4 -mx-2">
              {content.media_url && (
                <div className="flex justify-center">
                  <img
                    src={content.media_url}
                    alt={content.title || "Content image"}
                    className="w-full max-h-[32rem] object-contain rounded-lg shadow-lg"
                    onError={(e) => {
                      e.target.style.display = 'none'
                    }}
                  />
                </div>
              )}
            </div>

            {/* Right Column - Content Details */}
            <div className="space-y-6 pr-4">
              {/* Business Logo and Name */}
              {profileData && (
                <div className="flex items-center justify-between pb-4 border-b border-gray-200">
                  <div className="flex items-center gap-3">
                    <img
                      src={profileData.logo_url || '/default-logo.png'}
                      alt={profileData.business_name || 'Business logo'}
                      className="w-10 h-10 rounded-full object-cover border-2 border-gray-200"
                      onError={(e) => {
                        e.target.src = '/default-logo.png'
                      }}
                    />
                    <div>
                      <span className={`font-semibold text-lg ${
                        isDarkMode ? 'text-gray-100' : 'text-gray-900'
                      }`}>
                        {profileData.business_name || 'Business'}
                      </span>
                    </div>
                  </div>

                  {/* Edit Button - Top Right */}
                  {!isEditing && (content.title || content.content) && (
                    <button
                      onClick={handleEdit}
                      className={`p-2 rounded-lg transition-colors ${
                        isDarkMode
                          ? 'text-gray-400 hover:text-blue-400 hover:bg-blue-900/20'
                          : 'text-gray-500 hover:text-blue-600 hover:bg-blue-50'
                      }`}
                      title="Edit content"
                    >
                      <Edit className="w-5 h-5" />
                    </button>
                  )}
                </div>
              )}

              {/* Title */}
              {content.title && (
                <div>
                  {isEditing ? (
                    <div className="mb-4">
                      <div className="flex items-center justify-between mb-2">
                        <label className={`block text-sm font-medium ${
                          isDarkMode ? 'text-gray-300' : 'text-gray-700'
                        }`}>Title</label>
                        <button
                          onClick={() => handleAIEdit('title')}
                          disabled={aiEditing}
                          className={`p-1 rounded transition-colors disabled:opacity-50 ${
                            isDarkMode
                              ? 'text-gray-400 hover:text-purple-400 hover:bg-purple-900/20'
                              : 'text-gray-500 hover:text-purple-600 hover:bg-purple-50'
                          }`}
                          title="Enhance with AI"
                        >
                          <Sparkles className="w-4 h-4" />
                        </button>
                      </div>
                      <textarea
                        value={editTitleValue}
                        onChange={(e) => setEditTitleValue(e.target.value)}
                        className={`w-full p-3 border rounded-lg text-xl font-bold focus:outline-none focus:ring-2 ${
                          isDarkMode
                            ? 'border-gray-600 text-gray-200 bg-gray-700 focus:ring-blue-400'
                            : 'border-gray-300 text-gray-900 focus:ring-blue-500'
                        }`}
                        rows={2}
                        placeholder="Enter title..."
                      />
                    </div>
                  ) : (
                    <h2 className={`text-2xl font-bold leading-tight ${
                      isDarkMode ? 'text-gray-100' : 'text-gray-900'
                    }`}>
                      {content.title}
                    </h2>
                  )}
                </div>
              )}

              {/* Full Content */}
              {content.content && (
                <div>
                  {isEditing ? (
                    <div className="mb-4">
                      <div className="flex items-center justify-between mb-2">
                        <label className={`block text-sm font-medium ${
                          isDarkMode ? 'text-gray-300' : 'text-gray-700'
                        }`}>Content</label>
                        <button
                          onClick={() => handleAIEdit('content')}
                          disabled={aiEditing}
                          className={`p-1 rounded transition-colors disabled:opacity-50 ${
                            isDarkMode
                              ? 'text-gray-400 hover:text-purple-400 hover:bg-purple-900/20'
                              : 'text-gray-500 hover:text-purple-600 hover:bg-purple-50'
                          }`}
                          title="Enhance with AI"
                        >
                          <Sparkles className="w-4 h-4" />
                        </button>
                      </div>
                      <textarea
                        value={editContentValue}
                        onChange={(e) => setEditContentValue(e.target.value)}
                        className={`w-full p-4 border rounded-lg leading-relaxed focus:outline-none focus:ring-2 min-h-[200px] ${
                          isDarkMode
                            ? 'border-gray-600 text-gray-200 bg-gray-700 focus:ring-blue-400'
                            : 'border-gray-300 text-gray-700 focus:ring-blue-500'
                        }`}
                        placeholder="Enter content..."
                      />
                      <div className="flex items-center justify-between mb-2 mt-4">
                        <label className={`block text-sm font-medium ${
                          isDarkMode ? 'text-gray-300' : 'text-gray-700'
                        }`}>Hashtags</label>
                        <button
                          onClick={() => handleAIEdit('hashtags')}
                          disabled={aiEditing}
                          className={`p-1 rounded transition-colors disabled:opacity-50 ${
                            isDarkMode
                              ? 'text-gray-400 hover:text-purple-400 hover:bg-purple-900/20'
                              : 'text-gray-500 hover:text-purple-600 hover:bg-purple-50'
                          }`}
                          title="Generate hashtags with AI"
                        >
                          <Sparkles className="w-4 h-4" />
                        </button>
                      </div>
                      <input
                        type="text"
                        value={editHashtagsValue}
                        onChange={(e) => setEditHashtagsValue(e.target.value)}
                        className={`w-full p-3 border rounded-lg focus:outline-none focus:ring-2 ${
                          isDarkMode
                            ? 'border-gray-600 text-gray-200 bg-gray-700 focus:ring-blue-400'
                            : 'border-gray-300 text-gray-700 focus:ring-blue-500'
                        }`}
                        placeholder="Enter hashtags separated by spaces (e.g., #marketing #socialmedia)"
                      />
                    </div>
                  ) : (
                    <div className={`leading-relaxed whitespace-pre-wrap ${
                      isDarkMode ? 'text-gray-300' : 'text-gray-700'
                    }`}>
                      {content.content}
                    </div>
                  )}
                </div>
              )}


              {isEditing && (
                <div className={`flex justify-end gap-2 pt-4 border-t ${
                  isDarkMode ? 'border-gray-700' : 'border-gray-200'
                }`}>
                  <button
                    onClick={handleCancelEdit}
                    className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                      isDarkMode
                        ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-gray-100 border-gray-600 hover:border-gray-500'
                        : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                    }`}
                  >
                    <XIcon className="w-4 h-4" />
                    <span>Cancel</span>
                  </button>
                  <button
                    onClick={handleSave}
                    className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                      isDarkMode
                        ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-gray-100 border-gray-600 hover:border-gray-500'
                        : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                    }`}
                  >
                    <Check className="w-4 h-4" />
                    <span>Save Changes</span>
                  </button>
                </div>
              )}

              {/* Hashtags - Only show when not editing */}
              {!isEditing && content.hashtags && Array.isArray(content.hashtags) && content.hashtags.length > 0 && (
                <div className="pt-4 border-t border-gray-200">
                  <p className="text-sm text-blue-500">
                    {content.hashtags.map((hashtag, index) => (
                      <span key={index}>
                        {hashtag.startsWith('#') ? hashtag : `#${hashtag}`}
                        {index < content.hashtags.length - 1 ? ' ' : ''}
                      </span>
                    ))}
                  </p>
                </div>
              )}

              {/* Additional content fields */}
              {content.email_subject && (
                <div className="pt-4 border-t border-gray-200">
                  <h3 className="font-semibold text-gray-900 mb-2">Email Subject:</h3>
                  <p className={`${
                    isDarkMode ? 'text-gray-300' : 'text-gray-700'
                  }`}>{content.email_subject}</p>
                </div>
              )}

              {content.email_body && (
                <div className="pt-4">
                  <h3 className="font-semibold text-gray-900 mb-2">Email Body:</h3>
                  <div className={`whitespace-pre-wrap ${
                    isDarkMode ? 'text-gray-300' : 'text-gray-700'
                  }`}>{content.email_body}</div>
                </div>
              )}

              {content.short_video_script && (
                <div className="pt-4 border-t border-gray-200">
                  <h3 className="font-semibold text-gray-900 mb-2">Short Video Script:</h3>
                  <div className={`whitespace-pre-wrap p-4 rounded-lg ${
                    isDarkMode
                      ? 'text-gray-300 bg-gray-700'
                      : 'text-gray-700 bg-gray-50'
                  }`}>{content.short_video_script}</div>
                </div>
              )}

              {content.long_video_script && (
                <div className="pt-4">
                  <h3 className="font-semibold text-gray-900 mb-2">Long Video Script:</h3>
                  <div className={`whitespace-pre-wrap p-4 rounded-lg ${
                    isDarkMode
                      ? 'text-gray-300 bg-gray-700'
                      : 'text-gray-700 bg-gray-50'
                  }`}>{content.long_video_script}</div>
                </div>
              )}

              {content.message && (
                <div className="pt-4 border-t border-gray-200">
                  <h3 className="font-semibold text-gray-900 mb-2">Message:</h3>
                  <div className={`whitespace-pre-wrap p-4 rounded-lg ${
                    isDarkMode
                      ? 'text-gray-300 bg-gray-700'
                      : 'text-gray-700 bg-gray-50'
                  }`}>{content.message}</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* AI Edit Modal */}
      {showAIEditModal && (
        <div
          className="fixed inset-0 bg-black bg-opacity-75 z-[60]"
          onClick={handleCancelAIEdit}
        >
          <div
            className="fixed inset-0 flex items-center justify-center p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={`relative max-w-2xl w-full rounded-2xl shadow-2xl overflow-hidden ${
              isDarkMode ? 'bg-gray-800' : 'bg-white'
            }`}>
              {/* Header */}
              <div className={`p-6 border-b ${
                isDarkMode
                  ? 'border-gray-700 bg-gradient-to-r from-gray-700 to-gray-600'
                  : 'border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50'
              }`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <img
                      src="/leo_logo.jpg"
                      alt="Leo"
                      className="w-12 h-12 rounded-full object-cover border-2 border-gray-200"
                      onError={(e) => {
                        e.target.src = '/default-logo.png'
                      }}
                    />
                    <div>
                      <h3 className={`text-xl font-semibold ${
                        isDarkMode ? 'text-gray-100' : 'text-gray-900'
                      }`}>
                        Edit {aiEditType === 'title' ? 'Title' : aiEditType === 'content' ? 'Content' : 'Hashtags'} with Leo
                      </h3>
                      <p className={`text-sm ${
                        isDarkMode ? 'text-gray-400' : 'text-gray-600'
                      }`}>
                        Provide instructions for Leo to modify the {aiEditType}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={handleCancelAIEdit}
                    className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
                      isDarkMode
                        ? 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                        : 'bg-gray-100 hover:bg-gray-200 text-gray-500'
                    }`}
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {/* Content */}
              <div className="p-6">
                <div className="space-y-4">
                  {!showAIResult ? (
                    <>
                      {/* Current Content Preview */}
                      <div>
                        <label className={`block text-sm font-medium mb-2 ${
                          isDarkMode ? 'text-gray-300' : 'text-gray-700'
                        }`}>
                          Current {aiEditType === 'title' ? 'Title' : aiEditType === 'content' ? 'Content' : 'Hashtags'}
                        </label>
                        <div className={`p-3 rounded-lg text-sm max-h-32 overflow-y-auto ${
                          isDarkMode
                            ? 'bg-gray-700 text-gray-300'
                            : 'bg-gray-50 text-gray-700'
                        }`}>
                          {aiEditType === 'title'
                            ? editTitleValue
                            : aiEditType === 'content'
                            ? editContentValue
                            : editHashtagsValue
                          }
                        </div>
                      </div>

                      {/* AI Instruction */}
                      <div>
                        <label className={`block text-sm font-medium mb-2 ${
                          isDarkMode ? 'text-gray-300' : 'text-gray-700'
                        }`}>
                          AI Instruction <span className="text-red-500">*</span>
                        </label>
                        <div className="relative">
                          <textarea
                            value={aiEditInstruction}
                            onChange={(e) => setAiEditInstruction(e.target.value)}
                            className={`w-full p-4 border rounded-lg focus:ring-2 focus:border-transparent resize-none text-sm ${
                              isDarkMode
                                ? 'border-gray-600 text-gray-200 bg-gray-700 focus:ring-blue-400'
                                : 'border-gray-300 text-gray-900 focus:ring-blue-500'
                            }`}
                            rows={5}
                            placeholder="Describe how you want the content to be modified..."
                          />
                          <div className="absolute bottom-3 right-3 text-xs text-gray-400">
                            {aiEditInstruction.length}/500
                          </div>
                        </div>

                        {/* Instruction Examples */}
                        <div className="mt-3">
                          <p className={`text-xs mb-2 ${
                            isDarkMode ? 'text-gray-400' : 'text-gray-500'
                          }`}>Example instructions:</p>
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                            <button
                              onClick={() => setAiEditInstruction("Make it more engaging and add relevant emojis")}
                              className={`text-left p-2 text-xs rounded border transition-colors ${
                                isDarkMode
                                  ? 'bg-blue-900/20 hover:bg-blue-900/30 border-blue-700 text-blue-300'
                                  : 'bg-blue-50 hover:bg-blue-100 border-blue-200 text-blue-800'
                              }`}
                            >
                              Make it more engaging
                            </button>
                            <button
                              onClick={() => setAiEditInstruction("Make it shorter and more concise")}
                              className={`text-left p-2 text-xs rounded border transition-colors ${
                                isDarkMode
                                  ? 'bg-blue-900/20 hover:bg-blue-900/30 border-blue-700 text-blue-300'
                                  : 'bg-blue-50 hover:bg-blue-100 border-blue-200 text-blue-800'
                              }`}
                            >
                              Make it shorter
                            </button>
                            <button
                              onClick={() => setAiEditInstruction("Change the tone to be more professional")}
                              className={`text-left p-2 text-xs rounded border transition-colors ${
                                isDarkMode
                                  ? 'bg-blue-900/20 hover:bg-blue-900/30 border-blue-700 text-blue-300'
                                  : 'bg-blue-50 hover:bg-blue-100 border-blue-200 text-blue-800'
                              }`}
                            >
                              Professional tone
                            </button>
                            <button
                              onClick={() => setAiEditInstruction("Add a call-to-action at the end")}
                              className={`text-left p-2 text-xs rounded border transition-colors ${
                                isDarkMode
                                  ? 'bg-blue-900/20 hover:bg-blue-900/30 border-blue-700 text-blue-300'
                                  : 'bg-blue-50 hover:bg-blue-100 border-blue-200 text-blue-800'
                              }`}
                            >
                              Add call-to-action
                            </button>
                          </div>
                        </div>
                      </div>
                    </>
                  ) : (
                    /* AI Result Preview */
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        AI Generated {aiEditType === 'title' ? 'Title' : aiEditType === 'content' ? 'Content' : 'Hashtags'}
                      </label>
                      <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-sm text-gray-700 max-h-64 overflow-y-auto">
                        {aiEditedContent}
                      </div>
                      <p className="text-xs text-blue-600 mt-2">
                        ✨ AI has processed your content based on: "{aiEditInstruction}"
                      </p>
                    </div>
                  )}
                </div>

                {/* Action Buttons */}
                <div className="flex items-center justify-end space-x-3 mt-6 pt-4 border-t border-gray-200">
                  <button
                    onClick={handleCancelAIEdit}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                      isDarkMode
                        ? 'text-gray-400 bg-gray-700 hover:bg-gray-600'
                        : 'text-gray-600 bg-gray-100 hover:bg-gray-200'
                    }`}
                  >
                    {showAIResult ? 'Try Again' : 'Cancel'}
                  </button>
                  {!showAIResult ? (
                    <button
                      onClick={handleAISaveEdit}
                      disabled={aiEditing || !aiEditInstruction.trim() || aiEditInstruction.length > 500}
                      className="px-4 py-2 bg-gradient-to-r from-blue-500 to-indigo-500 text-white rounded-lg font-medium hover:from-blue-600 hover:to-indigo-600 transition-all duration-200 disabled:opacity-50 flex items-center space-x-2"
                    >
                      {aiEditing ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          <span>AI Editing...</span>
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-4 h-4" />
                          <span>Edit with AI</span>
                        </>
                      )}
                    </button>
                  ) : (
                    <button
                      onClick={handleSaveAIResult}
                      className="px-4 py-2 bg-gradient-to-r from-blue-500 to-indigo-500 text-white rounded-lg font-medium hover:from-blue-600 hover:to-indigo-600 transition-all duration-200 flex items-center space-x-2"
                    >
                      <Check className="w-4 h-4" />
                      <span>Save Changes</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ATSNContentModal
