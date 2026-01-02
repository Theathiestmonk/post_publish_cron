import React, { useState, useEffect, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useNotifications } from '../contexts/NotificationContext'
import { supabase } from '../lib/supabase'
import { Send, ArrowRight, User, Bot, RefreshCw, MessageCircle, Clock, AlertCircle, Trash2, Square, CheckSquare, Edit, Share, Calendar, Save, Copy, Upload, Video, Mail, Phone, Heart } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import ContentCard from './ContentCard'
import ATSNContentCard from './ATSNContentCard'
import ATSNContentModal from './ATSNContentModal'
import LeadCard from './LeadCard'
import MultiMediaUpload from './MultiMediaUpload'
import CharacterCard from './CharacterCard'
import { leadsAPI } from '../services/leads'
import { connectionsAPI } from '../services/connections'
import { mediaAPI } from '../services/api'

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

// Get API URL
const getApiBaseUrl = () => {
  const envUrl = import.meta.env.VITE_API_URL
  if (envUrl) {
    if (envUrl.startsWith(':')) {
      return `http://localhost${envUrl}`
    }
    if (!envUrl.startsWith('http://') && !envUrl.startsWith('https://')) {
      return `http://${envUrl}`
    }
    return envUrl
  }
  return 'http://localhost:8000'
}
const API_BASE_URL = getApiBaseUrl().replace(/\/$/, '')

