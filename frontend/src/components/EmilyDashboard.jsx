import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useNotifications } from '../contexts/NotificationContext'
import { onboardingAPI } from '../services/onboarding'
import { supabase } from '../lib/supabase'
import SideNavbar from './SideNavbar'

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

    window.addEventListener('storage', handleStorageChange)

    // Also listen for custom events for same-tab updates
    const handleCustomChange = (e) => {
      if (e.detail.key === key) {
        callback(e.detail.value === 'true')
      }
    }

    window.addEventListener('localStorageChange', handleCustomChange)

    return () => {
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('localStorageChange', handleCustomChange)
    }
  }, [key, callback])
}

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'https://agent-emily.onrender.com').replace(/\/$/, '')
import MobileNavigation from './MobileNavigation'
import LoadingBar from './LoadingBar'
import MainContentLoader from './MainContentLoader'
import ATSNChatbot from './ATSNChatbot'
import RecentTasks from './RecentTasks'
import CustomContentChatbot from './CustomContentChatbot'
import ContentCard from './ContentCard'
import { Sparkles, TrendingUp, Target, BarChart3, FileText, Calendar, PanelRight, PanelLeft, X, ChevronRight, RefreshCw, ChevronDown } from 'lucide-react'

// Voice Orb Component with animated border (spring-like animation)
const VoiceOrb = ({ isSpeaking }) => {
  const [borderWidth, setBorderWidth] = useState(0)
  const velocityRef = useRef(0)
  const animationRef = useRef(null)
  const lastTimeRef = useRef(performance.now())

  useEffect(() => {
    if (isSpeaking) {
      // Spring animation parameters (similar to React Native Reanimated)
      const stiffness = 90
      const damping = 12
      const mass = 0.5
      const targetWidth = 8 + Math.random() * 4 // Vary between 8-12px based on "volume"
      
      const animate = (currentTime) => {
        const deltaTime = (currentTime - lastTimeRef.current) / 16.67 // Normalize to ~60fps
        lastTimeRef.current = currentTime
        
        setBorderWidth(prev => {
          const current = prev
          const diff = targetWidth - current
          
          // Spring physics: F = -kx - bv
          const springForce = (stiffness / mass) * diff
          const dampingForce = (damping / mass) * velocityRef.current
          const acceleration = springForce - dampingForce
          
          // Update velocity
          velocityRef.current += acceleration * (deltaTime * 0.01)
          velocityRef.current *= 0.95 // Additional damping
          
          // Update position
          const newWidth = current + velocityRef.current * (deltaTime * 0.01)
          
          return Math.max(0, newWidth)
        })
        
        if (isSpeaking) {
          animationRef.current = requestAnimationFrame(animate)
        }
      }
      lastTimeRef.current = performance.now()
      animationRef.current = requestAnimationFrame(animate)
    } else {
      // Smoothly return to 0 with spring animation
      const stiffness = 90
      const damping = 12
      const mass = 0.5
      const targetWidth = 0
      
      const animate = (currentTime) => {
        const deltaTime = (currentTime - lastTimeRef.current) / 16.67
        lastTimeRef.current = currentTime
        
        setBorderWidth(prev => {
          if (prev < 0.1 && Math.abs(velocityRef.current) < 0.1) {
            velocityRef.current = 0
            return 0
          }
          
          const current = prev
          const diff = targetWidth - current
          
          const springForce = (stiffness / mass) * diff
          const dampingForce = (damping / mass) * velocityRef.current
          const acceleration = springForce - dampingForce
          
          velocityRef.current += acceleration * (deltaTime * 0.01)
          velocityRef.current *= 0.95
          
          const newWidth = current + velocityRef.current * (deltaTime * 0.01)
          
          return Math.max(0, newWidth)
        })
        
        if (borderWidth > 0.1 || Math.abs(velocityRef.current) > 0.1) {
          animationRef.current = requestAnimationFrame(animate)
        }
      }
      lastTimeRef.current = performance.now()
      animationRef.current = requestAnimationFrame(animate)
    }

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [isSpeaking])

  return (
    <div className="relative flex items-center justify-center">
      {/* Outer animated border container */}
      <div 
        className="absolute rounded-full border-2 flex items-center justify-center"
        style={{
          width: '290px',
          height: '290px',
          borderRadius: '145px',
          borderWidth: `${borderWidth}px`,
          borderColor: isSpeaking ? 'rgb(96, 165, 250)' : 'transparent',
          transition: 'border-color 0.2s ease',
        }}
      >
        {/* Inner orb */}
        <div 
          className="rounded-full bg-gradient-to-br from-pink-400 to-purple-500 flex items-center justify-center"
          style={{
            width: '280px',
            height: '280px',
            borderRadius: '140px',
          }}
        >
          <span className="text-white font-bold text-4xl">E</span>
        </div>
      </div>
    </div>
  )
}

// Import components directly

function EmilyDashboard() {
  const { user, logout } = useAuth()
  const { showContentGeneration, showSuccess, showError, showInfo } = useNotifications()
  const navigate = useNavigate()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [isPanelOpen, setIsPanelOpen] = useState(true)
  const [conversations, setConversations] = useState([])
  const [loadingConversations, setLoadingConversations] = useState(false)
  const [atsnConversationToLoad, setAtsnConversationToLoad] = useState(null)
  const [selectedDate, setSelectedDate] = useState(() => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    return today
  })
  const hasSetInitialDate = useRef(false)
  const [messageFilter, setMessageFilter] = useState('all') // 'all', 'emily', 'chase', 'leo'
  const [dateFilter, setDateFilter] = useState('today') // 'today', 'yesterday', '2_days_ago', etc.
  const [showDateFilterDropdown, setShowDateFilterDropdown] = useState(false)
  const [showCustomContentChatbot, setShowCustomContentChatbot] = useState(false)
  const [showMobileChatHistory, setShowMobileChatHistory] = useState(false)
  const [isDarkMode, setIsDarkMode] = useState(getDarkModePreference)

  // Listen for dark mode changes from other components (like SideNavbar)
  useStorageListener('darkMode', setIsDarkMode)

  // Generate date filter options for past 7 days
  const dateFilterOptions = React.useMemo(() => {
    const options = []
    const today = new Date()

    for (let i = 0; i < 7; i++) {
      const date = new Date(today)
      date.setDate(today.getDate() - i)

      const dateStr = date.toISOString().split('T')[0]
      const displayText = i === 0 ? 'Today' :
                         i === 1 ? 'Yesterday' :
                         `${date.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric' })}`

      options.push({
        value: dateStr,
        label: displayText,
        date: date
      })
    }

    return options
  }, [])

  // Get selected date filter label
  const getSelectedDateFilterLabel = () => {
    const option = dateFilterOptions.find(opt => opt.value === dateFilter)
    return option ? option.label : 'Select Date'
  }

  const handleRefreshChat = async () => {
    try {
      const authToken = await getAuthToken()
      if (!authToken) {
        showError('Authentication required', 'Please log in again.')
        return
      }

      // Clear the partial payload cache on the backend
      const response = await fetch(`${API_BASE_URL}/chatbot/chat/v2/refresh`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        }
      })

      if (response.ok) {
        // Clear the chat messages in the frontend
        // ATSNChatbot handles chat clearing internally
        showSuccess('Chat refreshed', 'The conversation has been reset to start fresh.')
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to refresh chat' }))
        showError('Failed to refresh chat', errorData.detail || 'Please try again.')
      }
    } catch (error) {
      console.error('Error refreshing chat:', error)
      showError('Error refreshing chat', error.message || 'Please try again.')
    }
  }

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await onboardingAPI.getProfile()
        setProfile(response.data)
      } catch (error) {
        console.error('Error fetching profile:', error)
        // If profile doesn't exist, that's okay - user just completed onboarding
        setProfile(null)
      } finally {
        setLoading(false)
      }
    }

    if (user) {
      fetchProfile()
    } else {
      setLoading(false)
    }
  }, [user])

  // Fetch all conversations when panel opens
  useEffect(() => {
    if (isPanelOpen && user) {
      fetchAllConversations()
    }
  }, [isPanelOpen, user])

  // Set selectedDate to the most recent conversation date when conversations are first loaded
  useEffect(() => {
    if (conversations.length > 0 && !hasSetInitialDate.current) {
      const grouped = groupConversationsByDate(conversations)
      if (grouped.length > 0) {
        // Get the most recent date (first in sorted array)
        const mostRecentDate = grouped[0].dateObj
        setSelectedDate(new Date(mostRecentDate))
        hasSetInitialDate.current = true
      }
    }
  }, [conversations])

  // Reload ATSN conversations when date filter changes
  useEffect(() => {
    console.log('Date filter changed to:', dateFilter)
    if (user && dateFilter) {
      console.log('Loading conversations for date:', dateFilter)

      // First, clear any existing conversations to reset the chatbot
      setAtsnConversationToLoad(null)

      // Small delay to allow the chatbot to reset, then load new conversations
      setTimeout(() => {
        loadAtsnConversationsForDate().then(atsnConversations => {
          console.log('Reloaded ATSN conversations for date filter:', dateFilter, 'conversations:', atsnConversations)

          // Convert conversations to message format expected by ATSNChatbot
          if (atsnConversations && atsnConversations.length > 0) {
            let atsnMessages = []

            // Process ATSN conversations
            if (atsnConversations.length > 0) {
              // Use the first conversation for this date (they should be ordered by creation time)
              const conversation = atsnConversations[0]
              console.log('Processing conversation:', conversation.id, 'with', conversation.messages?.length || 0, 'messages')
              atsnMessages = conversation.messages.map(msg => ({
                id: msg.id,
                conversationId: conversation.id,
                sender: msg.sender,
                text: msg.text,
                timestamp: msg.timestamp,
                intent: msg.intent,
                agent_name: msg.agent_name,
                current_step: msg.current_step,
                clarification_question: msg.clarification_question,
                clarification_options: msg.clarification_options,
                content_items: msg.content_items,
                lead_items: msg.lead_items
              }))
            }

            console.log('Setting ATSN conversation to load:', atsnMessages.length, 'messages')
            setAtsnConversationToLoad([...atsnMessages])
          } else {
            console.log('No conversations found for date:', dateFilter)
            setAtsnConversationToLoad([])
          }
        }).catch(error => {
          console.error('Error loading conversations for date filter:', error)
          setAtsnConversationToLoad([])
        })
      }, 100)
    }
  }, [dateFilter, user])

  // Close date filter dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (showDateFilterDropdown && !event.target.closest('.date-filter-dropdown-container')) {
        setShowDateFilterDropdown(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showDateFilterDropdown])

  // Apply dark mode to document body
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
    // Save preference to localStorage
    localStorage.setItem('darkMode', isDarkMode.toString())
  }, [isDarkMode])

  const getAuthToken = async () => {
    const { data: { session } } = await supabase.auth.getSession()
    return session?.access_token
  }

  const fetchAllConversations = async () => {
    setLoadingConversations(true)
    try {
      const authToken = await getAuthToken()
      if (!authToken) {
        console.error('No auth token available')
        setLoadingConversations(false)
        return
      }

      const response = await fetch(`${API_BASE_URL}/chatbot/conversations?all=true`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        }
      })

      if (response.ok) {
        const data = await response.json()
        if (data.success && data.conversations) {
          setConversations(data.conversations)
        }
      }
    } catch (error) {
      console.error('Error fetching conversations:', error)
    } finally {
      setLoadingConversations(false)
    }
  }

  // Group conversations by date and get only the last conversation per date
  const groupConversationsByDate = (conversations) => {
    const grouped = {}
    const dateMap = {} // Map dateKey to actual Date object for sorting
    
    conversations.forEach(conv => {
      const date = new Date(conv.created_at)
      const dateKey = date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
      })
      
      if (!grouped[dateKey]) {
        grouped[dateKey] = []
        // Store the date object for sorting (use start of day)
        const dateForSorting = new Date(date)
        dateForSorting.setHours(0, 0, 0, 0)
        dateMap[dateKey] = dateForSorting
      }
      grouped[dateKey].push(conv)
    })

    // Sort dates (newest first) using the date objects
    const sortedDates = Object.keys(grouped).sort((a, b) => {
      return dateMap[b] - dateMap[a]
    })

    // Return only the last conversation for each date
    return sortedDates.map(date => {
      const dateConversations = grouped[date].sort((a, b) => 
        new Date(a.created_at) - new Date(b.created_at)
      )
      // Get the last conversation (most recent)
      const lastConversation = dateConversations[dateConversations.length - 1]
      // Also store the date object for filtering
      const dateObj = dateMap[date]
      
      return {
        date,
        dateObj, // Store date object for filtering
        lastConversation,
        allConversations: dateConversations // Store all conversations for this date
      }
    })
  }

  // Function to load ATSN conversations for the selected date filter
  const loadAtsnConversationsForDate = async () => {
    try {
      const authToken = await getAuthToken()
      if (!authToken) {
        console.error('No auth token available')
        return []
      }

      console.log('Fetching ATSN conversations for date:', dateFilter)
      const response = await fetch(`${API_BASE_URL}/atsn/conversations?date=${dateFilter}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        }
      })

      if (response.ok) {
        const data = await response.json()
        console.log('ATSN API response:', data)
        console.log('Number of conversations returned:', data.conversations?.length || 0)
        return data.conversations || []
      } else {
        const errorText = await response.text()
        console.error('Failed to load ATSN conversations:', response.status, errorText)
        return []
      }
    } catch (error) {
      console.error('Error loading ATSN conversations:', error)
      return []
    }
  }

  // Function to load conversations for a specific date
  const loadConversationsForDate = async (dateObj) => {
    try {
      const authToken = await getAuthToken()
      if (!authToken) {
        console.error('No auth token available')
        return
      }

      // Update selected date in header (use the date object directly to avoid timezone issues)
      setSelectedDate(new Date(dateObj))

      // Calculate date range for the selected date
      const startDate = new Date(dateObj)
      startDate.setHours(0, 0, 0, 0)
      const endDate = new Date(dateObj)
      endDate.setHours(23, 59, 59, 999)

      // Filter from already loaded conversations
      const dateConversations = conversations.filter(conv => {
        const convDate = new Date(conv.created_at)
        return convDate >= startDate && convDate <= endDate
      })

      // Also load ATSN conversations for this date
      const atsnConversations = await loadAtsnConversationsForDate()
      console.log('Loaded ATSN conversations:', atsnConversations)

      // Convert to message format and load in chatbot
      const conversationMessages = dateConversations
        .sort((a, b) => new Date(a.created_at) - new Date(b.created_at))
        .map(conv => {
          // Handle metadata - it might be None, dict, or string
          let metadata = conv.metadata
          if (typeof metadata === 'string') {
            try {
              metadata = JSON.parse(metadata)
            } catch {
              metadata = {}
            }
          }
          if (!metadata) metadata = {}
          
          return {
            id: `conv-${conv.id}`,
            type: conv.message_type === 'user' ? 'user' : 'bot',
            content: conv.content,
            timestamp: conv.created_at,
            isNew: false,
            scheduledMessageId: metadata?.scheduled_message_id || null
          }
        })

      // Remove duplicates based on scheduled_message_id
      const seenScheduledIds = new Set()
      const uniqueMessages = []
      for (const msg of conversationMessages) {
        if (msg.scheduledMessageId) {
          if (seenScheduledIds.has(msg.scheduledMessageId)) {
            continue
          }
          seenScheduledIds.add(msg.scheduledMessageId)
        }
        uniqueMessages.push(msg)
      }

      // Check if these are ATSN conversations and load them into ATSNChatbot
      const hasAtsnConversations = dateConversations.some(conv => {
        let metadata = conv.metadata
        if (typeof metadata === 'string') {
          try {
            metadata = JSON.parse(metadata)
          } catch {
            metadata = {}
          }
        }
        return metadata?.agent === 'atsn'
      }) || atsnConversations.length > 0

      if (hasAtsnConversations) {
        // Load ATSN conversations into the chatbot
        let atsnMessages = []

        // Process new format ATSN conversations (from ATSN conversations table)
        if (atsnConversations.length > 0) {
          // Use the first conversation for this date (they should be ordered by creation time)
          const conversation = atsnConversations[0]
          atsnMessages = conversation.messages.map(msg => ({
            id: msg.id,
            conversationId: conversation.id,
            sender: msg.sender,
            text: msg.text,
            timestamp: msg.timestamp,
            intent: msg.intent,
            agent_name: msg.agent_name,
            current_step: msg.current_step,
            clarification_question: msg.clarification_question,
            clarification_options: msg.clarification_options,
            content_items: msg.content_items,
            lead_items: msg.lead_items
          }))
        }

        // Always create a new array reference to ensure useEffect triggers
        console.log('Setting ATSN conversation to load:', atsnMessages)
        setAtsnConversationToLoad([...atsnMessages])
        // Clear after a short delay to allow ATSNChatbot to load them
        setTimeout(() => {
          console.log('Clearing ATSN conversation to load')
          setAtsnConversationToLoad(null)
        }, 100)
      } else {
        // Regular chatbot conversations are loaded internally
        // ATSNChatbot loads conversations internally via hooks
      }
    } catch (error) {
      console.error('Error loading conversations for date:', error)
    }
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-4">Not Authenticated</h1>
          <p className="text-gray-600">Please log in to access the dashboard.</p>
        </div>
      </div>
    )
  }


  return (
    <div className={`h-screen overflow-hidden md:overflow-auto ${
      isDarkMode ? 'bg-gray-900' : 'bg-white'
    }`}>
      {/* Mobile Navigation */}
      <MobileNavigation 
        setShowCustomContentChatbot={() => {}} // Dashboard doesn't have these functions
        handleGenerateContent={() => {}}
        generating={false}
        fetchingFreshData={false}
        onOpenChatHistory={() => {
          setShowMobileChatHistory(true)
          if (!conversations.length && user) {
            fetchAllConversations()
          }
        }}
        showChatHistory={showMobileChatHistory}
      />
      
      {/* Side Navbar */}
      <SideNavbar />
      
      {/* Main Content */}
      <div className={`md:ml-48 xl:ml-64 flex flex-col h-screen overflow-hidden pt-16 md:pt-0 bg-transparent ${
        isDarkMode ? 'md:bg-gray-900' : 'md:bg-white'
      }`}>
        {/* Header */}
        <div className={`hidden md:block shadow-sm border-b z-30 flex-shrink-0 ${
          isDarkMode ? 'bg-gray-900 border-gray-700' : 'bg-white border-gray-200'
        }`}>
          <div className="px-4 lg:px-6 py-3 lg:py-4">
            <div className="flex justify-between items-center">
              <div className="hidden md:flex items-center gap-3">
                {/* Agent Filter Icons */}
                <div className="flex items-center gap-1">
                  {/* All Messages */}
                  <button
                    onClick={() => setMessageFilter('all')}
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
                      messageFilter === 'all'
                        ? 'bg-gray-600 text-white ring-2 ring-gray-300'
                        : isDarkMode
                        ? 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    }`}
                    title="All Messages"
                  >
                    All
                  </button>

                  {/* Emily */}
                  <button
                    onClick={() => setMessageFilter('emily')}
                    className={`w-8 h-8 rounded-full flex items-center justify-center transition-all border-2 border-gray-300 ${
                      messageFilter === 'emily'
                        ? 'ring-2 ring-purple-300'
                        : 'hover:opacity-80'
                    }`}
                    title="Emily Messages"
                  >
                    <img src="/emily_icon.png" alt="Emily" className="w-9 h-9 rounded-full object-cover" />
                  </button>

                  {/* Chase */}
                  <button
                    onClick={() => setMessageFilter('chase')}
                    className={`w-8 h-8 rounded-full flex items-center justify-center transition-all border-2 border-gray-300 ${
                      messageFilter === 'chase'
                        ? 'ring-2 ring-blue-300'
                        : 'hover:opacity-80'
                    }`}
                    title="Chase Messages"
                  >
                    <img src="/chase_logo.png" alt="Chase" className="w-9 h-9 rounded-full object-cover" />
                  </button>

                  {/* Leo */}
                  <button
                    onClick={() => setMessageFilter('leo')}
                    className={`w-8 h-8 rounded-full flex items-center justify-center transition-all border-2 border-gray-300 ${
                      messageFilter === 'leo'
                        ? 'ring-2 ring-green-300'
                        : 'hover:opacity-80'
                    }`}
                    title="Leo Messages"
                  >
                    <img src="/leo_logo.jpg" alt="Leo" className="w-9 h-9 rounded-full object-cover" />
                  </button>
                </div>


                <span className={isDarkMode ? 'text-gray-500' : 'text-gray-400'}>|</span>
                <div className={`text-sm lg:text-base ${
                  isDarkMode ? 'text-gray-100' : 'text-gray-900'
                }`}>
                  {profile?.business_name || user?.user_metadata?.name || 'you'}
                </div>
                <span className={isDarkMode ? 'text-gray-500' : 'text-gray-400'}>|</span>
                {/* Date Filter Dropdown */}
                <div className="relative date-filter-dropdown-container">
                  <button
                    onClick={() => setShowDateFilterDropdown(!showDateFilterDropdown)}
                    className={`flex items-center gap-1 px-2 py-1 rounded text-sm transition-all hover:bg-opacity-80 ${
                      isDarkMode ? 'text-gray-300 hover:bg-gray-700' : 'text-gray-700 hover:bg-gray-100'
                    }`}
                    title="Filter conversations by date"
                  >
                    <span>{getSelectedDateFilterLabel()}</span>
                    <ChevronDown className={`w-3 h-3 transition-transform ${
                      showDateFilterDropdown ? 'rotate-180' : ''
                    }`} />
                  </button>

                  {showDateFilterDropdown && (
                    <div className={`absolute top-full mt-1 w-48 rounded-lg shadow-lg z-50 max-h-64 overflow-y-auto ${
                      isDarkMode
                        ? 'bg-gray-800 border border-gray-700 shadow-gray-900/50'
                        : 'bg-white border border-gray-200'
                    }`}>
                      {dateFilterOptions.map((option) => (
                        <button
                          key={option.value}
                          onClick={() => {
                            setDateFilter(option.value)
                            setShowDateFilterDropdown(false)
                          }}
                          className={`w-full text-left px-4 py-2 text-sm first:rounded-t-lg last:rounded-b-lg ${
                            dateFilter === option.value
                              ? 'bg-green-100 text-green-700 font-medium'
                              : isDarkMode
                              ? 'text-gray-200 hover:bg-gray-700'
                              : 'text-gray-700 hover:bg-gray-50'
                          }`}
                        >
                          {option.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              
              <div className="flex items-center gap-2">
                {/* Panel Toggle Button */}
                <button
                  onClick={() => setIsPanelOpen(!isPanelOpen)}
                  className={`p-2 rounded-md transition-colors border ${
                    isDarkMode
                      ? 'hover:bg-gray-700 border-gray-600 text-gray-300'
                      : 'hover:bg-gray-100 border-gray-200'
                  }`}
                  title={isPanelOpen ? "Close Panel" : "Open Panel"}
                >
                  {isPanelOpen ? (
                    <PanelLeft className={`w-5 h-5 ${
                      isDarkMode ? 'text-gray-300' : 'text-gray-700'
                    }`} />
                  ) : (
                    <PanelRight className={`w-5 h-5 ${
                      isDarkMode ? 'text-gray-300' : 'text-gray-700'
                    }`} />
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Main Content Area */}
        <div className={`flex-1 flex items-start bg-transparent h-full ${
          isDarkMode ? 'md:bg-gray-800' : 'md:bg-gray-50'
        }`} style={{ minHeight: 0, overflow: 'hidden' }}>
            <div className="w-full h-full flex gap-2">
                {/* Main Chat Area */}
              <div className="flex-1 h-full">
                <div className="h-full relative pt-0.5 px-8 overflow-x-auto">
                  <ATSNChatbot
                    key={`atsn-chatbot-${dateFilter}`}
                    externalConversations={atsnConversationToLoad}
                  />
                </div>
              </div>

              {/* Right Side Panel - Part of main content */}
              <div
                className={`hidden md:flex transition-all duration-300 ease-in-out overflow-hidden h-full ${
                  isDarkMode
                    ? 'bg-gray-900'
                    : 'bg-white'
                } ${
                  isPanelOpen ? 'w-48 xl:w-64' : 'w-0'
                }`}
              >
                {isPanelOpen && (
                  <div className="h-full flex flex-col">
                    {/* Panel Header */}
                    <div className={`p-3 lg:p-4 border-b flex items-center justify-between flex-shrink-0 ${
                      isDarkMode
                        ? 'border-gray-700'
                        : 'border-gray-200'
                    }`}>
                      <span className={`text-sm font-medium ${
                        isDarkMode ? 'text-gray-200' : 'text-gray-700'
                      }`}>
                        Reminders
                      </span>
                    </div>


                    {/* Panel Content */}
                    <div className="flex-1 overflow-y-auto p-4">
                      {loadingConversations ? (
                        <div className="flex items-center justify-center py-8">
                          <div className={`text-sm ${
                            isDarkMode ? 'text-gray-400' : 'text-gray-500'
                          }`}>Loading conversations...</div>
                        </div>
                      ) : conversations.length === 0 ? (
                        <div className="flex items-center justify-center py-8">
                          <div className={`text-sm ${
                            isDarkMode ? 'text-gray-400' : 'text-gray-500'
                          }`}>No conversations yet</div>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          {groupConversationsByDate(conversations).map(({ date, dateObj, lastConversation }) => {
                            if (!lastConversation) return null
                            
                            const isUser = lastConversation.message_type === 'user'
                            const preview = lastConversation.content?.substring(0, 50) + (lastConversation.content?.length > 50 ? '...' : '')
                            const messageDate = new Date(lastConversation.created_at)
                            const formattedDate = messageDate.toLocaleDateString('en-US', { 
                              month: 'short', 
                              day: 'numeric',
                              year: messageDate.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined
                            })
                            
                            // Check if this date is selected
                            const isSelected = selectedDate && 
                              selectedDate.toDateString() === new Date(dateObj).toDateString()
                            
                            return (
                              <div key={date}>
                                <div
                                  onClick={() => {
                                    setSelectedDate(new Date(dateObj))
                                    loadConversationsForDate(dateObj)
                                  }}
                                  className={`p-2 rounded-lg cursor-pointer transition-colors ${
                                    isSelected 
                                      ? isDarkMode ? 'bg-gray-700' : 'bg-gray-100'
                                      : isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-50'
                                  }`}
                                >
                                  <div className="flex items-center gap-2">
                                    <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-sm ${
                                      isUser ? 'bg-pink-400' : 'bg-gradient-to-br from-pink-400 to-purple-500'
                                    }`}>
                                      {isUser ? (
                                        profile?.logo_url ? (
                                          <img src={profile.logo_url} alt="User" className="w-10 h-10 rounded-full object-cover" />
                                        ) : (
                                          <span className="text-white">U</span>
                                        )
                                      ) : (
                                        <span className="text-white font-bold">E</span>
                                      )}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                      <div className="flex items-center justify-between mb-1">
                                        <span className={`text-xs font-medium ${
                                          isUser
                                            ? 'text-pink-400'
                                            : isDarkMode ? 'text-purple-300' : 'text-purple-700'
                                        }`}>
                                          {isUser ? 'You' : 'Emily'}
                                        </span>
                                        <span className={`text-xs ${
                                          isDarkMode ? 'text-gray-500' : 'text-gray-400'
                                        }`}>{formattedDate}</span>
                                      </div>
                                      <p className={`text-xs line-clamp-2 ${
                                        isDarkMode ? 'text-gray-300' : 'text-gray-700'
                                      }`}>{preview}</p>
                  </div>
                </div>
              </div>
            </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                )}
          </div>
        </div>
      </div>
      </div>

      {/* Custom Content Chatbot Modal */}
      <CustomContentChatbot
        isOpen={showCustomContentChatbot}
        onClose={() => setShowCustomContentChatbot(false)}
        onContentCreated={async (content) => {
          console.log('onContentCreated called with content:', content)
          setShowCustomContentChatbot(false)
          
          // Create chatbot message with post card
          if (content && user?.id) {
            try {
              console.log('Creating chatbot message for post:', content)
              
              // Format scheduled date and time
              const scheduledDate = content.scheduled_date || content.scheduled_at?.split('T')[0]
              const scheduledTime = content.scheduled_time || content.scheduled_at?.split('T')[1]?.split('.')[0] || '12:00:00'
              
              let formattedDate = 'Not scheduled'
              let formattedTime = ''
              
              if (scheduledDate) {
                try {
                  const dateObj = new Date(`${scheduledDate}T${scheduledTime}`)
                  if (!isNaN(dateObj.getTime())) {
                    formattedDate = dateObj.toLocaleDateString('en-US', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric'
                    })
                    formattedTime = dateObj.toLocaleTimeString('en-US', {
                      hour: 'numeric',
                      minute: '2-digit',
                      hour12: true
                    })
                  }
                } catch (dateError) {
                  console.error('Error formatting date:', dateError)
                }
              }
              
              const businessName = profile?.business_name || user?.user_metadata?.name || 'your business'
              
              // Create message content
              const messageContent = `Generated this post for ${businessName}`
              
              // Create chatbot message with post data in metadata
              const chatbotMessageData = {
                user_id: user.id,
                message_type: 'bot',
                content: messageContent,
                intent: 'post_generated',
                metadata: {
                  sender: 'leo',
                  post_data: content,
                  scheduled_date: formattedDate,
                  scheduled_time: formattedTime,
                  notification_type: 'post_generated'
                }
              }
              
              console.log('Inserting chatbot message:', chatbotMessageData)
              
              // Insert into Supabase
              const { data, error } = await supabase
                .from('chatbot_conversations')
                .insert(chatbotMessageData)
                .select()
                .single()
              
              if (error) {
                console.error('Error creating chatbot message:', error)
                showError('Failed to create chatbot notification')
              } else {
                console.log('Chatbot message created successfully:', data)
                // The realtime subscription should pick this up automatically
              }
            } catch (error) {
              console.error('Error handling post creation:', error)
              showError('Failed to create chatbot notification')
            }
          } else {
            console.warn('onContentCreated called but content or user is missing:', { content, userId: user?.id })
          }
        }}
      />
      

      {/* Mobile Chat History Panel - Full Screen */}
      {showMobileChatHistory && (
        <div className="md:hidden fixed inset-0 z-50 bg-white">
          <div className="flex flex-col h-full">
            {/* Header */}
            <div className="p-4 border-b border-gray-200 flex items-center justify-between bg-gray-50 flex-shrink-0">
              <h2 className="text-lg font-semibold text-gray-900">Chat History</h2>
              <button
                onClick={() => setShowMobileChatHistory(false)}
                className="p-2 rounded-md hover:bg-gray-200 transition-colors"
                title="Close"
              >
                <X className="w-5 h-5 text-gray-600" />
              </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-4">
              {loadingConversations ? (
                <div className="flex items-center justify-center py-8">
                  <div className="text-sm text-gray-500">Loading conversations...</div>
                </div>
              ) : conversations.length === 0 ? (
                <div className="flex items-center justify-center py-8">
                  <div className="text-sm text-gray-500">No conversations yet</div>
                </div>
              ) : (
                <div className="space-y-4">
                  {groupConversationsByDate(conversations).map(({ date, dateObj, lastConversation }) => {
                    if (!lastConversation) return null
                    
                    const isUser = lastConversation.message_type === 'user'
                    const preview = lastConversation.content?.substring(0, 50) + (lastConversation.content?.length > 50 ? '...' : '')
                    const messageDate = new Date(lastConversation.created_at)
                    const formattedDate = messageDate.toLocaleDateString('en-US', { 
                      month: 'short', 
                      day: 'numeric',
                      year: messageDate.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined
                    })
                    
                    // Check if this date is selected
                    const isSelected = selectedDate && 
                      selectedDate.toDateString() === new Date(dateObj).toDateString()
                    
                    return (
                      <div key={date}>
                        <div
                          onClick={() => {
                            setSelectedDate(new Date(dateObj))
                            loadConversationsForDate(dateObj)
                            setShowMobileChatHistory(false)
                          }}
                          className={`p-3 rounded-lg cursor-pointer transition-colors ${
                            isSelected 
                              ? 'bg-gray-100'
                              : 'hover:bg-gray-50'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-sm ${
                              isUser ? 'bg-pink-400' : 'bg-gradient-to-br from-pink-400 to-purple-500'
                            }`}>
                              {isUser ? (
                                profile?.logo_url ? (
                                  <img src={profile.logo_url} alt="User" className="w-10 h-10 rounded-full object-cover" />
                                ) : (
                                  <span className="text-white">U</span>
                                )
                              ) : (
                                <span className="text-white font-bold">E</span>
                              )}
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center justify-between mb-1">
                                <span className={`text-sm font-medium ${isUser ? 'text-pink-700' : 'text-purple-700'}`}>
                                  {isUser ? 'You' : 'Emily'}
                                </span>
                                <span className="text-xs text-gray-400">{formattedDate}</span>
                              </div>
                              <p className="text-sm text-gray-700 line-clamp-2">{preview}</p>
                              <p className="text-xs text-gray-500 mt-1">{date}</p>
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default EmilyDashboard