const ATSNChatbot = ({ externalConversations = null }) => {
  const { user } = useAuth()
  const { showError, showSuccess } = useNotifications()
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [isPublishing, setIsPublishing] = useState(false)
  const [conversationHistory, setConversationHistory] = useState([])
  const [agentStatus, setAgentStatus] = useState(null)
  const [selectedContent, setSelectedContent] = useState([])
  const [selectedLeadId, setSelectedLeadId] = useState(null)
  const [selectedLeads, setSelectedLeads] = useState([])
  const [leadFilters, setLeadFilters] = useState({
    status: '',
    source: '',
    search: '',
    dateFrom: '',
    dateTo: ''
  })
  const [fetchedLeads, setFetchedLeads] = useState({})
  const [isDeleting, setIsDeleting] = useState(false)
  const [isScheduling, setIsScheduling] = useState(false)
  const [showScheduleModal, setShowScheduleModal] = useState(false)
  const [isConnecting, setIsConnecting] = useState(false)
  const [showEditLeadModal, setShowEditLeadModal] = useState(false)
  const [editLeadData, setEditLeadData] = useState(null)
  const [scheduleData, setScheduleData] = useState({ date: '', time: '', contentId: null })
  const [currentRequestIntent, setCurrentRequestIntent] = useState(null)
  const [lastSentMessage, setLastSentMessage] = useState('')
  const [showContentModal, setShowContentModal] = useState(false)
  const [chatReset, setChatReset] = useState(false) // Track if chat was reset
  const [selectedContentForModal, setSelectedContentForModal] = useState(null)
  const [showDatePicker, setShowDatePicker] = useState(false)
  const [selectedDateRange, setSelectedDateRange] = useState({ start: '', end: '' })
  const [showSingleDatePicker, setShowSingleDatePicker] = useState(false)
  const [selectedSingleDate, setSelectedSingleDate] = useState('')
  const [thinkingPhase, setThinkingPhase] = useState(0) // 0: assigning, 1: contacting, 2: invoking, 3: working
  const [isFirstMessage, setIsFirstMessage] = useState(true) // Track if this is the first message in session
  const [showMediaUploadModal, setShowMediaUploadModal] = useState(false)
  const [uploadedMediaUrls, setUploadedMediaUrls] = useState([])
  const [selectedFilesForUpload, setSelectedFilesForUpload] = useState([])
  const [isUploadingMedia, setIsUploadingMedia] = useState(false)
  const [tooltipAgent, setTooltipAgent] = useState(null)
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 })
  const [isDarkMode, setIsDarkMode] = useState(getDarkModePreference)
  const [likedMessages, setLikedMessages] = useState(new Set())
  const [countedTasks, setCountedTasks] = useState(new Set())
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const lastExternalConversationsRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  // 1️⃣ Intent-based global keypress handler
  const handleGlobalKeyPress = useRef((e) => {
    const input = inputRef.current;

    // Ignore shortcuts
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    // Ignore non-character keys
    if (e.key.length !== 1) return;

    // Ignore if typing in another input (MODALS, forms, etc.)
    const target = e.target;
    const isEditable =
      target.tagName === "INPUT" ||
      target.tagName === "TEXTAREA" ||
      target.tagName === "SELECT" ||
      target.isContentEditable;

    if (isEditable) return;

    // Ignore if user is selecting text
    if (window.getSelection().toString().length > 0) return;

    // 🔑 KEY: Ignore if any modal is open
    if (showEditLeadModal || showScheduleModal || showContentModal || showMediaUploadModal || showDatePicker || showSingleDatePicker) return;

    // Only then focus chat input
    input.focus();
  });

  // 2️⃣ Handle clicking in chat area to focus input
  const handleChatAreaClick = (e) => {
    // Prevent focusing when clicking links or buttons or form elements
    if (e.target.closest("a, button, input, textarea, select")) return;

    // Prevent focusing when modals are open
    if (showEditLeadModal || showScheduleModal || showContentModal || showMediaUploadModal || showDatePicker || showSingleDatePicker) return;

    inputRef.current?.focus();
  };

  // 3️⃣ Handle escape key to unfocus (accessibility)
  const handleEscapeKey = useRef((e) => {
    if (e.key === "Escape") {
      inputRef.current?.blur();
    }
  });

  // Auto-focus input when component mounts
  useEffect(() => {
    // Add global keydown listener for typing anywhere
    window.addEventListener('keydown', handleGlobalKeyPress.current);

    // Add escape key handler for accessibility
    window.addEventListener('keydown', handleEscapeKey.current);

    return () => {
      window.removeEventListener('keydown', handleGlobalKeyPress.current);
      window.removeEventListener('keydown', handleEscapeKey.current);
    };
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Listen for dark mode changes from other components (like SideNavbar)
  useStorageListener('darkMode', setIsDarkMode)

  // Handle thinking message phases
  useEffect(() => {
    if (isLoading) {
      if (isFirstMessage) {
        // First message phases
        const phaseTimers = [
          setTimeout(() => setThinkingPhase(1), 1000), // Contacting after 1s
          setTimeout(() => setThinkingPhase(2), 2000), // Invoking after 2s
          setTimeout(() => setThinkingPhase(3), 3000), // Working after 3s
        ]
        return () => phaseTimers.forEach(clearTimeout)
      } else {
        // Subsequent message phases
        const phaseTimers = [
          setTimeout(() => setThinkingPhase(1), 1000), // Processing after 1s
          setTimeout(() => setThinkingPhase(2), 2000), // Finalizing after 2s
          setTimeout(() => setThinkingPhase(3), 3000), // Almost done after 3s
        ]
        return () => phaseTimers.forEach(clearTimeout)
      }
    } else if (!isLoading && isFirstMessage && messages.length > 0) {
      // Find the last user message and mark as not first message
      const lastUserMessage = messages.slice().reverse().find(msg => msg.sender === 'user')
      if (lastUserMessage) {
        setIsFirstMessage(false)
        setThinkingPhase(0) // Reset phase for subsequent messages
      }
    } else if (!isLoading && !isFirstMessage) {
      // Reset phase for next subsequent message
      setThinkingPhase(0)
    }
  }, [isLoading, isFirstMessage, messages])

  // Auto-select content for created_content messages
  useEffect(() => {
    const latestMessage = messages[messages.length - 1]
    if (latestMessage && latestMessage.intent === 'created_content' && latestMessage.content_items && latestMessage.content_items.length > 0) {
      // Automatically select the single created content item
      setSelectedContent([latestMessage.content_items[0].content_id])
    }
  }, [messages])

  // Auto-select lead for messages with lead_id and fetch lead data
  useEffect(() => {
    const latestMessage = messages[messages.length - 1]
    if (latestMessage && latestMessage.lead_id && !latestMessage.lead_items) {
      // Automatically select the created lead
      setSelectedLeadId(latestMessage.lead_id)

      // Fetch lead data from Supabase
      const fetchLeadData = async () => {
        try {
          console.log('Fetching lead data for ID:', latestMessage.lead_id)
          const response = await leadsAPI.getLead(latestMessage.lead_id)
          console.log('Lead data fetched:', response)

          if (response && response.data) {
            // Store fetched lead data separately
            setFetchedLeads(prev => ({
              ...prev,
              [latestMessage.lead_id]: response.data
            }))
          }
        } catch (error) {
          console.error('Error fetching lead data:', error)
          showError('Failed to load lead details')
        }
      }

      fetchLeadData()
    }
  }, [messages, showError])

  // Handle OAuth connections when needed
  useEffect(() => {
    const latestMessage = messages[messages.length - 1]
    if (latestMessage && latestMessage.sender === 'bot' && latestMessage.needs_connection && latestMessage.connection_platform) {
      console.log('Connection required for platform:', latestMessage.connection_platform)
      console.log('Full message:', latestMessage)
      // Automatically trigger OAuth connection
      handleConnectionRequired(latestMessage.connection_platform)
    }
  }, [messages])

  // Get authentication token from session
  const getAuthToken = async () => {
    const { data: { session } } = await supabase.auth.getSession()
    return session?.access_token
  }

  // Load conversations from database
  const loadConversations = async () => {
    try {
      const token = await getAuthToken()
      if (!token) return

      const response = await fetch(`${API_BASE_URL}/atsn/conversations`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        const data = await response.json()
        console.log('ATSN loadConversations response:', data)
        if (data.conversations && data.conversations.length > 0) {
          // Handle new conversation structure with embedded messages
          console.log(`Found ${data.conversations.length} ATSN conversations`)

          // Flatten all messages from all conversations
          const allMessages = []
          data.conversations.forEach(conv => {
            if (conv.messages && conv.messages.length > 0) {
              conv.messages.forEach(msg => {
                allMessages.push({
                  id: msg.id,
                  conversationId: conv.id,
                  sender: msg.sender,
                  text: msg.text,
                  timestamp: msg.timestamp,
                  intent: msg.intent,
                  agent_name: msg.agent_name,
                  current_step: msg.current_step,
                  clarification_question: msg.clarification_question,
                  clarification_options: msg.clarification_options,
                  content_items: msg.content_items,
                  lead_items: msg.lead_items,
                  isNew: false
                })
              })
            }
          })

          if (allMessages.length > 0) {
            // Sort messages by timestamp
            allMessages.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
            setMessages(allMessages)
            console.log(`Loaded ${allMessages.length} ATSN messages from ${data.conversations.length} conversations`)
            return // Don't show welcome message if we have conversations
          }
        }
      }
    } catch (error) {
      console.error('Error loading ATSN conversations:', error)
    }

    // Don't show automatic welcome message - only show when "New Chat" is clicked
  }


  // Load today's conversations when component mounts (like Chatbot.jsx)
  useEffect(() => {
    // Don't load external conversations if chat was reset
    if (chatReset) {
      setChatReset(false) // Reset the flag
      return
    }

    if (externalConversations) {
      // Load external conversations (from past discussions panel)
      console.log('Loading external conversations:', externalConversations)
      setMessages(externalConversations)
      // Scroll to bottom after loading external conversations
      setTimeout(() => scrollToBottom(), 100)
    } else if (user && messages.length === 0) {
      // Load all ATSN conversations (not just today's)
      loadConversations()
    }
  }, [user, externalConversations, chatReset])

  // Detect and count completed tasks when results are displayed
  useEffect(() => {
    if (messages.length > 0) {
      const lastMessage = messages[messages.length - 1]

      // Only count bot messages that contain actual task results and haven't been counted yet
      if (lastMessage.sender === 'bot' && !countedTasks.has(lastMessage.id)) {
        const hasContentResults = lastMessage.content_items && lastMessage.content_items.length > 0
        const hasLeadResults = lastMessage.lead_items && lastMessage.lead_items.length > 0
        const isMeaningfulIntent = lastMessage.intent && [
          'create_content', 'edit_content', 'publish_content',
          'delete_content', 'schedule_content', 'create_lead',
          'edit_lead', 'delete_lead', 'show_leads'
        ].includes(lastMessage.intent.toLowerCase())

        // Count task if it has results OR is a meaningful completed intent
        if (hasContentResults || hasLeadResults || isMeaningfulIntent) {
          // Mark as counted and increment
          setCountedTasks(prev => new Set([...prev, lastMessage.id]))

          // Use a timeout to avoid counting during rapid updates
          setTimeout(() => {
            incrementTaskCount()
          }, 500)
        }
      }
    }
  }, [messages])

  // Load today's conversations (similar to Chatbot.jsx)
  const loadTodayConversations = async () => {
    try {
      const token = await getAuthToken()
      if (!token) {
        console.error('No auth token available')
        return
      }

      const response = await fetch(`${API_BASE_URL}/atsn/conversations`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        }
      })

      if (!response.ok) {
        console.error('Failed to fetch today\'s conversations:', response.status)
        return
      }

      const data = await response.json()
      console.log('Today\'s conversations response:', data)

      if (data.conversations && data.conversations.length > 0) {
        // Handle new conversation structure with embedded messages
        console.log(`Found ${data.conversations.length} ATSN conversations for today`)

        // Flatten all messages from all conversations
        const allMessages = []
        data.conversations.forEach(conv => {
          if (conv.messages && conv.messages.length > 0) {
            conv.messages.forEach(msg => {
              allMessages.push({
                id: msg.id,
                conversationId: conv.id,
                sender: msg.sender,
                text: msg.text,
                timestamp: msg.timestamp,
                intent: msg.intent,
                agent_name: msg.agent_name,
                current_step: msg.current_step,
                clarification_question: msg.clarification_question,
                clarification_options: msg.clarification_options,
                content_items: msg.content_items,
                lead_items: msg.lead_items,
                isNew: false
              })
            })
          }
        })

        if (allMessages.length > 0) {
          // Sort messages by timestamp
          allMessages.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
          setMessages(allMessages)
          console.log(`Loaded ${allMessages.length} today's ATSN messages from ${data.conversations.length} conversations`)
        }
      }
    } catch (error) {
      console.error('Error loading today\'s conversations:', error)
    }
  }

  // Real-time conversation updates
  useEffect(() => {
    if (!user) return

    // Subscribe to real-time conversation updates for ATSN
    const channel = supabase
      .channel('atsn_conversations')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'chatbot_conversations',
          filter: `user_id=eq.${user.id}`
        },
        (payload) => {
          const newMessage = payload.new

          // Only process ATSN conversations
          if (newMessage.metadata?.agent === 'atsn') {
            // Determine agent_name with fallback logic
            let agent_name = newMessage.metadata?.agent_name
            if (!agent_name && newMessage.message_type === 'bot' && newMessage.intent) {
              // Fallback: determine agent from intent (similar to backend logic)
              const intent = newMessage.intent.toLowerCase()
              if (intent.includes('lead')) {
                agent_name = 'chase'
              } else if (['view_content', 'publish_content', 'delete_content'].includes(intent)) {
                agent_name = 'emily'
              } else if (['create_content', 'edit_content', 'schedule_content'].includes(intent)) {
                agent_name = 'leo'
              } else if (intent.includes('orio') || intent.includes('analytics')) {
                agent_name = 'orio'
              } else {
                agent_name = 'emily' // default
              }
            }

            const messageObj = {
              id: newMessage.id,
              conversationId: newMessage.id,
              sender: newMessage.message_type === 'user' ? 'user' : 'bot',
              text: newMessage.content,
              timestamp: newMessage.created_at,
              intent: newMessage.intent,
              agent_name: agent_name,
              isNew: true
            }

            setMessages(prev => {
              // Avoid duplicates
              const exists = prev.some(msg => msg.id === newMessage.id)
              if (exists) return prev

              return [...prev, messageObj]
            })
          }
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(channel)
    }
  }, [user])

  // Handle message copying
  const handleCopyMessage = async (message) => {
    try {
      // Extract text content from message
      let textToCopy = message.text || message.content || ''

      // For bot messages, get the content
      if (message.sender === 'bot' && !textToCopy) {
        textToCopy = message.content || ''
      }

      await navigator.clipboard.writeText(textToCopy)

      // Remove focus from input to allow text selection
      if (inputRef.current) {
        inputRef.current.blur()
      }

      showSuccess('Message copied to clipboard')
    } catch (error) {
      console.error('Error copying message:', error)
      showError('Failed to copy message')
    }
  }

  const handleDeleteMessage = async (message) => {
    if (!message.conversationId) {
      // If it's a local message (not saved to Supabase), just remove from UI
      setMessages(prev => prev.filter(msg => msg.id !== message.id))
      return
    }

    try {
      const token = await getAuthToken()
      if (!token) {
        throw new Error('No authentication token available')
      }

      const response = await fetch(`${API_BASE_URL}/chatbot/conversations/${message.conversationId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (response.ok) {
        // Remove from UI
        setMessages(prev => prev.filter(msg => msg.id !== message.id))
        showSuccess('Message deleted successfully')
      } else {
        throw new Error('Failed to delete message')
      }
    } catch (error) {
      console.error('Error deleting message:', error)
      showError('Failed to delete message')
    }
  }

  const handleLikeMessage = async (message) => {
    const isCurrentlyLiked = likedMessages.has(message.id)

    // Update local state immediately for better UX
    setLikedMessages(prev => {
      const newSet = new Set(prev)
      if (isCurrentlyLiked) {
        newSet.delete(message.id)
        showSuccess('Message unliked')
      } else {
        newSet.add(message.id)
        showSuccess('Message liked')
      }
      return newSet
    })

    // If liking (not unliking) and message has an agent_name, increment likes count
    if (!isCurrentlyLiked && message.agent_name) {
      try {
        const token = await getAuthToken()
        if (!token) {
          console.error('No auth token available')
          return
        }

        const response = await fetch(`${API_BASE_URL}/agents/${message.agent_name}/like`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        })

        if (!response.ok) {
          console.error('Failed to increment likes count')
          // Optionally revert the local state if API call fails
        }
      } catch (error) {
        console.error('Error incrementing likes count:', error)
      }
    }
  }

  const incrementTaskCount = async () => {
    try {
      const token = await getAuthToken()
      if (!token) {
        console.error('No auth token available for task increment')
        return
      }

      const response = await fetch(`${API_BASE_URL}/profile/increment-task`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        console.log('Task count incremented successfully')
      } else {
        console.error('Failed to increment task count')
      }
    } catch (error) {
      console.error('Error incrementing task count:', error)
    }
  }

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return

    const userMessage = inputMessage.trim()
    const messageId = Date.now()

    // Add user message
    setMessages(prev => [...prev, {
      id: messageId,
      sender: 'user',
      text: userMessage,
      timestamp: new Date().toISOString()
    }])

    // Calculate updated conversation history (don't rely on async state update)
    const updatedHistory = [...conversationHistory, userMessage]
    
    // Store the message for loading detection
    setLastSentMessage(inputMessage)

    // Update conversation history state
    setConversationHistory(updatedHistory)
    setInputMessage('')
    setIsLoading(true)

    try {
      // Get token from session
      const token = await getAuthToken()
      
      if (!token) {
        throw new Error('No authentication session found. Please log in again.')
      }

      const response = await fetch(`${API_BASE_URL}/atsn/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: userMessage,
          conversation_history: updatedHistory
        })
      })

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication failed. Please log in again.')
        }
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()


      // Add bot response
      setMessages(prev => [...prev, {
        id: Date.now(),
        sender: 'bot',
        text: data.response,
        timestamp: new Date().toISOString(),
        intent: data.intent,
        step: data.current_step,
        payload: data.payload,
        waiting_for_user: data.waiting_for_user,
        payload_complete: data.payload_complete,
        error: data.error,
        content_items: data.content_items || null,
        lead_id: data.lead_id || null,
        lead_items: data.lead_items || null,
        agent_name: data.agent_name || 'emily',
        clarification_options: data.clarification_options || [],
        needs_connection: data.needs_connection || false,
        connection_platform: data.connection_platform || null
      }])

      // Update agent status
      setAgentStatus({
        intent: data.intent,
        step: data.current_step,
        waiting: data.waiting_for_user,
        complete: data.payload_complete
      })

    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage = error.message || 'Failed to send message. Please try again.'
      showError(errorMessage)
      
      setMessages(prev => [...prev, {
        id: Date.now(),
        sender: 'bot',
        text: `❌ ${errorMessage}\n\n${error.message?.includes('authentication') ? 'Please refresh the page and log in again.' : 'Please try again or reset the conversation.'}`,
        timestamp: new Date().toISOString(),
        error: true
      }])
    } finally {
      setIsLoading(false)
      setLastSentMessage('')

      // Refocus input for continued conversation
      setTimeout(() => {
        inputRef.current?.focus()
      }, 100)
    }
  }

  const handleReset = async () => {
    try {
      // Get token from session
      const token = await getAuthToken()

      if (!token) {
        throw new Error('No authentication session found. Please log in again.')
      }

      await fetch(`${API_BASE_URL}/atsn/reset`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      // Clear all messages and state
      setConversationHistory([])
      setAgentStatus(null)
      setIsFirstMessage(true) // Reset to show "assigning agent" for first message
      setThinkingPhase(0) // Reset phase

      // Clear any selected content/leads
      setSelectedContent([])
      setSelectedLeadId(null)
      setFetchedLeads({})

      // Clear input
      setInputMessage('')
      setLastSentMessage('')

      // Reset loading states
      setIsLoading(false)
      setIsPublishing(false)
      setIsDeleting(false)
      setIsScheduling(false)
      setShowScheduleModal(false)
      setCurrentRequestIntent(null)

      // Mark chat as reset to prevent loading external conversations
      setChatReset(true)

      // Set a short, human-like welcome message
      setMessages([{
        id: 'welcome-new-chat',
        sender: 'bot',
        text: `Hi! I'm your ATSN team - Emily, Leo, and Chase.\n\nTogether we can help you create and manage content, publish across platforms, and nurture your leads.\n\nWhat would you like to do today?`,
        timestamp: new Date().toISOString(),
        intent: null,
        agent_name: 'atsn' // Special agent name for welcome message
      }])

      showSuccess('New chat started successfully')
    } catch (error) {
      console.error('Error resetting:', error)
      showError(error.message || 'Failed to start new chat')
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // Content selection functions
  const handleContentSelect = (contentId, intent) => {
    if (intent === 'publish_content') {
      // Single selection for publishing
      setSelectedContent([contentId])
    } else {
      // Multi-selection for other intents
      setSelectedContent(prev => {
        if (prev.includes(contentId)) {
          return prev.filter(id => id !== contentId)
        } else {
          return [...prev, contentId]
        }
      })
    }
  }

  // Lead selection functions
  const handleLeadSelect = (leadId, intent) => {
    if (intent === 'delete_leads') {
      // Single selection for deletion
      setSelectedLeads([leadId])
    } else {
      // Multi-selection for other operations
      setSelectedLeads(prev => {
        if (prev.includes(leadId)) {
          return prev.filter(id => id !== leadId)
        } else {
          return [...prev, leadId]
        }
      })
    }
  }

  const handleSelectAll = (contentItems) => {
    const allIds = contentItems.map(item => item.content_id)
    setSelectedContent(allIds)
  }

  const handleDeselectAll = () => {
    setSelectedContent([])
  }

  const handleContentClick = (contentItem) => {
    // Process the content item the same way as for ATSNContentCard
    const processedContent = {
      id: contentItem.content_id,
      title: contentItem.title_display || contentItem.title,
      content: contentItem.content_text || contentItem.content_preview,
      hashtags: contentItem.hashtags_display ?
        contentItem.hashtags_display.split(' ').filter(tag => tag.startsWith('#')).map(tag => tag.substring(1)) :
        (contentItem.hashtags ?
          (Array.isArray(contentItem.hashtags) ? contentItem.hashtags : []) :
          (contentItem.raw_data?.hashtags ?
            (Array.isArray(contentItem.raw_data.hashtags) ? contentItem.raw_data.hashtags : []) :
            [])),
      media_url: contentItem.media_url,
      images: contentItem.images || [],
      metadata: contentItem.metadata || {},
      post_type: contentItem.raw_data?.post_type,
      content_type: contentItem.content_type,
      selected_content_type: contentItem.raw_data?.selected_content_type,
      carousel_images: contentItem.raw_data?.carousel_images || contentItem.raw_data?.images,
      // Add additional fields for different content types
      email_subject: contentItem.email_subject,
      email_body: contentItem.email_body,
      short_video_script: contentItem.short_video_script,
      long_video_script: contentItem.long_video_script,
      message: contentItem.message,
      platform: contentItem.platform
    }

    setSelectedContentForModal(processedContent)
    setShowContentModal(true)
  }

  const handleCloseContentModal = () => {
    setShowContentModal(false)
    setSelectedContentForModal(null)
  }

  const handleDeleteSelected = async () => {
    if (selectedContent.length === 0) {
      showError('Please select at least one item to delete')
      return
    }

    if (!window.confirm(`Are you sure you want to delete ${selectedContent.length} content item(s)? This action cannot be undone.`)) {
      return
    }

    setIsDeleting(true)

    try {
      const token = await getAuthToken()

      // Delete selected content items from Supabase
      for (const contentId of selectedContent) {
        const { error } = await supabase
          .from('created_content')
          .delete()
          .eq('id', contentId)
          .eq('user_id', user.id) // Security: ensure user can only delete their own content

        if (error) {
          console.error(`Error deleting content ${contentId}:`, error)
          showError(`Failed to delete content: ${error.message}`)
          return
        }
      }

      // Add success message
      setMessages(prev => [...prev, {
        id: Date.now(),
        sender: 'bot',
        text: `Successfully deleted ${selectedContent.length} content item(s)`,
        timestamp: new Date().toISOString()
      }])

      // Clear selection
      setSelectedContent([])
      showSuccess(`Successfully deleted ${selectedContent.length} content item(s)`)

    } catch (error) {
      console.error('Error deleting content:', error)
      showError(error.message || 'Failed to delete content')
    } finally {
      setIsDeleting(false)
    }
  }

  const handleEditSelected = () => {
    if (selectedContent.length === 0) {
      showError('Please select a content item to edit')
      return
    }
    if (selectedContent.length > 1) {
      showError('Please select only one item to edit')
      return
    }

    // Open image editor modal - this would need to be implemented
    // For now, just show a placeholder
    console.log('Edit content:', selectedContent[0])
    showError('Image editor modal coming soon!')

    // Clear selection after action
    setSelectedContent([])
  }

  const handlePublishSelected = async () => {
    if (selectedContent.length === 0) {
      showError('Please select at least one item to publish')
      return
    }

    setIsPublishing(true)

    try {
      for (const contentId of selectedContent) {
        // Find the content item from messages
        let contentToPublish = null
        for (const message of messages) {
          if (message.content_items) {
            contentToPublish = message.content_items.find(item => item.content_id === contentId)
            if (contentToPublish) break
          }
        }

        if (!contentToPublish) {
          console.error(`Content with ID ${contentId} not found`)
          continue
        }

        // Check if already published
        const status = contentToPublish.status?.toLowerCase()
        if (status === 'published') {
          showError('Post Already Published', 'This post has already been published.')
          continue
        }

        // Check if platform is connected
        if (!isPlatformConnected(contentToPublish.platform)) {
          showError('Account Not Connected', `Please connect your ${contentToPublish.platform} account in Settings > Connections before publishing.`)
          continue
        }

        console.log('Posting content to', contentToPublish.platform, ':', contentToPublish)

        try {
          // Handle different platforms
          if (contentToPublish.platform.toLowerCase() === 'facebook') {
            await postToFacebook(contentToPublish)
          } else if (contentToPublish.platform.toLowerCase() === 'instagram') {
            await postToInstagram(contentToPublish)
          } else if (contentToPublish.platform.toLowerCase() === 'linkedin') {
            await postToLinkedIn(contentToPublish)
          } else if (contentToPublish.platform.toLowerCase() === 'youtube') {
            await postToYouTube(contentToPublish)
          } else {
            showError(`${contentToPublish.platform} posting not yet implemented`)
            continue
          }

          showSuccess(`Successfully published to ${contentToPublish.platform}!`)

        } catch (error) {
          console.error('Error posting content:', error)
          showError(`Failed to post to ${contentToPublish.platform}: ${error.message}`)
        }
      }

    } catch (error) {
      console.error('Error in publish process:', error)
      showError('Publishing failed', error.message || 'An unexpected error occurred during publishing.')
    } finally {
      setIsPublishing(false)
      setSelectedContent([])
    }
  }

  const isPlatformConnected = (platform) => {
    // This would need to check user's connected platforms
    // For now, return true as placeholder - you might want to implement this properly
    return true
  }

  const handleScheduleSelected = () => {
    if (selectedContent.length === 0) {
      showError('Please select a content item to schedule')
      return
    }
    if (selectedContent.length > 1) {
      showError('Please select only one item to schedule')
      return
    }

    // Open schedule modal
    setScheduleData({ date: '', time: '', contentId: selectedContent[0] })
    setShowScheduleModal(true)
  }

  const handleScheduleConfirm = async () => {
    if (!scheduleData.date || !scheduleData.time) {
      showError('Please select both date and time')
      return
    }

    setIsScheduling(true)

    try {
      const token = await getAuthToken()

      // Combine date and time
      const scheduleDateTime = new Date(`${scheduleData.date}T${scheduleData.time}`)

      // Update the content with schedule information
      const { error } = await supabase
        .from('created_content')
        .update({
          status: 'scheduled',
          scheduled_at: scheduleDateTime.toISOString()
        })
        .eq('id', scheduleData.contentId)
        .eq('user_id', user.id)

      if (error) {
        console.error('Error scheduling content:', error)
        showError(`Failed to schedule content: ${error.message}`)
        return
      }

      // Add success message
      setMessages(prev => [...prev, {
        id: Date.now(),
        sender: 'bot',
        text: `Content scheduled for ${scheduleData.date} at ${scheduleData.time}`,
        timestamp: new Date().toISOString()
      }])

      setShowScheduleModal(false)
      setSelectedContent([])
      showSuccess('Content scheduled successfully!')

    } catch (error) {
      console.error('Error scheduling content:', error)
      showError(error.message || 'Failed to schedule content')
    } finally {
      setIsScheduling(false)
    }
  }

  // Lead action handlers
  const handleEditLead = () => {
    if (!selectedLeadId) {
      showError('Please select a lead to edit')
      return
    }

    const leadToEdit = messages.find(msg => msg.intent === 'lead_created')?.lead_items?.find(lead => lead.id === selectedLeadId)
    if (leadToEdit) {
      // Trigger edit lead flow
      sendMessage(`Edit lead: ${leadToEdit.name}`)
    }
  }

  const handleDeleteLead = () => {
    if (!selectedLeadId) {
      showError('Please select a lead to delete')
      return
    }

    if (window.confirm('Are you sure you want to delete this lead?')) {
      // Trigger delete lead flow
      sendMessage(`Delete lead: ${selectedLeadId}`)
    }
  }

  const handleSaveLead = () => {
    if (!selectedLeadId) {
      showError('Please select a lead to save')
      return
    }

    // Trigger save lead flow (mark as saved/completed)
    sendMessage(`Save lead: ${selectedLeadId}`)
  }

  const handleEditSelectedLead = () => {
    if (selectedLeads.length !== 1) {
      showError('Please select exactly one lead to edit')
      return
    }

    const leadId = selectedLeads[0]
    // Find the lead data from current message
    const currentMessage = messages[messages.length - 1]
    const leadToEdit = currentMessage?.lead_items?.find(lead => lead.lead_id === leadId || lead.id === leadId)

    if (leadToEdit) {
      setEditLeadData(leadToEdit)
      setShowEditLeadModal(true)
    } else {
      showError('Lead data not found')
    }
  }

  const handleDeleteSelectedLeads = async () => {
    if (selectedLeads.length === 0) {
      showError('Please select at least one lead to delete')
      return
    }

    const confirmMessage = selectedLeads.length === 1
      ? 'Are you sure you want to delete this lead? This action cannot be undone.'
      : `Are you sure you want to delete ${selectedLeads.length} leads? This action cannot be undone.`

    if (!confirm(confirmMessage)) {
      return
    }

    setIsDeleting(true)

    try {
      for (const leadId of selectedLeads) {
        // Send delete message for each selected lead
        await sendMessage(`Delete lead with ID: ${leadId}`)
      }

      showSuccess(`Successfully initiated deletion of ${selectedLeads.length} lead${selectedLeads.length > 1 ? 's' : ''}`)
      setSelectedLeads([]) // Clear selection after deletion
    } catch (error) {
      console.error('Error deleting leads:', error)
      showError('Failed to delete some leads. Please try again.')
    } finally {
      setIsDeleting(false)
    }
  }

  const handleConnectionRequired = async (platform) => {
    console.log('handleConnectionRequired called with platform:', platform)
    if (!platform) {
      console.error('No platform specified for connection')
      showError('Unable to determine which platform to connect. Please try again.')
      return
    }

    // Normalize platform name to lowercase for OAuth compatibility
    platform = platform.toLowerCase()
    if (platform === "gmail") {
      platform = "google"
    }
    console.log('Normalized platform:', platform)

    try {
      setIsConnecting(true)
      console.log('Starting connection process for platform:', platform)

      if (platform === 'google') {
        // Handle Google OAuth with popup (same as ConnectionCards)
        const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://agent-emily.onrender.com'
        const cleanUrl = API_BASE_URL.replace(/\/+$/, '') + '/connections/google/auth/initiate'
        console.log('Google auth URL:', cleanUrl)

        const response = await fetch(cleanUrl)
        console.log('Google auth response status:', response.status)

        if (!response.ok) {
          const errorText = await response.text()
          console.error('Google auth error:', response.status, errorText)
          throw new Error(`Failed to get Google auth URL: ${response.status}`)
        }

        const data = await response.json()
        console.log('Google auth data received:', data)

        if (data.auth_url) {
          console.log('Opening Google OAuth popup with URL:', data.auth_url)
          const popup = window.open(
            data.auth_url,
            'google-oauth',
            'width=500,height=600,scrollbars=yes,resizable=yes,status=yes,location=yes,toolbar=no,menubar=no'
          )

          console.log('Popup opened:', popup)

          // Check if popup was blocked
          if (!popup || popup.closed || typeof popup.closed === 'undefined') {
            console.error('Popup was blocked or failed to open')
            showError('Popup blocked! Please allow popups for this site and try again.')
            setIsConnecting(false)
            return
          }

          // Listen for popup messages (same as ConnectionCards)
          const messageHandler = async (event) => {
            const allowedOrigins = [
              window.location.origin,
              'https://emily.atsnai.com',
              'https://agent-emily.onrender.com'
            ]

            if (!allowedOrigins.includes(event.origin)) {
              console.log('Ignoring message from origin:', event.origin)
              return
            }

            console.log('Received message:', event.data, 'from origin:', event.origin)

            if (event.data.type === 'GOOGLE_OAUTH_SUCCESS' || event.data.type === 'OAUTH_SUCCESS') {
              console.log('OAuth successful:', event.data)
              popup.close()
              window.removeEventListener('message', messageHandler)

              // After successful connection, retry the publish operation
              showSuccess('Account connected successfully! Retrying publish operation...')
              setTimeout(() => {
                const lastMessage = messages[messages.length - 1]
                if (lastMessage && lastMessage.sender === 'user') {
                  sendMessage(lastMessage.text)
                }
              }, 2000)
            } else if (event.data.type === 'GOOGLE_OAUTH_ERROR' || event.data.type === 'OAUTH_ERROR') {
              console.error('OAuth error:', event.data.error)
              popup.close()
              window.removeEventListener('message', messageHandler)
              showError(`Connection failed: ${event.data.error}`)
            }
          }

          window.addEventListener('message', messageHandler)

          // Check if popup was closed manually
          const checkClosed = setInterval(() => {
            if (popup.closed) {
              clearInterval(checkClosed)
              window.removeEventListener('message', messageHandler)
              console.log('Popup closed, retrying publish operation...')
              setTimeout(() => {
                const lastMessage = messages[messages.length - 1]
                if (lastMessage && lastMessage.sender === 'user') {
                  sendMessage(lastMessage.text)
                }
              }, 1000)
            }
          }, 1000)
        } else {
          throw new Error('Failed to get Google auth URL from response')
        }
      } else {
        // Handle other platforms using the proper connections API with popup
        console.log(`Initiating ${platform} connection via API`)
        const result = await connectionsAPI.initiateConnection(platform)

        if (result.error) {
          throw new Error(result.error)
        }

        if (result.data) {
          console.log(`${platform} auth URL received:`, result.data)

          // Open OAuth in popup for ALL platforms (not just Google)
          const popup = window.open(
            result.data,
            `${platform}-oauth`,
            'width=500,height=600,scrollbars=yes,resizable=yes,status=yes,location=yes,toolbar=no,menubar=no'
          )

          console.log('Popup opened:', popup)

          // Check if popup was blocked
          if (!popup || popup.closed || typeof popup.closed === 'undefined') {
            console.error('Popup was blocked or failed to open')
            showError('Popup blocked! Please allow popups for this site and try again.')
            setIsConnecting(false)
            return
          }

          // Listen for OAuth messages (both Google and generic)
          const messageHandler = async (event) => {
            const allowedOrigins = [
              window.location.origin,
              'https://emily.atsnai.com',
              'https://agent-emily.onrender.com'
            ]

            if (!allowedOrigins.includes(event.origin)) {
              console.log('Ignoring message from origin:', event.origin)
              return
            }

            console.log('Received message:', event.data, 'from origin:', event.origin)

            if (event.data.type === 'GOOGLE_OAUTH_SUCCESS' || event.data.type === 'OAUTH_SUCCESS') {
              console.log('OAuth successful:', event.data)
              popup.close()
              window.removeEventListener('message', messageHandler)

              // After successful connection, retry the publish operation
              showSuccess('Account connected successfully! Retrying publish operation...')
              setTimeout(() => {
                const lastMessage = messages[messages.length - 1]
                if (lastMessage && lastMessage.sender === 'user') {
                  sendMessage(lastMessage.text)
                }
              }, 2000)
            } else if (event.data.type === 'GOOGLE_OAUTH_ERROR' || event.data.type === 'OAUTH_ERROR') {
              console.error('OAuth error:', event.data.error)
              popup.close()
              window.removeEventListener('message', messageHandler)
              showError(`Connection failed: ${event.data.error}`)
            }
          }

          window.addEventListener('message', messageHandler)

          // Check if popup was closed manually
          const checkClosed = setInterval(() => {
            if (popup.closed) {
              clearInterval(checkClosed)
              window.removeEventListener('message', messageHandler)
              console.log('Popup closed, retrying publish operation...')
              setTimeout(() => {
                const lastMessage = messages[messages.length - 1]
                if (lastMessage && lastMessage.sender === 'user') {
                  sendMessage(lastMessage.text)
                }
              }, 1000)
            }
          }, 1000)
        } else {
          throw new Error('Failed to get auth URL')
        }
      }
    } catch (error) {
      console.error(`Error connecting to ${platform}:`, error)
      showError(`Failed to connect to ${platform}. Please try again.`)
    } finally {
      setIsConnecting(false)
    }
  }

  const handleSaveSelected = async () => {
    if (selectedContent.length === 0) {
      showError('Please select at least one item to save')
      return
    }

    try {
      // Content is already saved as draft when created, this just confirms
      console.log('Save draft content:', selectedContent)
      showSuccess('Content saved as draft successfully!')

      // Clear selection after action
      setSelectedContent([])

    } catch (error) {
      console.error('Error saving content:', error)
      showError(error.message || 'Failed to save content')
    }
  }

  // Handle option selection from clarification buttons
  const handleOptionSelect = async (value) => {
    if (!value || isLoading) return

    // Special handling for custom date picker
    if (value === 'show_date_picker') {
      // Detect if this is for lead follow-up (single date) or content viewing (range)
      const lastMessage = messages[messages.length - 1]
      const isLeadFollowUp = lastMessage?.clarification_options?.some(opt =>
        opt.value === 'tomorrow' || opt.value === 'next week' || opt.value === 'next month'
      )

      if (isLeadFollowUp) {
        setShowSingleDatePicker(true)
      } else {
        setShowDatePicker(true)
      }
      return
    }

    // Special handling for media upload
    const lastMessage = messages[messages.length - 1]
    if (lastMessage?.clarification_options &&
        lastMessage.clarification_options.some(opt => opt.value === 'Upload') &&
        value === 'Upload') {
      setShowMediaUploadModal(true)
      return
    }

    const optionMessage = value.trim()
    const messageId = Date.now()

    // Add user message with selected option
    setMessages(prev => [...prev, {
      id: messageId,
      sender: 'user',
      text: optionMessage,
      timestamp: new Date().toISOString()
    }])

    // Update conversation history
    const updatedHistory = [...conversationHistory, optionMessage]
    setConversationHistory(updatedHistory)
    setInputMessage('')
    setIsLoading(true)

    try {
      // Get token from session
      const token = await getAuthToken()

      if (!token) {
        throw new Error('No authentication session found. Please log in again.')
      }

      const response = await fetch(`${API_BASE_URL}/atsn/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: optionMessage,
          conversation_history: updatedHistory
        })
      })

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication failed. Please log in again.')
        }
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      // Add bot response
      setMessages(prev => [...prev, {
        id: Date.now(),
        sender: 'bot',
        text: data.response,
        timestamp: new Date().toISOString(),
        intent: data.intent,
        step: data.current_step,
        payload: data.payload,
        waiting_for_user: data.waiting_for_user,
        payload_complete: data.payload_complete,
        error: data.error,
        content_items: data.content_items || null,
        lead_id: data.lead_id || null,
        lead_items: data.lead_items || null,
        agent_name: data.agent_name || 'emily',
        clarification_options: data.clarification_options || [],
        needs_connection: data.needs_connection || false,
        connection_platform: data.connection_platform || null
      }])

      // Update agent status
      setAgentStatus({
        intent: data.intent,
        step: data.current_step,
        waiting: data.waiting_for_user,
        complete: data.payload_complete
      })

    } catch (error) {
      console.error('Error sending option:', error)
      const errorMessage = error.message || 'Failed to send option. Please try again.'
      showError(errorMessage)

      setMessages(prev => [...prev, {
        id: Date.now(),
        sender: 'bot',
        text: `❌ ${errorMessage}\n\n${error.message?.includes('authentication') ? 'Please refresh the page and log in again.' : 'Please try again or reset the conversation.'}`,
        timestamp: new Date().toISOString(),
        error: true
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleDatePickerConfirm = async () => {
    if (!selectedDateRange.start) {
      showError('Please select a start date')
      return
    }

    let dateMessage = selectedDateRange.start
    if (selectedDateRange.end && selectedDateRange.end !== selectedDateRange.start) {
      dateMessage = `${selectedDateRange.start} to ${selectedDateRange.end}`
    }

    const messageId = Date.now()

    // Add user message with selected date(s)
    setMessages(prev => [...prev, {
      id: messageId,
      sender: 'user',
      text: dateMessage,
      timestamp: new Date().toISOString()
    }])

    // Update conversation history
    const updatedHistory = [...conversationHistory, dateMessage]
    setConversationHistory(updatedHistory)
    setShowDatePicker(false)
    setSelectedDateRange({ start: '', end: '' })
    setIsLoading(true)

    try {
      // Get token from session
      const token = await getAuthToken()

      if (!token) {
        throw new Error('No authentication session found. Please log in again.')
      }

      const response = await fetch(`${API_BASE_URL}/atsn/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: dateMessage,
          conversation_history: updatedHistory
        })
      })

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Authentication failed. Please log in again.')
        }
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      // Add bot response
      setMessages(prev => [...prev, {
        id: Date.now(),
        sender: 'bot',
        text: data.response,
        timestamp: new Date().toISOString(),
        intent: data.intent,
        step: data.current_step,
        payload: data.payload,
        waiting_for_user: data.waiting_for_user,
        payload_complete: data.payload_complete,
        error: data.error,
        content_items: data.content_items || null,
        lead_id: data.lead_id || null,
        lead_items: data.lead_items || null,
        agent_name: data.agent_name || 'emily',
        clarification_options: data.clarification_options || [],
        needs_connection: data.needs_connection || false,
        connection_platform: data.connection_platform || null
      }])

      // Update agent status
      setAgentStatus({
        intent: data.intent,
        step: data.current_step,
        waiting: data.waiting_for_user,
        complete: data.payload_complete
      })

    } catch (error) {
      console.error('Error sending date selection:', error)
      const errorMessage = error.message || 'Failed to send date selection. Please try again.'
      showError(errorMessage)

      setMessages(prev => [...prev, {
        id: Date.now(),
        sender: 'bot',
        text: `❌ ${errorMessage}\n\n${error.message?.includes('authentication') ? 'Please refresh the page and log in again.' : 'Please try again or reset the conversation.'}`,
        timestamp: new Date().toISOString(),
        error: true
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleDatePickerCancel = () => {
    setShowDatePicker(false)
    setSelectedDateRange({ start: '', end: '' })
  }

  const handleSingleDatePickerConfirm = async () => {
    if (!selectedSingleDate) {
      showError('Please select a follow-up date')
      return
    }

    const dateMessage = selectedSingleDate
    const messageId = Date.now()

    // Add user message with selected date
    setMessages(prev => [...prev, {
      id: messageId,
      sender: 'user',
      text: dateMessage,
      timestamp: new Date().toISOString()
    }])

    // Update conversation history
    const updatedHistory = [...conversationHistory, dateMessage]
    setConversationHistory(updatedHistory)
    setShowSingleDatePicker(false)
    setSelectedSingleDate('')
    setIsLoading(true)

    try {
      // Get token from session
      const token = await getAuthToken()

      if (!token) {
        throw new Error('No authentication session found. Please log in again.')
      }

      const response = await fetch(`${API_BASE_URL}/atsn/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          message: dateMessage,
          conversation_history: updatedHistory
        })
      })

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Session expired. Please log in again.')
        }
        throw new Error('Failed to send message')
      }

      const data = await response.json()

      // Add bot response
      setMessages(prev => [...prev, {
        id: Date.now(),
        sender: 'bot',
        text: data.response,
        timestamp: new Date().toISOString(),
        intent: data.intent,
        step: data.current_step,
        payload: data.payload,
        waiting_for_user: data.waiting_for_user,
        payload_complete: data.payload_complete,
        error: data.error,
        content_items: data.content_items || null,
        lead_id: data.lead_id || null,
        lead_items: data.lead_items || null,
        agent_name: data.agent_name || 'emily',
        clarification_options: data.clarification_options || [],
        needs_connection: data.needs_connection || false,
        connection_platform: data.connection_platform || null
      }])

      // Update agent status
      setAgentStatus({
        intent: data.intent,
        step: data.current_step,
        waiting: data.waiting_for_user,
        complete: data.payload_complete
      })

    } catch (error) {
      console.error('Error sending follow-up date:', error)
      const errorMessage = error.message || 'Failed to send follow-up date. Please try again.'
      showError(errorMessage)

      setMessages(prev => [...prev, {
        id: Date.now(),
        sender: 'bot',
        text: `❌ ${errorMessage}\n\n${error.message?.includes('authentication') ? 'Please refresh the page and log in again.' : 'Please try again or reset the conversation.'}`,
        timestamp: new Date().toISOString(),
        error: true
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleSingleDatePickerCancel = () => {
    setShowSingleDatePicker(false)
    setSelectedSingleDate('')
  }

  const handleFileSelection = (files) => {
    // Store selected files for confirmation before upload
    setSelectedFilesForUpload(files)
  }

  const handleAgentHover = (agentName, event) => {
    const rect = event.currentTarget.getBoundingClientRect()
    setTooltipAgent(agentName)
    setTooltipPosition({
      x: rect.left + rect.width / 2,
      y: rect.top
    })
  }

  const handleAgentLeave = () => {
    setTooltipAgent(null)
  }

  const handleCancelUpload = () => {
    setSelectedFilesForUpload([])
  }

  const handleConfirmUpload = async () => {
    if (selectedFilesForUpload.length === 0) return

    setIsUploadingMedia(true)

    // Capture media type before clearing
    const mediaType = selectedFilesForUpload[0].type.startsWith('image/') ? 'image' : 'video'

    try {
      const token = await getAuthToken()
      if (!token) {
        showError('Authentication required')
        return
      }

      const formData = new FormData()
      selectedFilesForUpload.forEach((file, index) => {
        formData.append('files', file)
      })

      const response = await fetch(`${API_BASE_URL}/media/upload`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      })

      if (response.ok) {
        const data = await response.json()
        setUploadedMediaUrls(data.urls || [])
        setShowMediaUploadModal(false)

        // Create a task for media upload
        const taskMessage = `I uploaded a ${mediaType} for my content. Please help me create engaging content using this media.`

        // Clear selected files after capturing media type
        setSelectedFilesForUpload([])

        // Add user message about media upload
        setMessages(prev => [...prev, {
          id: Date.now(),
          sender: 'user',
          text: taskMessage,
          timestamp: new Date().toISOString(),
          media_urls: data.urls || []
        }])

        // Send to chatbot
        try {
          const chatResponse = await fetch(`${API_BASE_URL}/atsn/chat`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
              message: taskMessage,
              media_urls: data.urls || [],
              conversation_history: [...conversationHistory, taskMessage]
            })
          })

          if (chatResponse.ok) {
            const chatData = await chatResponse.json()
            // Handle the response similar to regular messages
            setMessages(prev => [...prev, {
              id: Date.now() + 1,
              sender: 'bot',
              text: chatData.response || 'Content creation task started!',
              timestamp: new Date().toISOString(),
              intent: chatData.intent,
              agent_name: chatData.agent_name
            }])
          }
        } catch (chatError) {
          console.error('Error sending media upload task:', chatError)
        }

        showSuccess('Media uploaded and task created successfully!')
      } else {
        throw new Error('Upload failed')
      }
    } catch (error) {
      console.error('Upload error:', error)
      showError('Failed to upload media')
    } finally {
      setIsUploadingMedia(false)
    }
  }

  // Publish functions copied from ContentDashboard
  const getBestImageUrl = (content) => {
    console.log('🔍 getBestImageUrl - Content object:', {
      hasImages: !!content.images,
      imagesType: typeof content.images,
      imagesIsArray: Array.isArray(content.images),
      imagesLength: content.images?.length || 0,
      imagesValue: content.images,
      firstImage: content.images?.[0],
      media_url: content.media_url,
      primary_image_url: content.primary_image_url,
      rawDataImages: content.raw_data?.images,
      content_id: content.content_id,
      platform: content.platform
    })

    if (content.images && Array.isArray(content.images) && content.images.length > 0) {
      console.log('✅ Using content.images[0]:', content.images[0])
      return content.images[0]
    }
    if (content.media_url) {
      console.log('✅ Using content.media_url:', content.media_url)
      return content.media_url
    }
    if (content.primary_image_url) {
      console.log('✅ Using content.primary_image_url:', content.primary_image_url)
      return content.primary_image_url
    }
    if (content.raw_data?.images && Array.isArray(content.raw_data.images) && content.raw_data.images.length > 0) {
      console.log('✅ Using content.raw_data.images[0]:', content.raw_data.images[0])
      return content.raw_data.images[0]
    }
    console.log('❌ No image URL found in any location')
    return ''
  }

  const postToFacebook = async (content) => {
    try {
      const authToken = await getAuthToken()

      // Check if this is a carousel post
      const isCarousel = content.post_type === 'carousel' ||
                         (content.metadata && content.metadata.carousel_images && content.metadata.carousel_images.length > 0)
      const carouselImages = isCarousel ? (content.metadata?.carousel_images || []) : []

      // Get the image URL if available (from content.images array)
      let imageUrl = getBestImageUrl(content)
      if (imageUrl && !isCarousel) {
        console.log('📸 Including image in Facebook post:', imageUrl)
      }

      if (isCarousel) {
        console.log(`🎠 Posting carousel with ${carouselImages.length} images to Facebook`)
      }

      const postBody = {
        message: content.content,
        title: content.title,
        hashtags: content.hashtags || [],
        content_id: content.content_id
      }

      if (isCarousel && carouselImages.length > 0) {
        postBody.post_type = 'carousel'
        postBody.carousel_images = carouselImages
      } else {
        postBody.image_url = imageUrl
      }

      const response = await fetch(`${API_BASE_URL}/connections/facebook/post`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify(postBody)
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`HTTP error! status: ${response.status}: ${errorText}`)
      }

      const result = await response.json()
      console.log('Facebook post result:', result)

      // Show beautiful notification with post URL if available
      showPostNotification('Facebook', result.post_url || result.url)

      // Update the content status in messages
      const publishedAt = new Date().toISOString()
      setMessages(prev => prev.map(message => {
        if (message.content_items) {
          return {
            ...message,
            content_items: message.content_items.map(item =>
              item.content_id === content.id
                ? { ...item, status: 'published', published_at: publishedAt, facebook_post_id: result.post_id }
                : item
            )
          }
        }
        return message
      }))

    } catch (error) {
      console.error('Error posting to Facebook:', error)
      throw error
    }
  }

  const postToInstagram = async (content) => {
    let oauthError = null

    try {
      const authToken = await getAuthToken()

      // Check if this is a carousel post
      const isCarousel = content.post_type === 'carousel' ||
                         (content.metadata && content.metadata.carousel_images && content.metadata.carousel_images.length > 0)
      const carouselImages = isCarousel ? (content.metadata?.carousel_images || []) : []

      let imageUrl = getBestImageUrl(content)
      if (imageUrl && !isCarousel) {
        console.log('📸 Including image in Instagram post:', imageUrl)
      }

      if (isCarousel) {
        console.log(`🎠 Posting carousel with ${carouselImages.length} images to Instagram`)
      }

      const postBody = {
        message: content.content,
        title: content.title,
        hashtags: content.hashtags || [],
        content_id: content.content_id
      }

      if (isCarousel && carouselImages.length > 0) {
        postBody.post_type = 'carousel'
        postBody.carousel_images = carouselImages
      } else {
        postBody.image_url = imageUrl
      }

      const response = await fetch(`${API_BASE_URL}/connections/instagram/post`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify(postBody)
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`HTTP error! status: ${response.status}: ${errorText}`)
      }

      const result = await response.json()
      console.log('Instagram post result:', result)

      // Show beautiful notification with post URL if available
      showPostNotification('Instagram', result.post_url || result.url)

      // Update the content status in messages
      const publishedAt = new Date().toISOString()
      setMessages(prev => prev.map(message => {
        if (message.content_items) {
          return {
            ...message,
            content_items: message.content_items.map(item =>
              item.content_id === content.id
                ? { ...item, status: 'published', published_at: publishedAt, instagram_post_id: result.post_id }
                : item
            )
          }
        }
        return message
      }))

    } catch (error) {
      console.error('Error posting to Instagram:', error)
      throw error
    }
  }

  const postToLinkedIn = async (content) => {
    try {
      const authToken = await getAuthToken()

      // Get the image URL if available (from content.images array)
      let imageUrl = getBestImageUrl(content)
      if (imageUrl) {
        console.log('📸 Including image in LinkedIn post:', imageUrl)
      }

      const postBody = {
        message: content.content,
        title: content.title,
        hashtags: content.hashtags || [],
        content_id: content.content_id
      }

      if (imageUrl) {
        postBody.image_url = imageUrl
      }

      const response = await fetch(`${API_BASE_URL}/connections/linkedin/post`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify(postBody)
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`HTTP error! status: ${response.status}: ${errorText}`)
      }

      const result = await response.json()
      console.log('LinkedIn post result:', result)

      // Show beautiful notification with post URL if available
      showPostNotification('LinkedIn', result.post_url || result.url)

      // Update the content status in messages
      const publishedAt = new Date().toISOString()
      setMessages(prev => prev.map(message => {
        if (message.content_items) {
          return {
            ...message,
            content_items: message.content_items.map(item =>
              item.content_id === content.id
                ? { ...item, status: 'published', published_at: publishedAt, linkedin_post_id: result.post_id || result.id }
                : item
            )
          }
        }
        return message
      }))

    } catch (error) {
      console.error('Error posting to LinkedIn:', error)
      throw error
    }
  }

  const postToYouTube = async (content) => {
    try {
      const authToken = await getAuthToken()

      // Get the image URL if available (from content.images array)
      let imageUrl = getBestImageUrl(content)
      if (imageUrl) {
        console.log('📸 Including image in YouTube post:', imageUrl)
      }

      const postBody = {
        message: content.content,
        title: content.title,
        hashtags: content.hashtags || [],
        content_id: content.content_id
      }

      if (imageUrl) {
        postBody.image_url = imageUrl
      }

      const response = await fetch(`${API_BASE_URL}/connections/youtube/post`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify(postBody)
      })

      if (!response.ok) {
        const errorText = await response.text()
        throw new Error(`HTTP error! status: ${response.status}: ${errorText}`)
      }

      const result = await response.json()
      console.log('YouTube post result:', result)

      // Show beautiful notification with post URL if available
      showPostNotification('YouTube', result.post_url || result.url)

      // Update the content status in messages
      const publishedAt = new Date().toISOString()
      setMessages(prev => prev.map(message => {
        if (message.content_items) {
          return {
            ...message,
            content_items: message.content_items.map(item =>
              item.content_id === content.id
                ? { ...item, status: 'published', published_at: publishedAt, youtube_post_id: result.post_id || result.id }
                : item
            )
          }
        }
        return message
      }))

    } catch (error) {
      console.error('Error posting to YouTube:', error)
      throw error
    }
  }

  const showPostNotification = (platform, url) => {
    // Simple notification - could be enhanced
    showSuccess(`Successfully posted to ${platform}!${url ? ` View post: ${url}` : ''}`)
  }

  // Render agent icon based on agent name
  const renderAgentIcon = (agentName) => {
    switch (agentName?.toLowerCase()) {
      case 'leo':
        return <img src="/leo_logo.jpg" alt="Leo" className="w-16 h-16 rounded-full object-cover" />
      case 'chase':
        return <img src="/chase_logo.png" alt="Chase" className="w-16 h-16 rounded-full object-cover" />
      case 'orio':
        return <span className="text-xl font-bold text-white">O</span>
      case 'atsn':
        // Combined logo for ATSN welcome message
        return (
          <div className="w-16 h-16 rounded-full bg-gradient-to-br from-purple-500 via-blue-500 to-green-500 flex items-center justify-center relative overflow-hidden">
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="w-12 h-12 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm">
                <div className="grid grid-cols-2 gap-1">
                  <img src="/emily_icon.png" alt="E" className="w-4 h-4 rounded-full object-cover" />
                  <img src="/leo_logo.jpg" alt="L" className="w-4 h-4 rounded-full object-cover" />
                  <img src="/chase_logo.png" alt="C" className="w-4 h-4 rounded-full object-cover" />
                  <div className="w-4 h-4 rounded-full bg-white/30 flex items-center justify-center">
                    <span className="text-xs font-bold text-white">A</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )
      case 'emily':
      default:
        return <img src="/emily_icon.png" alt="Emily" className="w-16 h-16 rounded-full object-cover" />
    }
  }


  // Get thinking message based on current phase
  const getThinkingMessage = () => {
    if (isFirstMessage) {
      switch (thinkingPhase) {
        case 0:
          return "Assigning a suitable agent to work on your request...";
        case 1:
          return "Contacting the agent...";
        case 2:
          return "Invoking the agent...";
        default:
          return "Working on your request...";
      }
    } else {
      switch (thinkingPhase) {
        case 0:
          return "Working on your request...";
        case 1:
          return "Processing your request...";
        case 2:
          return "Finalizing your request...";
        default:
          return "Almost done...";
      }
    }
  }

  // Get agent based on message content
  const getAgentFromMessage = (message) => {
    const msg = message.toLowerCase();
    if (msg.includes('lead')) return 'chase';
    if (msg.includes('analytics') || msg.includes('insight')) return 'orio';

    // Check for view/search operations on content first
    if ((msg.includes('view') || msg.includes('show') || msg.includes('find') || msg.includes('search')) && msg.includes('content')) {
      return 'emily';
    }

    // Then check for other content operations
    if (msg.includes('content') || msg.includes('post') || msg.includes('schedule') || msg.includes('publish')) return 'leo';

    return 'emily';
  }

  // Format agent name for display
  const formatAgentName = (agentName) => {
    if (!agentName) return 'Emily';
    if (agentName.toLowerCase() === 'atsn') return 'ATSN Team';
    return agentName.charAt(0).toUpperCase() + agentName.slice(1);
  }


  return (
    <div className="flex flex-col h-full rounded-lg">
      {/* Custom scrollbar styles */}
      <style dangerouslySetInnerHTML={{
        __html: `
          .chat-scrollbar::-webkit-scrollbar {
            height: 6px;
          }
          .chat-scrollbar::-webkit-scrollbar-track {
            background: #f3f4f6;
            border-radius: 3px;
          }
          .chat-scrollbar::-webkit-scrollbar-thumb {
            background: #d1d5db;
            border-radius: 3px;
          }
          .chat-scrollbar::-webkit-scrollbar-thumb:hover {
            background: #6B7280;
          }

          /* Hide scrollbar for chat messages */
          .scrollbar-hide {
            -ms-overflow-style: none;  /* IE and Edge */
            scrollbar-width: none;  /* Firefox */
          }
          .scrollbar-hide::-webkit-scrollbar {
            display: none;  /* Chrome, Safari and Opera */
          }
        `
      }} />

      {/* Schedule Modal */}
      {showScheduleModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-xl font-semibold mb-4">Schedule Content</h3>
            <div className="space-y-4">
              <div>
                <label className="block text-base font-medium text-gray-700 mb-1">Date</label>
                <input
                  type="date"
                  value={scheduleData.date}
                  onChange={(e) => setScheduleData(prev => ({ ...prev, date: e.target.value }))}
                  min={new Date().toISOString().split('T')[0]}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
              <div>
                <label className="block text-base font-medium text-gray-700 mb-1">Time</label>
                <input
                  type="time"
                  value={scheduleData.time}
                  onChange={(e) => setScheduleData(prev => ({ ...prev, time: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowScheduleModal(false)}
                className="flex-1 px-4 py-2 text-base bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleScheduleConfirm}
                disabled={isScheduling || !scheduleData.date || !scheduleData.time}
                className="flex-1 px-4 py-2 text-base bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition-colors"
              >
                {isScheduling ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Scheduling...
                  </>
                ) : (
                  'Schedule'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      <div
        className="flex-1 overflow-y-auto scrollbar-hide p-4 space-y-6"
        onClick={handleChatAreaClick}
      >
        {messages.map((message, index) => (
          <div
            key={message.id}
            className={`group flex gap-3 ${message.sender === 'user' ? 'flex-row-reverse' : 'flex-row'}`}
          >
            {/* Avatar */}
            <div
              className={`${
                message.agent_name?.toLowerCase() === 'emily' || message.agent_name?.toLowerCase() === 'leo' || message.agent_name?.toLowerCase() === 'chase' || message.agent_name?.toLowerCase() === 'atsn'
                  ? 'w-16 h-16'
                  : 'w-8 h-8'
              } rounded-full flex items-center justify-center flex-shrink-0 ${
                message.sender === 'bot' ? 'hover:scale-110 transition-transform duration-200 cursor-pointer border-2 border-gray-300' : ''
              } ${
              message.sender === 'user'
                ? 'bg-gradient-to-br from-pink-500 to-rose-500'
                : message.agent_name?.toLowerCase() === 'leo'
                  ? '' // No background for Leo
                : message.agent_name?.toLowerCase() === 'chase'
                  ? '' // No background for Chase
                  : message.agent_name?.toLowerCase() === 'emily'
                  ? '' // No background for Emily
                  : message.agent_name?.toLowerCase() === 'atsn'
                  ? '' // No background for ATSN combined logo
                : 'bg-gradient-to-br from-purple-500 to-pink-500'
              }`}
              onMouseEnter={message.sender === 'bot' ? (e) => handleAgentHover(message.agent_name, e) : undefined}
              onMouseLeave={message.sender === 'bot' ? handleAgentLeave : undefined}
            >
              {message.sender === 'user' ? (
                <User className="w-5 h-5 text-white" />
              ) : (
                renderAgentIcon(message.agent_name)
              )}
            </div>

            {/* Message bubble */}
            <div className={`flex-1 max-w-[80%] ${message.sender === 'user' ? 'text-right' : 'text-left'}`}>
              <div
                className={`inline-block p-4 rounded-2xl backdrop-blur-md border shadow-lg ${
                  message.sender === 'user'
                    ? 'bg-pink-500/90 border-pink-400 text-white rounded-tr-none'
                    : message.error
                    ? isDarkMode
                      ? 'bg-red-900/50 border-red-700 text-red-200 rounded-tl-none'
                      : 'bg-red-50 border-red-200 text-red-900 rounded-tl-none'
                    : isDarkMode
                    ? 'bg-gray-800/80 border-gray-600 text-white rounded-tl-none'
                    : 'bg-white/80 border-gray-200 text-gray-900 rounded-tl-none'
                }`}
              >
                {message.sender === 'bot' ? (
                  <div className="space-y-4">
                    {/* Agent name above message */}
                    <div className="flex items-center justify-between mb-2">
                      <span className={`text-base font-bold bg-clip-text text-transparent ${
                        message.agent_name?.toLowerCase() === 'leo'
                          ? isDarkMode
                            ? 'bg-gradient-to-r from-blue-300 to-blue-500'
                            : 'bg-gradient-to-r from-blue-500 to-blue-700'
                          : message.agent_name?.toLowerCase() === 'chase'
                          ? isDarkMode
                            ? 'bg-gradient-to-r from-green-400 to-yellow-400'
                            : 'bg-gradient-to-r from-green-800 to-amber-800'
                          : message.agent_name?.toLowerCase() === 'atsn'
                          ? isDarkMode
                            ? 'bg-gradient-to-r from-purple-300 via-blue-300 to-green-300'
                            : 'bg-gradient-to-r from-purple-500 via-blue-500 to-green-500'
                          : isDarkMode
                          ? 'bg-gradient-to-r from-purple-400 to-pink-400'
                          : 'bg-gradient-to-r from-purple-600 to-pink-500'
                      }`}>
                        {formatAgentName(message.agent_name)}
                      </span>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleCopyMessage(message)}
                          className={`p-1 rounded transition-colors ${
                            isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                          }`}
                          title="Copy message"
                        >
                          <Copy className={`w-3 h-3 ${
                            isDarkMode ? 'text-gray-400' : 'text-gray-600'
                          }`} />
                        </button>
                        <button
                          onClick={() => handleLikeMessage(message)}
                          className={`p-1 rounded transition-colors ${
                            isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                          }`}
                          title={likedMessages.has(message.id) ? "Unlike message" : "Like message"}
                        >
                          <Heart className={`w-3 h-3 ${
                            likedMessages.has(message.id)
                              ? 'text-red-500 fill-current'
                              : isDarkMode
                              ? 'text-gray-400'
                              : 'text-gray-600'
                          }`} />
                        </button>
                        <button
                          onClick={() => handleDeleteMessage(message)}
                          className={`p-1 rounded transition-colors ${
                            isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-gray-100'
                          }`}
                          title="Delete message"
                        >
                          <Trash2 className={`w-3 h-3 ${
                            isDarkMode ? 'text-gray-400' : 'text-gray-600'
                          }`} />
                        </button>
                      </div>
                    </div>

                    <div className="relative max-w-none leading-tight">
                      {/* Check if message contains markdown syntax */}
                      {message.text.includes('#') || message.text.includes('*') || message.text.includes('`') || message.text.includes('[') ? (
                        <div className={`leading-tight pr-16 ${
                          isDarkMode ? 'prose-invert prose prose-gray' : 'prose'
                        }`}>
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {message.text}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <div className={`whitespace-pre-line leading-tight pr-16 ${
                          isDarkMode ? 'text-white' : ''
                        }`}>
                          {message.text}
                        </div>
                      )}
                      <div className={`absolute bottom-0 right-0 text-xs ${
                        message.sender === 'user'
                          ? 'text-white'
                          : isDarkMode
                          ? 'text-gray-500'
                          : 'text-gray-400'
                      }`}>
                        {new Date(message.timestamp).toLocaleTimeString()}
                      </div>
                      </div>

                    {/* Render clarification options only for active clarifications */}
                    {message.clarification_options && message.clarification_options.length > 0 && message.waiting_for_user && (
                      <div className="mt-4 flex flex-wrap gap-3">
                        {message.clarification_options.map((option, index) => (
                          <button
                            key={index}
                            onClick={() => handleOptionSelect(option.value)}
                            className={`px-4 py-3 backdrop-blur-sm rounded-xl border shadow-lg hover:shadow-xl transition-all duration-200 text-sm font-normal transform hover:scale-105 ${
                              isDarkMode
                                ? 'bg-gray-700/80 text-gray-200 hover:text-white border-gray-600'
                                : 'bg-white/80 text-gray-800 hover:text-gray-900 border-gray-300'
                            }`}
                          >
                            <div className="font-normal text-center">{option.label}</div>
                            {option.description && (
                              <div className="text-xs opacity-75 mt-1 text-center leading-tight">{option.description}</div>
                            )}
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Render content cards if available */}
                    {message.content_items && message.content_items.length > 0 && (
                      <div className="mt-4">
                        {/* Horizontal scrollable posts window */}
                        <div className="w-full max-w-4xl">
                          <div className="relative">
                            {/* Scrollable container with window effect - shows ~5 posts width */}
                            <div className="overflow-x-auto overflow-y-hidden max-w-full" style={{
                              scrollbarWidth: 'thin',
                              scrollbarColor: '#9CA3AF #E5E7EB'
                            }}>
                              <div className="chat-scrollbar flex gap-4 pb-2 px-1" style={{
                                width: 'max-content',
                                minWidth: message.content_items.length > 5 ? `${message.content_items.length * 336}px` : 'auto' // 320px + 16px gap (w-80 = 320px)
                              }}>
                                {message.content_items.map((contentItem, index) => (
                                   <div key={`${message.id}-${index}`} className="relative flex-shrink-0 w-96">
                                    {/* Selection checkbox for view, delete, and publish operations */}
                                    {(message.intent === 'view_content' || message.intent === 'delete_content' || message.intent === 'created_content' || message.intent === 'publish_content') && (
                                      <div className="absolute top-2 right-2 z-10">
                                        <button
                                          onClick={() => handleContentSelect(contentItem.content_id, message.intent)}
                                          className={`w-6 h-6 rounded border-2 flex items-center justify-center transition-colors ${
                                            selectedContent.includes(contentItem.content_id)
                                              ? (message.intent === 'delete_content' ? 'bg-red-600 border-red-600' : 'bg-purple-600 border-purple-600') + ' text-white'
                                              : 'bg-white border-gray-300 hover:border-purple-400'
                                          }`}
                                        >
                                          {selectedContent.includes(contentItem.content_id) ? (
                                            <CheckSquare className="w-4 h-4" />
                                          ) : (
                                            <Square className="w-4 h-4" />
                                          )}
                                        </button>
                                      </div>
                                    )}

                                    {/* Use ATSNContentCard for posts, ContentCard for others */}
                                    {contentItem.raw_data?.content_type === 'post' || contentItem.content_type?.toLowerCase().includes('post') ? (
                                      <ATSNContentCard
                                        content={{
                                          id: contentItem.content_id,
                                          title: contentItem.title_display || contentItem.title,
                                          content: contentItem.content_preview || contentItem.content_text,
                                          hashtags: contentItem.hashtags_display ?
                                            contentItem.hashtags_display.split(' ').filter(tag => tag.startsWith('#')).map(tag => tag.substring(1)) :
                                            (contentItem.hashtags ?
                                              (Array.isArray(contentItem.hashtags) ? contentItem.hashtags : []) :
                                              []),
                                          media_url: contentItem.media_url,
                                          images: contentItem.images || [],
                                          metadata: contentItem.metadata || {},
                                          post_type: contentItem.raw_data?.post_type,
                                          content_type: contentItem.content_type,
                                          selected_content_type: contentItem.raw_data?.selected_content_type,
                                          carousel_images: contentItem.raw_data?.carousel_images || contentItem.raw_data?.images,
                                          // Add additional fields for different content types
                                          email_subject: contentItem.email_subject,
                                          email_body: contentItem.email_body,
                                          short_video_script: contentItem.short_video_script,
                                          long_video_script: contentItem.long_video_script,
                                          message: contentItem.message
                                        }}
                                        platform={contentItem.platform}
                                        contentType={contentItem.content_type}
                                        intent={message.intent}
                                        onClick={() => handleContentClick(contentItem)}
                                        isDarkMode={isDarkMode}
                                      />
                                    ) : (
                                      <ContentCard
                                        content={{
                                          id: contentItem.content_id,
                                          title: contentItem.title_display || contentItem.title,
                                          content: contentItem.content_preview || contentItem.content_text,
                                          hashtags: contentItem.hashtags_display ?
                                            contentItem.hashtags_display.split(' ').filter(tag => tag.startsWith('#')).map(tag => tag.substring(1)) :
                                            (contentItem.hashtags ?
                                              (Array.isArray(contentItem.hashtags) ? contentItem.hashtags : []) :
                                              []),
                                          media_url: contentItem.media_url,
                                          images: contentItem.images || [],
                                          metadata: contentItem.metadata || {},
                                          post_type: contentItem.raw_data?.post_type,
                                          content_type: contentItem.content_type,
                                          selected_content_type: contentItem.raw_data?.selected_content_type,
                                          carousel_images: contentItem.raw_data?.carousel_images || contentItem.raw_data?.images,
                                          // Add additional fields for different content types
                                          email_subject: contentItem.email_subject,
                                          email_body: contentItem.email_body,
                                          short_video_script: contentItem.short_video_script,
                                          long_video_script: contentItem.long_video_script,
                                          message: contentItem.message
                                        }}
                                        platform={contentItem.platform}
                                        contentType={contentItem.content_type}
                                        minimal={message.intent !== 'created_content'}
                                        onCopy={() => {
                                          let textToCopy = '';

                                          // Handle different content types for copying
                                          if (contentItem.content_type?.toLowerCase() === 'email' && contentItem.email_subject && contentItem.email_body) {
                                            textToCopy = `Subject: ${contentItem.email_subject}\n\n${contentItem.email_body}`;
                                          } else if ((contentItem.content_type?.toLowerCase() === 'short video' || contentItem.content_type?.toLowerCase() === 'long video') && (contentItem.short_video_script || contentItem.long_video_script)) {
                                            textToCopy = contentItem.short_video_script || contentItem.long_video_script;
                                          } else if (contentItem.content_type?.toLowerCase() === 'message' && contentItem.message) {
                                            textToCopy = contentItem.message;
                                          } else {
                                            textToCopy = contentItem.content_preview || contentItem.content_text;
                                          }

                                          if (textToCopy) {
                                            navigator.clipboard.writeText(textToCopy);
                                            showSuccess('Content copied to clipboard!');
                                          }
                                        }}
                                        onPreview={(content) => {
                                          // Open content preview modal or navigate to detail view
                                          console.log('Preview content:', content);
                                        }}
                                        onEdit={() => {
                                          // Handle edit action - could navigate to edit page or open modal
                                          console.log('Edit content:', contentItem.content_id);
                                        }}
                                      />
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>

                            {/* Scroll indicators */}
                            {message.content_items.length > 5 && (
                              <div className="flex justify-center mt-2">
                                <div className="flex items-center gap-1 text-xs text-gray-500">
                                  <span>← Scroll to see more posts →</span>
                                </div>
                              </div>
                            )}
                          </div>


                                          {/* Action buttons for publish content */}
                          {message.intent === 'publish_content' && message.content_items && message.content_items.length > 0 && selectedContent.length > 0 && (
                            <div className={`mt-4 flex flex-wrap items-center gap-3 p-4 backdrop-blur-md border rounded-xl shadow-lg ${
                              isDarkMode
                                ? 'bg-gray-800/90 border-gray-700'
                                : 'bg-white/90 border-gray-200'
                            }`}>
                              <div className="flex gap-2">
                                <button
                                  onClick={handlePublishSelected}
                                  disabled={isPublishing}
                                  className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-lg ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                >
                                  {isPublishing ? (
                                    <>
                                      <RefreshCw className="w-4 h-4 animate-spin" />
                                      Publishing...
                                    </>
                                  ) : (
                                    <>
                                      <Share className="w-4 h-4" />
                                      Publish Selected ({selectedContent.length})
                                    </>
                                  )}
                                </button>
                              </div>
                            </div>
                          )}

                                          {/* Action buttons for created content */}
                          {message.intent === 'created_content' && message.content_items && message.content_items.length > 0 && (
                            <div className={`mt-4 flex flex-wrap items-center gap-3 p-4 backdrop-blur-md border rounded-xl shadow-lg ${
                              isDarkMode
                                ? 'bg-gray-800/90 border-gray-700'
                                : 'bg-white/90 border-gray-200'
                            }`}>
                              <div className="flex gap-2">
                                <button
                                  onClick={handleEditSelected}
                                  className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                >
                                  <Edit className="w-4 h-4" />
                                  <span>Edit</span>
                                </button>
                                <button
                                  onClick={handlePublishSelected}
                                  disabled={isPublishing}
                                  className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-lg ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                >
                                  {isPublishing ? (
                                    <>
                                      <RefreshCw className="w-4 h-4 animate-spin" />
                                      <span>Publishing...</span>
                                    </>
                                  ) : (
                                    <>
                                      <Share className="w-4 h-4" />
                                      <span>Publish</span>
                                    </>
                                  )}
                                </button>
                                <button
                                  onClick={handleScheduleSelected}
                                  disabled={isScheduling}
                                  className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-lg ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                >
                                  {isScheduling ? (
                                    <>
                                      <RefreshCw className="w-4 h-4 animate-spin" />
                                      <span>Scheduling...</span>
                                    </>
                                  ) : (
                                    <>
                                      <Clock className="w-4 h-4" />
                                      <span>Schedule</span>
                                    </>
                                  )}
                                </button>
                                <button
                                  onClick={handleSaveSelected}
                                  className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                >
                                  <Save className="w-4 h-4" />
                                  <span>Save Draft</span>
                                </button>
                                <button
                                  onClick={handleDeleteSelected}
                                  className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                >
                                  <Trash2 className="w-4 h-4" />
                                  <span>Delete</span>
                                </button>
                              </div>
                            </div>
                          )}

                          {/* Selection controls for view operations - below posts */}
                          {message.intent === 'view_content' && (
                            <div className="mt-4 flex flex-wrap items-center gap-3 p-3 rounded-lg">
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={() => handleSelectAll(message.content_items)}
                                  className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                >
                                  <CheckSquare className="w-4 h-4" />
                                  <span>Select All</span>
                                </button>
                                <button
                                  onClick={handleDeselectAll}
                                  className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                >
                                  <Square className="w-4 h-4" />
                                  <span>Deselect All</span>
                                </button>
                                <span className="text-base text-gray-600">
                                  {selectedContent.length}/{message.content_items.length} selected
                                </span>
                              </div>
                              {selectedContent.length > 0 && (
                                <div className="flex gap-2">
                                  <button
                                    onClick={handleEditSelected}
                                    disabled={selectedContent.length > 1}
                                    className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-lg ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                  >
                                    <Edit className="w-4 h-4" />
                                    <span>Edit {selectedContent.length === 1 ? '' : '(Select 1)'}</span>
                                  </button>
                                  <button
                                    onClick={handlePublishSelected}
                                    disabled={isPublishing}
                                    className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-lg ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                  >
                                    {isPublishing ? (
                                      <>
                                        <RefreshCw className="w-4 h-4 animate-spin" />
                                        <span>Publishing...</span>
                                      </>
                                    ) : (
                                      <>
                                        <Share className="w-4 h-4" />
                                        <span>Publish ({selectedContent.length})</span>
                                      </>
                                    )}
                                  </button>
                                  <button
                                    onClick={handleScheduleSelected}
                                    disabled={selectedContent.length > 1}
                                    className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-lg ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                  >
                                    <Calendar className="w-4 h-4" />
                                    <span>Schedule {selectedContent.length === 1 ? '' : '(Select 1)'}</span>
                                  </button>
                                  <button
                                    onClick={handleDeleteSelected}
                                    disabled={isDeleting}
                                    className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-lg ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                  >
                                    {isDeleting ? (
                                      <>
                                        <RefreshCw className="w-4 h-4 animate-spin" />
                                        <span>Deleting...</span>
                                      </>
                                    ) : (
                                      <>
                                        <Trash2 className="w-4 h-4" />
                                        <span>Delete ({selectedContent.length})</span>
                                      </>
                                    )}
                                  </button>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Selection controls for delete operations - below posts */}
                          {message.intent === 'delete_content' && (
                            <div className="mt-4 flex flex-wrap items-center gap-3 p-3 rounded-lg">
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={() => handleSelectAll(message.content_items)}
                                  className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                >
                                  <CheckSquare className="w-4 h-4" />
                                  <span>Select All</span>
                                </button>
                                <button
                                  onClick={handleDeselectAll}
                                  className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                                >
                                  <Square className="w-4 h-4" />
                                  <span>Deselect All</span>
                                </button>
                                <span className="text-base text-gray-600">
                                  {selectedContent.length}/{message.content_items.length} selected
                                </span>
                              </div>
                              {selectedContent.length > 0 && (
                                <button
                                  onClick={handleDeleteSelected}
                                  disabled={isDeleting}
                                  className="px-4 py-2 text-base bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
                                >
                                  {isDeleting ? (
                                    <>
                                      <RefreshCw className="w-4 h-4 animate-spin" />
                                      Deleting...
                                    </>
                                  ) : (
                                    <>
                                      <Trash2 className="w-4 h-4" />
                                      Delete Selected ({selectedContent.length})
                                    </>
                                  )}
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Render lead table for view_leads and other lead operations */}
                    {message.lead_items && message.lead_items.length > 0 && (
                      <div className="mt-4">
                        {/* Filter Controls */}
                        <div className={`rounded-xl shadow-lg border p-4 mb-4 ${
                          isDarkMode
                            ? 'bg-gray-800 border-gray-700 shadow-gray-900/50'
                            : 'bg-amber-50 border-amber-200'
                        }`}>
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                            {/* Search Filter */}
                            <div>
                              <label className={`block text-sm font-medium mb-2 ${
                                isDarkMode ? 'text-green-300' : 'text-green-800'
                              }`}>
                                Search
                              </label>
                              <input
                                type="text"
                                placeholder="Name or email..."
                                value={leadFilters.search}
                                onChange={(e) => setLeadFilters(prev => ({ ...prev, search: e.target.value }))}
                                className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 text-sm ${
                                  isDarkMode
                                    ? 'bg-gray-700 border-gray-600 text-gray-200 focus:ring-green-500 focus:border-green-500 placeholder-gray-400'
                                    : 'border-gray-300 focus:ring-green-500 focus:border-green-500'
                                }`}
                              />
                            </div>

                            {/* Status Filter */}
                            <div>
                              <label className={`block text-sm font-medium mb-2 ${
                                isDarkMode ? 'text-green-300' : 'text-green-800'
                              }`}>
                                Status
                              </label>
                              <select
                                value={leadFilters.status}
                                onChange={(e) => setLeadFilters(prev => ({ ...prev, status: e.target.value }))}
                                className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 text-sm ${
                                  isDarkMode
                                    ? 'bg-gray-700 border-gray-600 text-gray-200 focus:ring-green-500 focus:border-green-500'
                                    : 'border-gray-300 focus:ring-green-500 focus:border-green-500'
                                }`}
                              >
                                <option value="">All Status</option>
                                <option value="new">New</option>
                                <option value="contacted">Contacted</option>
                                <option value="responded">Responded</option>
                                <option value="qualified">Qualified</option>
                                <option value="converted">Converted</option>
                                <option value="lost">Lost</option>
                                <option value="invalid">Invalid</option>
                              </select>
                            </div>

                            {/* Source Filter */}
                            <div>
                              <label className={`block text-sm font-medium mb-2 ${
                                isDarkMode ? 'text-green-300' : 'text-green-800'
                              }`}>
                                Source
                              </label>
                              <select
                                value={leadFilters.source}
                                onChange={(e) => setLeadFilters(prev => ({ ...prev, source: e.target.value }))}
                                className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 text-sm ${
                                  isDarkMode
                                    ? 'bg-gray-700 border-gray-600 text-gray-200 focus:ring-green-500 focus:border-green-500'
                                    : 'border-gray-300 focus:ring-green-500 focus:border-green-500'
                                }`}
                              >
                                <option value="">All Sources</option>
                                <option value="Website">Website</option>
                                <option value="Facebook">Facebook</option>
                                <option value="Instagram">Instagram</option>
                                <option value="LinkedIn">LinkedIn</option>
                                <option value="Walk Ins">Walk Ins</option>
                                <option value="Referral">Referral</option>
                                <option value="Email">Email</option>
                                <option value="Phone Call">Phone Call</option>
                                <option value="Manual Entry">Manual Entry</option>
                              </select>
                            </div>

                            {/* Date From Filter */}
                            <div>
                              <label className={`block text-sm font-medium mb-2 ${
                                isDarkMode ? 'text-green-300' : 'text-green-800'
                              }`}>
                                Date From
                              </label>
                              <input
                                type="date"
                                value={leadFilters.dateFrom}
                                onChange={(e) => setLeadFilters(prev => ({ ...prev, dateFrom: e.target.value }))}
                                className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 text-sm ${
                                  isDarkMode
                                    ? 'bg-gray-700 border-gray-600 text-gray-200 focus:ring-green-500 focus:border-green-500'
                                    : 'border-gray-300 focus:ring-green-500 focus:border-green-500'
                                }`}
                              />
                            </div>

                            {/* Date To Filter */}
                            <div>
                              <label className={`block text-sm font-medium mb-2 ${
                                isDarkMode ? 'text-green-300' : 'text-green-800'
                              }`}>
                                Date To
                              </label>
                              <input
                                type="date"
                                value={leadFilters.dateTo}
                                onChange={(e) => setLeadFilters(prev => ({ ...prev, dateTo: e.target.value }))}
                                className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 text-sm ${
                                  isDarkMode
                                    ? 'bg-gray-700 border-gray-600 text-gray-200 focus:ring-green-500 focus:border-green-500'
                                    : 'border-gray-300 focus:ring-green-500 focus:border-green-500'
                                }`}
                              />
                            </div>
                          </div>

                          {/* Clear Filters Button */}
                          <div className="flex justify-end mt-4">
                            <button
                              onClick={() => setLeadFilters({
                                status: '',
                                source: '',
                                search: '',
                                dateFrom: '',
                                dateTo: ''
                              })}
                              className={`px-4 py-2 text-sm rounded-md transition-colors border ${
                                isDarkMode
                                  ? 'text-green-300 hover:text-green-200 hover:bg-gray-700 border-green-600'
                                  : 'text-green-700 hover:text-green-800 hover:bg-green-50 border-green-200'
                              }`}
                            >
                              Clear Filters
                            </button>
                          </div>
                        </div>

                        <div className={`rounded-xl shadow-lg border overflow-hidden ${
                          isDarkMode
                            ? 'bg-gray-800 border-gray-700 shadow-gray-900/50'
                            : 'bg-amber-50 border-amber-200'
                        }`}>
                          {(() => {
                            // Apply filters to lead items
                            const filteredLeads = message.lead_items.filter(lead => {
                              // Search filter (name or email)
                              if (leadFilters.search) {
                                const searchLower = leadFilters.search.toLowerCase()
                                const nameMatch = (lead.name || '').toLowerCase().includes(searchLower)
                                const emailMatch = (lead.email || '').toLowerCase().includes(searchLower)
                                if (!nameMatch && !emailMatch) return false
                              }

                              // Status filter
                              if (leadFilters.status && lead.status !== leadFilters.status) {
                                return false
                              }

                              // Source filter
                              if (leadFilters.source && lead.source_platform !== leadFilters.source) {
                                return false
                              }

                              // Date range filter
                              if (leadFilters.dateFrom || leadFilters.dateTo) {
                                const leadDate = new Date(lead.created_at)
                                if (leadFilters.dateFrom) {
                                  const fromDate = new Date(leadFilters.dateFrom)
                                  if (leadDate < fromDate) return false
                                }
                                if (leadFilters.dateTo) {
                                  const toDate = new Date(leadFilters.dateTo)
                                  toDate.setHours(23, 59, 59, 999) // End of day
                                  if (leadDate > toDate) return false
                                }
                              }

                              return true
                            })

                            return (
                              <>
                                {/* Results count */}
                                <div className={`px-4 py-3 border-b flex justify-between items-center ${
                                  isDarkMode
                                    ? 'bg-gray-700 border-gray-600'
                                    : 'bg-green-100 border-green-200'
                                }`}>
                                  <span className={`text-sm font-medium ${
                                    isDarkMode ? 'text-green-300' : 'text-green-800'
                                  }`}>
                                    Showing {filteredLeads.length} of {message.lead_items.length} leads
                                  </span>
                                </div>

                                <div className="overflow-x-auto">
                                  <table className="w-full">
                                    <thead className={`border-b ${
                                      isDarkMode
                                        ? 'bg-gray-700 border-gray-600'
                                        : 'bg-green-100 border-green-200'
                                    }`}>
                                      <tr>
                                        <th className="px-4 py-3 text-left">
                                          {(message.intent === 'view_leads' || message.intent === 'delete_leads') && (
                                            <button
                                              onClick={() => {
                                                const allFilteredIds = filteredLeads.map(item => item.lead_id || item.id)
                                                setSelectedLeads(allFilteredIds)
                                              }}
                                              className={`p-1 rounded transition-colors ${
                                                isDarkMode
                                                  ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-600'
                                                  : 'text-gray-600 hover:text-gray-800 hover:bg-gray-100'
                                              }`}
                                              title="Select All Filtered"
                                            >
                                              <CheckSquare className="w-4 h-4" />
                                            </button>
                                          )}
                                        </th>
                                        <th className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider ${
                                          isDarkMode ? 'text-gray-300' : 'text-gray-600'
                                        }`}>
                                          Lead Name
                                        </th>
                                        <th className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider ${
                                          isDarkMode ? 'text-gray-300' : 'text-gray-600'
                                        }`}>
                                          Email
                                        </th>
                                        <th className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider ${
                                          isDarkMode ? 'text-gray-300' : 'text-gray-600'
                                        }`}>
                                          Phone
                                        </th>
                                        <th className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider ${
                                          isDarkMode ? 'text-gray-300' : 'text-gray-600'
                                        }`}>
                                          Status
                                        </th>
                                        <th className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider ${
                                          isDarkMode ? 'text-gray-300' : 'text-gray-600'
                                        }`}>
                                          Source
                                        </th>
                                        <th className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider ${
                                          isDarkMode ? 'text-gray-300' : 'text-gray-600'
                                        }`}>
                                          Latest Remark
                                        </th>
                                        <th className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider ${
                                          isDarkMode ? 'text-gray-300' : 'text-gray-600'
                                        }`}>
                                          Created
                                        </th>
                                      </tr>
                                    </thead>
                                    <tbody className={`divide-y ${
                                      isDarkMode ? 'divide-gray-600' : 'divide-green-200'
                                    }`}>
                                      {filteredLeads.map((leadItem, index) => (
                                        <tr key={`${message.id}-${index}`} className={`transition-colors ${
                                          isDarkMode ? 'hover:bg-gray-700' : 'hover:bg-amber-50'
                                        }`}>
                                          <td className="px-4 py-3">
                                            {(message.intent === 'view_leads' || message.intent === 'delete_leads') && (
                                              <button
                                                onClick={() => handleLeadSelect(leadItem.lead_id || leadItem.id, message.intent)}
                                                className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                                                  selectedLeads.includes(leadItem.lead_id || leadItem.id)
                                                    ? 'bg-green-600 border-green-600 text-white'
                                                    : isDarkMode
                                                    ? 'bg-gray-700 border-gray-500 hover:border-green-400'
                                                    : 'bg-white border-gray-300 hover:border-green-400'
                                                }`}
                                              >
                                                {selectedLeads.includes(leadItem.lead_id || leadItem.id) ? (
                                                  <CheckSquare className="w-3 h-3" />
                                                ) : (
                                                  <Square className="w-3 h-3" />
                                                )}
                                              </button>
                                            )}
                                          </td>
                                          <td className="px-4 py-3">
                                            <div className="flex items-center gap-3">
                                              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center flex-shrink-0">
                                                <User className="w-4 h-4 text-white" />
                                              </div>
                                              <span className={`font-medium truncate ${
                                                isDarkMode ? 'text-gray-100' : 'text-gray-900'
                                              }`}>
                                                {leadItem.name || 'Unknown Lead'}
                                              </span>
                                            </div>
                                          </td>
                                          <td className={`px-4 py-3 text-sm truncate max-w-xs ${
                                            isDarkMode ? 'text-gray-300' : 'text-gray-600'
                                          }`}>
                                            {leadItem.email || 'No email'}
                                          </td>
                                          <td className={`px-4 py-3 text-sm ${
                                            isDarkMode ? 'text-gray-300' : 'text-gray-600'
                                          }`}>
                                            {leadItem.phone || 'No phone'}
                                          </td>
                                          <td className="px-4 py-3">
                                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                              leadItem.status === 'new' ? 'bg-blue-100 text-blue-800' :
                                              leadItem.status === 'contacted' ? 'bg-purple-100 text-purple-800' :
                                              leadItem.status === 'responded' ? 'bg-green-100 text-green-800' :
                                              leadItem.status === 'qualified' ? 'bg-orange-100 text-orange-800' :
                                              leadItem.status === 'converted' ? 'bg-emerald-100 text-emerald-800' :
                                              leadItem.status === 'lost' ? 'bg-gray-100 text-gray-800' :
                                              leadItem.status === 'invalid' ? 'bg-red-100 text-red-800' :
                                              'bg-gray-100 text-gray-800'
                                            }`}>
                                              {leadItem.status ? leadItem.status.charAt(0).toUpperCase() + leadItem.status.slice(1) : 'Unknown'}
                                            </span>
                                          </td>
                                          <td className={`px-4 py-3 text-sm ${
                                            isDarkMode ? 'text-gray-300' : 'text-gray-600'
                                          }`}>
                                            {leadItem.source || leadItem.source_platform || 'Unknown'}
                                          </td>
                                          <td className={`px-4 py-3 text-sm max-w-xs truncate ${
                                            isDarkMode ? 'text-gray-300' : 'text-gray-600'
                                          }`} title={leadItem.last_remark}>
                                            {leadItem.last_remark || 'No remarks'}
                                          </td>
                                          <td className={`px-4 py-3 text-sm ${
                                            isDarkMode ? 'text-gray-400' : 'text-gray-500'
                                          }`}>
                                            {leadItem.created_at || 'Unknown'}
                                          </td>
                                        </tr>
                                      ))}
                                    </tbody>
                                  </table>
                                </div>
                              </>
                            )
                          })()}
                        </div>
                      </div>
                    )}

                    {/* Render lead cards if available */}
                    {message.lead_id && fetchedLeads[message.lead_id] && (
                      <div className="mt-4 flex flex-wrap gap-4">
                        <LeadCard
                          key={message.lead_id}
                          lead={fetchedLeads[message.lead_id]}
                          onClick={() => setSelectedLeadId(message.lead_id)}
                          isSelected={selectedLeadId === message.lead_id}
                          selectionMode={true}
                          isDarkMode={isDarkMode}
                        />
                      </div>
                    )}

                    {/* Selection controls for lead operations */}
                    {message.intent === 'view_leads' && message.lead_items && message.lead_items.length > 0 && (
                      <div className="mt-4 flex flex-wrap items-center gap-3 p-3 rounded-lg">
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => {
                              const allLeadIds = message.lead_items.map(item => item.lead_id || item.id)
                              setSelectedLeads(allLeadIds)
                            }}
                            className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                          >
                            <CheckSquare className="w-4 h-4" />
                            <span>Select All</span>
                          </button>
                          <button
                            onClick={() => setSelectedLeads([])}
                            className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                                    isDarkMode
                                      ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                      : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                                  }`}
                          >
                            <Square className="w-4 h-4" />
                            <span>Deselect All</span>
                          </button>
                          <span className="text-base text-gray-600">
                            {selectedLeads.length}/{message.lead_items.length} selected
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Lead Action Buttons for Selected Leads */}
                    {selectedLeads.length > 0 && (
                      <div className={`mt-4 flex flex-wrap items-center gap-3 p-4 backdrop-blur-md border rounded-xl shadow-lg ${
                        isDarkMode
                          ? 'bg-gray-800/90 border-gray-700'
                          : 'bg-white/90 border-gray-200'
                      }`}>
                        <div className="flex gap-2">
                          <button
                            onClick={handleEditSelectedLead}
                            disabled={selectedLeads.length !== 1}
                            className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-lg ${
                              isDarkMode
                                ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                            }`}
                          >
                            <Edit className="w-4 h-4" />
                            <span>Edit Lead {selectedLeads.length !== 1 ? '(Select 1)' : ''}</span>
                          </button>
                          <button
                            onClick={handleDeleteSelectedLeads}
                            disabled={isDeleting}
                            className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none disabled:shadow-lg ${
                              isDarkMode
                                ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                            }`}
                          >
                            {isDeleting ? (
                              <>
                                <RefreshCw className="w-4 h-4 animate-spin" />
                                Deleting...
                              </>
                            ) : (
                              <>
                                <Trash2 className="w-4 h-4" />
                                Delete Selected ({selectedLeads.length})
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Lead Action Buttons */}
                    {message.lead_id && fetchedLeads[message.lead_id] && (
                      <div className={`mt-4 flex flex-wrap items-center gap-3 p-4 backdrop-blur-md border rounded-xl shadow-lg ${
                        isDarkMode
                          ? 'bg-gray-800/90 border-gray-700'
                          : 'bg-white/90 border-gray-200'
                      }`}>
                        <div className="flex gap-2">
                          <button
                            onClick={handleEditLead}
                            className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                              isDarkMode
                                ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                            }`}
                          >
                            <Edit className="w-4 h-4" />
                            <span>Edit</span>
                          </button>
                          <button
                            onClick={handleSaveLead}
                            className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                              isDarkMode
                                ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                            }`}
                          >
                            <Save className="w-4 h-4" />
                            <span>Save</span>
                          </button>
                          <button
                            onClick={handleDeleteLead}
                            className={`px-4 py-3 rounded-xl border transition-all duration-200 text-sm font-normal shadow-sm hover:shadow-md transform hover:scale-105 flex items-center gap-2 ${
                              isDarkMode
                                ? 'bg-gray-700 hover:bg-gray-600 text-gray-200 hover:text-white border-gray-600 hover:border-gray-500'
                                : 'bg-gray-100 hover:bg-gray-200 text-gray-800 hover:text-gray-900 border-gray-300 hover:border-gray-400'
                            }`}
                          >
                            <Trash2 className="w-4 h-4" />
                            <span>Delete</span>
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="relative">
                    <p className="text-base whitespace-pre-wrap pr-16">{message.text}</p>
                    <div className={`absolute bottom-0 right-0 text-xs ${
                      message.sender === 'user' ? 'text-white' : 'text-gray-400'
                    }`}>
                      {new Date(message.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                )}
              </div>

              {/* Message metadata */}
              {message.intent && (
                <div className="mt-1 text-xs text-gray-500 flex items-center gap-2">
                  <span className="px-2 py-0.5 bg-purple-100 text-purple-700 rounded-full">
                    {message.intent}
                  </span>
                  {message.step && (
                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded-full">
                      {message.step}
                    </span>
                  )}
                </div>
              )}

              {/* Thinking text below user messages when loading */}
              {isLoading && message.sender === 'user' && index === messages.length - 1 && (
                <div className="mt-2 ml-12">
                  <span className="text-sm text-gray-500 italic animate-pulse">
                    {getThinkingMessage()}
                  </span>
                </div>
              )}
            </div>
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className={`p-4 border-t ${
        isDarkMode ? 'border-gray-700' : 'border-gray-200'
      }`}>
        {/* New Chat Option */}
        <div className="flex items-center justify-between mb-3">
          <button
            onClick={handleReset}
            className={`flex items-center gap-2 text-sm font-medium transition-colors ${
              isDarkMode
                ? 'text-white hover:text-gray-200'
                : 'text-blue-600 hover:text-blue-700'
            }`}
          >
            <span className="text-lg">+</span>
            <span>New Chat</span>
          </button>
          <div className={`text-xs ${
            isDarkMode ? 'text-gray-400' : 'text-gray-500'
          }`}>
            Press Enter to send
          </div>
        </div>
        <div className="relative">
          <input
            ref={inputRef}
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask me to manage your content or leads..."
            className={`w-full px-4 pr-12 py-3 text-base rounded-[10px] backdrop-blur-sm focus:outline-none shadow-lg ${
              isDarkMode
                ? 'bg-gray-700/80 border-0 focus:ring-0 text-gray-100 placeholder-gray-400'
                : 'bg-white/80 border border-white/20 focus:ring-2 focus:ring-white/30 focus:border-white/50 text-gray-900 placeholder-gray-500'
            }`}
            disabled={isLoading}
          />
          <button
            onClick={handleSendMessage}
            disabled={isLoading || !inputMessage.trim()}
            className={`absolute right-2 top-1/2 transform -translate-y-1/2 w-6 h-6 transition-all flex items-center justify-center ${
              isDarkMode
                ? 'text-green-400 hover:text-green-300 disabled:text-gray-500'
                : 'text-blue-600 hover:text-blue-700 disabled:text-gray-400'
            } disabled:cursor-not-allowed`}
          >
            <Send className="w-5 h-5 transform rotate-45" />
          </button>
        </div>
        
        <div className={`mt-2 text-xs text-center ${
          isDarkMode ? 'text-gray-400' : 'text-gray-500'
        }`}>
          Try: "Show scheduled posts" • "Create lead" • "View analytics"
        </div>
      </div>

      {/* ATSN Content Modal */}
      {showContentModal && selectedContentForModal && (
        <ATSNContentModal
          content={selectedContentForModal}
          onClose={handleCloseContentModal}
        />
      )}

      {/* Date Picker Modal */}
      {showDatePicker && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Select Date Range</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Start Date
                </label>
                <input
                  type="date"
                  value={selectedDateRange.start}
                  onChange={(e) => setSelectedDateRange(prev => ({ ...prev, start: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  min="2024-01-01"
                  max="2030-12-31"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  End Date (Optional - leave empty for single date)
                </label>
                <input
                  type="date"
                  value={selectedDateRange.end}
                  onChange={(e) => setSelectedDateRange(prev => ({ ...prev, end: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  min={selectedDateRange.start || "2024-01-01"}
                  max="2030-12-31"
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={handleDatePickerCancel}
                className="flex-1 px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleDatePickerConfirm}
                disabled={!selectedDateRange.start}
                className="flex-1 px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Single Date Picker Modal for Lead Follow-up */}
      {showSingleDatePicker && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full mx-4 shadow-xl">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Select Follow-up Date</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Follow-up Date
                </label>
                <input
                  type="date"
                  value={selectedSingleDate}
                  onChange={(e) => setSelectedSingleDate(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  min={new Date().toISOString().split('T')[0]} // Today or later
                  max="2030-12-31"
                />
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={handleSingleDatePickerCancel}
                className="flex-1 px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSingleDatePickerConfirm}
                disabled={!selectedSingleDate}
                className="flex-1 px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-md transition-colors"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Media Upload Modal */}
      {showMediaUploadModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-2xl w-full mx-4 shadow-xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                {selectedFilesForUpload.length > 0 ? 'Confirm Upload' : 'Upload Media for Your Post'}
              </h3>
              <button
                onClick={() => {
                  setShowMediaUploadModal(false)
                  setSelectedFilesForUpload([])
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <AlertCircle className="w-6 h-6" />
              </button>
            </div>

            <div className="mb-4">
              {selectedFilesForUpload.length === 0 ? (
                <>
                  <p className="text-sm text-gray-600 mb-4">
                    Select an image or video file from your computer. Supported formats: JPG, PNG, GIF, WebP, MP4, MOV, AVI, WebM.
                  </p>

                  <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center cursor-pointer hover:border-gray-400 transition-colors"
                       onClick={() => document.getElementById('media-file-input').click()}>
                    <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-gray-700">
                        Click to select a file
                      </p>
                      <p className="text-xs text-gray-500">
                        Images: PNG, JPG, GIF, WebP up to 10MB | Videos: MP4, MOV, AVI, WebM up to 50MB
                      </p>
                    </div>
                    <input
                      id="media-file-input"
                      type="file"
                      accept="image/*,video/*"
                      onChange={(e) => {
                        const file = e.target.files[0]
                        if (file) {
                          // Validate file type
                          const allowedImageTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
                          const allowedVideoTypes = ['video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo', 'video/webm']
                          const allowedTypes = [...allowedImageTypes, ...allowedVideoTypes]

                          if (!allowedTypes.includes(file.type)) {
                            showError('Please select a valid image or video file')
                            return
                          }

                          // Validate file size
                          const isVideo = allowedVideoTypes.includes(file.type)
                          const maxSize = isVideo ? 50 * 1024 * 1024 : 10 * 1024 * 1024
                          if (file.size > maxSize) {
                            showError(`File size must be less than ${isVideo ? '50MB' : '10MB'}`)
                            return
                          }

                          handleFileSelection([file])
                        }
                      }}
                      className="hidden"
                    />
                  </div>
                </>
              ) : (
                <>
                  <p className="text-sm text-gray-600 mb-4">
                    Please confirm you want to upload this file:
                  </p>

                  <div className="bg-gray-50 rounded-lg p-4 mb-4">
                    <div className="flex items-start gap-4">
                      {selectedFilesForUpload[0].type.startsWith('image/') ? (
                        <img
                          src={URL.createObjectURL(selectedFilesForUpload[0])}
                          alt="Selected file"
                          className="w-20 h-20 object-cover rounded-lg border"
                        />
                      ) : (
                        <div className="w-20 h-20 bg-gray-200 rounded-lg flex items-center justify-center">
                          <Video className="w-8 h-8 text-gray-500" />
                        </div>
                      )}

                      <div className="flex-1">
                        <h4 className="font-medium text-gray-900 mb-1">
                          {selectedFilesForUpload[0].name}
                        </h4>
                        <p className="text-sm text-gray-600 mb-1">
                          Type: {selectedFilesForUpload[0].type.split('/')[1].toUpperCase()}
                        </p>
                        <p className="text-sm text-gray-600">
                          Size: {(selectedFilesForUpload[0].size / (1024 * 1024)).toFixed(2)} MB
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                    <div className="flex items-start gap-3">
                      <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
                      <div>
                        <h4 className="text-sm font-medium text-blue-900 mb-1">
                          Ready to upload
                        </h4>
                        <p className="text-sm text-blue-700">
                          This file will be uploaded to our secure storage and used in your content creation.
                        </p>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>

            <div className="flex gap-3">
              {selectedFilesForUpload.length === 0 ? (
                <button
                  onClick={() => {
                    setShowMediaUploadModal(false)
                    setSelectedFilesForUpload([])
                  }}
                  className="flex-1 px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                >
                  Cancel
                </button>
              ) : (
                <>
                  <button
                    onClick={handleCancelUpload}
                    disabled={isUploadingMedia}
                    className="flex-1 px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors disabled:opacity-50"
                  >
                    Change File
                  </button>
                  <button
                    onClick={handleConfirmUpload}
                    disabled={isUploadingMedia}
                    className="flex-1 px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-md transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {isUploadingMedia ? (
                      <>
                        <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                        Uploading...
                      </>
                    ) : (
                      <>
                        <Upload className="w-4 h-4" />
                        Upload & Continue
                      </>
                    )}
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Edit Lead Modal */}
      {showEditLeadModal && editLeadData && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl p-6 max-w-lg w-full mx-4 shadow-xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-xl font-semibold text-gray-900">Edit Lead</h3>
              <button
                onClick={() => {
                  setShowEditLeadModal(false)
                  setEditLeadData(null)
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <AlertCircle className="w-6 h-6" />
              </button>
            </div>

            <form onSubmit={(e) => {
              e.preventDefault()
              const formData = new FormData(e.target)
              const updatedLead = {
                lead_id: editLeadData.id,
                new_lead_name: formData.get('name'),
                new_lead_email: formData.get('email'),
                new_lead_phone: formData.get('phone'),
                new_lead_status: formData.get('status'),
                new_lead_source: formData.get('source_platform'),
                new_remarks: formData.get('remarks')
              }

              // Send edit message
              sendMessage(`Update lead: ${JSON.stringify(updatedLead)}`)

              setShowEditLeadModal(false)
              setEditLeadData(null)
              setSelectedLeads([])
            }} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Lead Name
                </label>
                <input
                  type="text"
                  name="name"
                  defaultValue={editLeadData.name}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Email Address
                </label>
                <input
                  type="email"
                  name="email"
                  defaultValue={editLeadData.email}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Phone Number
                </label>
                <input
                  type="tel"
                  name="phone"
                  defaultValue={editLeadData.phone}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Status
                </label>
                <select
                  name="status"
                  defaultValue={editLeadData.status}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="new">New</option>
                  <option value="contacted">Contacted</option>
                  <option value="responded">Responded</option>
                  <option value="qualified">Qualified</option>
                  <option value="converted">Converted</option>
                  <option value="lost">Lost</option>
                  <option value="invalid">Invalid</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Source Platform
                </label>
                <select
                  name="source_platform"
                  defaultValue={editLeadData.source_platform}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="Website">Website</option>
                  <option value="Facebook">Facebook</option>
                  <option value="Instagram">Instagram</option>
                  <option value="LinkedIn">LinkedIn</option>
                  <option value="Walk Ins">Walk Ins</option>
                  <option value="Referral">Referral</option>
                  <option value="Email">Email</option>
                  <option value="Phone Call">Phone Call</option>
                  <option value="Manual Entry">Manual Entry</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Remarks
                </label>
                <textarea
                  name="remarks"
                  defaultValue={editLeadData.last_remark}
                  rows={3}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Add any additional notes or remarks..."
                />
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => {
                    setShowEditLeadModal(false)
                    setEditLeadData(null)
                  }}
                  className="flex-1 px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-md transition-colors"
                >
                  Update Lead
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Character Card Tooltip */}
      <CharacterCard
        agentName={tooltipAgent}
        isVisible={!!tooltipAgent}
        position={tooltipPosition}
        isDarkMode={isDarkMode}
      />
    </div>
  )
}

export default ATSNChatbot

