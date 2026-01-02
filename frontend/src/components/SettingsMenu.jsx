import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { X, CreditCard, User, Download } from 'lucide-react'
import { socialMediaService } from '../services/socialMedia'
import { connectionsAPI } from '../services/connections'
import { fetchAllConnections } from '../services/fetchConnections'
import { supabase } from '../lib/supabase'
import { useAuth } from '../contexts/AuthContext'
import EditProfileModal from './EditProfileModal'
import { subscriptionAPI } from '../services/subscription'
import { generateInvoicePDF } from '../services/pdfGenerator'

const SettingsMenu = ({ isOpen, onClose, isDarkMode = false }) => {
  const navigate = useNavigate()
  const { user } = useAuth()
  const [connections, setConnections] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedPlatform, setSelectedPlatform] = useState('')
  const [activeTab, setActiveTab] = useState('profile') // 'profile', 'tools', or 'billing'
  const [profile, setProfile] = useState(null)
  const [profileLoading, setProfileLoading] = useState(false)
  const [isEditModalOpen, setIsEditModalOpen] = useState(false)
  const [subscriptionStatus, setSubscriptionStatus] = useState(null)
  const [billingHistory, setBillingHistory] = useState([])
  const [billingLoading, setBillingLoading] = useState(false)
  const [isDescriptionExpanded, setIsDescriptionExpanded] = useState(false)
  const pollingIntervalRef = useRef(null)

  const platforms = [
    { id: 'facebook', name: 'Facebook' },
    { id: 'instagram', name: 'Instagram' },
    { id: 'twitter', name: 'X (Twitter)' },
    { id: 'linkedin', name: 'LinkedIn' },
    { id: 'youtube', name: 'YouTube' },
    { id: 'wordpress', name: 'WordPress' },
    { id: 'google', name: 'Google' }
  ]

  const stopStatusPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current)
      pollingIntervalRef.current = null
    }
  }

  const fetchConnections = async (forceRefresh = false) => {
    try {
      setLoading(true)
      // Force refresh by clearing cache if needed
      if (forceRefresh) {
        const { connectionsCache } = await import('../services/connectionsCache')
        connectionsCache.clearCache()
      }
      const connections = await fetchAllConnections(!forceRefresh)
      setConnections(connections)
      return connections
    } catch (error) {
      console.error('Error fetching connections:', error)
      setConnections([])
      return []
    } finally {
      setLoading(false)
    }
  }

  const startStatusPolling = (platformId, maxAttempts = 30) => {
    // Stop any existing polling
    stopStatusPolling()
    
    let attempts = 0
    
    const poll = async () => {
      attempts++
      
      try {
        // Force refresh to get latest status
        const updatedConnections = await fetchConnections(true)
        const isNowConnected = updatedConnections.some(
          conn => conn.platform === platformId && conn.connection_status === 'active'
        )
        
        if (isNowConnected) {
          // Connection successful, stop polling
          stopStatusPolling()
          setSelectedPlatform('')
          setLoading(false)
          return
        }
        
        // If max attempts reached, stop polling
        if (attempts >= maxAttempts) {
          stopStatusPolling()
          setSelectedPlatform('')
          setLoading(false)
          console.log(`Stopped polling for ${platformId} after ${maxAttempts} attempts`)
        }
      } catch (error) {
        console.error('Error polling connection status:', error)
        // Stop polling on error
        stopStatusPolling()
        setSelectedPlatform('')
        setLoading(false)
      }
    }
    
    // Start polling every 2 seconds
    const interval = setInterval(poll, 2000)
    pollingIntervalRef.current = interval
    
    // Initial check
    poll()
  }

  useEffect(() => {
    if (isOpen) {
      fetchConnections()
      if (activeTab === 'profile') {
        fetchProfile()
      } else if (activeTab === 'billing') {
        fetchBillingData()
      }
    } else {
      // Stop polling when menu is closed
      stopStatusPolling()
    }
    
    return () => {
      // Cleanup polling on unmount
      stopStatusPolling()
    }
  }, [isOpen, activeTab])

  const fetchProfile = async () => {
    try {
      setProfileLoading(true)
      if (!user) {
        return
      }

      const { data, error } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', user.id)
        .single()

      if (error) {
        console.error('Error fetching profile:', error)
        return
      }

      setProfile(data)
    } catch (error) {
      console.error('Error fetching profile:', error)
    } finally {
      setProfileLoading(false)
    }
  }

  const fetchBillingData = async () => {
    try {
      setBillingLoading(true)
      
      // Fetch subscription status
      const statusResponse = await subscriptionAPI.getSubscriptionStatus()
      setSubscriptionStatus(statusResponse.data)
      
      // Fetch billing history
      const historyResponse = await subscriptionAPI.getBillingHistory()
      setBillingHistory(historyResponse.data.billing_history || [])
    } catch (error) {
      console.error('Error fetching billing data:', error)
    } finally {
      setBillingLoading(false)
    }
  }

  const formatDate = (dateString) => {
    if (!dateString) return 'N/A'
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric'
    })
  }

  const formatCurrency = (amount) => {
    if (!amount) return 'N/A'
    return `INR ${(amount / 100).toFixed(2)}`
  }

  const handleDownloadBill = () => {
    try {
      if (!billingHistory || billingHistory.length === 0) {
        alert('No billing history available to download.')
        return
      }

      const latestBill = billingHistory[0]
      
      // Format invoice data for PDF generation
      const invoiceData = {
        id: latestBill.id || latestBill.transaction_id || 'N/A',
        date: subscriptionStatus?.subscription_start_date || latestBill.payment_date || latestBill.created_at || new Date().toISOString(),
        status: latestBill.status || 'completed',
        amount: latestBill.amount || 0,
        description: latestBill.description || 'Subscription Payment'
      }

      // Prepare user profile data
      const userProfile = {
        name: profile?.name,
        business_name: profile?.business_name,
        email: user?.email,
        subscription_plan: subscriptionStatus?.plan
      }

      // Generate PDF
      const pdf = generateInvoicePDF(invoiceData, billingHistory, userProfile)
      
      // Download PDF
      const dateStr = new Date(invoiceData.date).toISOString().split('T')[0]
      pdf.save(`bill-${invoiceData.id}-${dateStr}.pdf`)
    } catch (error) {
      console.error('Error generating bill PDF:', error)
      alert(`Failed to generate bill PDF: ${error.message || 'Unknown error'}`)
    }
  }

  // Listen for OAuth success events
  useEffect(() => {
    const handleOAuthSuccess = async (event) => {
      console.log('OAuth success event received:', event.detail)
      // Clear cache and fetch fresh connections
      const { connectionsCache } = await import('../services/connectionsCache')
      connectionsCache.clearCache()
      await fetchConnections(true)
      
      // If we have a selected platform, start polling for it
      if (selectedPlatform) {
        startStatusPolling(selectedPlatform)
      }
    }
    
    const handleOAuthError = (event) => {
      console.log('OAuth error event received:', event.detail)
      stopStatusPolling()
      setLoading(false)
      setSelectedPlatform('')
    }
    
    window.addEventListener('oauthSuccess', handleOAuthSuccess)
    window.addEventListener('oauthError', handleOAuthError)
    
    return () => {
      window.removeEventListener('oauthSuccess', handleOAuthSuccess)
      window.removeEventListener('oauthError', handleOAuthError)
    }
  }, [selectedPlatform])

  const isPlatformConnected = (platformId) => {
    return connections.some(conn => conn.platform === platformId && conn.connection_status === 'active')
  }

  const handleToggle = async (platformId) => {
    const isConnected = isPlatformConnected(platformId)
    
    if (isConnected) {
      // Disconnect
      await handleDisconnect(platformId)
    } else {
      // Connect
      await handleConnect(platformId)
    }
  }

  const handleConnect = async (platformId) => {
    try {
      setLoading(true)
      setSelectedPlatform(platformId)
      
      if (platformId === 'google') {
        await handleGoogleConnect()
        // Start polling for Google connection
        startStatusPolling(platformId)
      } else if (platformId === 'wordpress') {
        // Navigate to settings page for WordPress (requires credentials)
        navigate('/settings')
        onClose()
      } else {
        // OAuth connection
        await socialMediaService.connectWithOAuth(platformId)
        // Start polling for OAuth connection
        startStatusPolling(platformId)
      }
    } catch (error) {
      console.error(`Failed to connect ${platformId}:`, error)
      stopStatusPolling()
      setLoading(false)
      setSelectedPlatform('')
    }
    // Note: Don't set loading to false here - let polling handle it
  }

  const handleDisconnect = async (platformId) => {
    try {
      setLoading(true)
      setSelectedPlatform(platformId)
      
      // Find the connection
      const connection = connections.find(conn => conn.platform === platformId && conn.connection_status === 'active')
      
      if (!connection) {
        throw new Error('Connection not found')
      }

      if (platformId === 'google') {
        // Handle Google disconnect
        const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://agent-emily.onrender.com'
        const baseUrl = API_BASE_URL.replace(/\/+$/, '')
        const authToken = localStorage.getItem('authToken') || 
                          localStorage.getItem('token') || 
                          localStorage.getItem('access_token')
        
        const response = await fetch(`${baseUrl}/connections/google/disconnect`, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            ...(authToken && { 'Authorization': `Bearer ${authToken}` })
          }
        })
        
        const data = await response.json()
        if (!data.success) {
          throw new Error('Failed to disconnect Google')
        }
      } else if (platformId === 'wordpress') {
        // Handle WordPress disconnect
        const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://agent-emily.onrender.com'
        const baseUrl = API_BASE_URL.replace(/\/+$/, '')
        const authToken = localStorage.getItem('authToken') || 
                          localStorage.getItem('token') || 
                          localStorage.getItem('access_token')
        
        const response = await fetch(`${baseUrl}/connections/platform/wordpress/delete/${connection.id}`, {
          method: 'DELETE',
          headers: {
            'Content-Type': 'application/json',
            ...(authToken && { 'Authorization': `Bearer ${authToken}` })
          }
        })
        
        if (!response.ok) {
          throw new Error('Failed to disconnect WordPress')
        }
      } else {
        // Handle other platforms - use connection ID
        if (connection.id) {
          await connectionsAPI.disconnectAccount(connection.id)
        } else {
          throw new Error('Connection ID not found')
        }
      }
      
      // Clear cache and refresh connections
      const { connectionsCache } = await import('../services/connectionsCache')
      connectionsCache.clearCache()
      await fetchConnections(true)
    } catch (error) {
      console.error(`Failed to disconnect ${platformId}:`, error)
      alert(`Failed to disconnect ${platformId}. Please try again.`)
    } finally {
      setLoading(false)
      setSelectedPlatform('')
    }
  }

  const handleGoogleConnect = async () => {
    try {
      const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://agent-emily.onrender.com'
      const baseUrl = API_BASE_URL.replace(/\/+$/, '')
      
      const authToken = localStorage.getItem('authToken') || 
                        localStorage.getItem('token') || 
                        localStorage.getItem('access_token')
      const headers = {
        'Content-Type': 'application/json',
        ...(authToken && { 'Authorization': `Bearer ${authToken}` })
      }

      const response = await fetch(`${baseUrl}/connections/google/reconnect`, {
        method: 'POST',
        headers
      })
      const reconnectData = await response.json()
      
      if (reconnectData.success) {
        const popup = window.open(
          reconnectData.auth_url,
          'google-oauth',
          'width=600,height=700,scrollbars=yes,resizable=yes,status=yes,location=yes,toolbar=no,menubar=no'
        )
        
        const messageHandler = (event) => {
          const allowedOrigins = [
            window.location.origin,
            'https://emily.atsnai.com',
            'https://agent-emily.onrender.com'
          ]
          
          if (!allowedOrigins.includes(event.origin)) {
            return
          }
          
          if (event.data.type === 'OAUTH_SUCCESS') {
            popup.close()
            window.removeEventListener('message', messageHandler)
            // Start polling for Google connection status
            startStatusPolling('google')
          } else if (event.data.type === 'OAUTH_ERROR') {
            popup.close()
            window.removeEventListener('message', messageHandler)
            stopStatusPolling()
            setLoading(false)
            setSelectedPlatform('')
          }
        }
        
        window.addEventListener('message', messageHandler)
        
        const checkClosed = setInterval(() => {
          if (popup.closed) {
            clearInterval(checkClosed)
            window.removeEventListener('message', messageHandler)
            // Start polling when popup closes (user may have completed OAuth)
            startStatusPolling('google')
          }
        }, 1000)
      }
    } catch (error) {
      console.error('Failed to start Google connection:', error)
    }
  }

  const connectedPlatforms = platforms.filter(p => isPlatformConnected(p.id))
  const disconnectedPlatforms = platforms.filter(p => !isPlatformConnected(p.id))

  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 z-50 transition-opacity"
        onClick={onClose}
      />
      
      {/* Settings Panel */}
      <div
        className={`fixed top-0 left-0 h-full w-[600px] shadow-2xl z-50 transform transition-transform duration-300 ease-in-out ${
          isDarkMode
            ? 'bg-gray-800 border-r border-gray-700'
            : 'bg-white'
        } ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* Header */}
        <div className={`p-4 border-b flex items-center justify-between ${
          isDarkMode ? 'border-gray-700 bg-gray-900' : 'border-gray-200'
        }`}>
          <h2 className={`text-lg font-bold ${
            isDarkMode ? 'text-gray-100' : 'text-gray-900'
          }`}>Settings</h2>
          <button
            onClick={onClose}
            className={`p-1 rounded transition-colors ${
              isDarkMode
                ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-700'
                : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
            }`}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Two Column Content */}
        <div className="flex h-[calc(100vh-64px)] overflow-hidden">
          {/* Left Column - Tabs */}
          <div className={`w-1/3 border-r overflow-y-auto ${
            isDarkMode ? 'border-gray-700 bg-gray-900' : 'border-gray-200'
          }`}>
            <div className="p-2">
              <button
                onClick={() => {
                  setActiveTab('profile')
                  fetchProfile()
                }}
                className={`w-full flex items-center p-3 mb-2 rounded-lg transition-colors ${
                  activeTab === 'profile'
                    ? 'bg-gradient-to-r from-green-500 to-emerald-600 text-white shadow-lg'
                    : isDarkMode
                    ? 'text-gray-300 hover:bg-gray-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <User className="w-4 h-4 mr-2" />
                <span className="text-sm font-medium">Profile</span>
              </button>
              <button
                onClick={() => setActiveTab('tools')}
                className={`w-full flex items-center p-3 mb-2 rounded-lg transition-colors ${
                  activeTab === 'tools'
                    ? 'bg-gradient-to-r from-green-500 to-emerald-600 text-white shadow-lg'
                    : isDarkMode
                    ? 'text-gray-300 hover:bg-gray-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <span className="text-sm font-medium">Connections</span>
              </button>
              <button
                onClick={() => setActiveTab('billing')}
                className={`w-full flex items-center p-3 mb-2 rounded-lg transition-colors ${
                  activeTab === 'billing'
                    ? 'bg-gradient-to-r from-green-500 to-emerald-600 text-white shadow-lg'
                    : isDarkMode
                    ? 'text-gray-300 hover:bg-gray-700'
                    : 'text-gray-700 hover:bg-gray-100'
                }`}
              >
                <CreditCard className="w-4 h-4 mr-2" />
                <span className="text-sm font-medium">Billing</span>
              </button>
            </div>
          </div>

          {/* Right Column - Tab Content */}
          <div className="flex-1 overflow-y-auto p-4">
            {activeTab === 'profile' && (
              <div>
                <h3 className={`text-sm font-semibold mb-4 ${
                  isDarkMode ? 'text-gray-200' : 'text-gray-700'
                }`}>Profile</h3>
                {profileLoading ? (
                  <div className={`text-sm ${
                    isDarkMode ? 'text-gray-400' : 'text-gray-500'
                  }`}>Loading profile...</div>
                ) : profile ? (
                  <div className="space-y-4">
                    {/* Basic Information */}
                    <div className="space-y-3">
                      {profile.name && (
                        <div>
                          <div className="text-xs font-medium text-gray-500 mb-1">Name</div>
                          <div className={`text-sm ${
                            isDarkMode ? 'text-gray-200' : 'text-gray-900'
                          }`}>{profile.name}</div>
                        </div>
                      )}
                      {user?.email && (
                        <div>
                          <div className="text-xs font-medium text-gray-500 mb-1">Email</div>
                          <div className={`text-sm ${
                            isDarkMode ? 'text-gray-200' : 'text-gray-900'
                          }`}>{user.email}</div>
                        </div>
                      )}
                      {profile.business_name && (
                        <div>
                          <div className="text-xs font-medium text-gray-500 mb-1">Business Name</div>
                          <div className={`text-sm ${
                            isDarkMode ? 'text-gray-200' : 'text-gray-900'
                          }`}>{profile.business_name}</div>
                        </div>
                      )}
                      {profile.business_description && (
                        <div>
                          <div className="text-xs font-medium text-gray-500 mb-1">Business Description</div>
                          <div className={`text-sm ${!isDescriptionExpanded ? 'line-clamp-15' : ''} ${
                            isDarkMode ? 'text-gray-200' : 'text-gray-900'
                          }`}>
                            {profile.business_description}
                          </div>
                          {(profile.business_description.length > 750 || profile.business_description.split('\n').length > 15) && (
                            <button
                              onClick={() => setIsDescriptionExpanded(!isDescriptionExpanded)}
                              className="text-xs text-purple-600 hover:text-purple-700 mt-1 font-medium"
                            >
                              {isDescriptionExpanded ? 'See less' : 'See more'}
                            </button>
                          )}
                        </div>
                      )}
                      {profile.industry && Array.isArray(profile.industry) && profile.industry.length > 0 && (
                        <div>
                          <div className="text-xs font-medium text-gray-500 mb-1">Industry</div>
                          <div className={`text-sm ${
                            isDarkMode ? 'text-gray-200' : 'text-gray-900'
                          }`}>{profile.industry.join(', ')}</div>
                        </div>
                      )}
                    </div>
                    
                    {/* Action Button */}
                    <div className={`pt-4 border-t ${
                      isDarkMode ? 'border-gray-700' : 'border-gray-200'
                    }`}>
                      <button
                        onClick={() => setIsEditModalOpen(true)}
                        className={`w-full flex items-center justify-center p-3 border rounded-lg transition-colors ${
                          isDarkMode
                            ? 'border-gray-600 hover:bg-gray-700 text-gray-200'
                            : 'border-gray-200 hover:bg-gray-50 text-gray-900'
                        }`}
                      >
                        <span className="text-sm font-medium">Edit Profile</span>
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className={`text-sm ${
                    isDarkMode ? 'text-gray-400' : 'text-gray-500'
                  }`}>No profile data available</div>
                )}
              </div>
            )}

            {activeTab === 'tools' && (
              <div>
                <h3 className={`text-sm font-semibold mb-4 ${
                  isDarkMode ? 'text-gray-200' : 'text-gray-700'
                }`}>Connections</h3>
                
                 {/* All Platforms as Toggle Switches */}
                 <div className="space-y-3">
                   {platforms.map((platform) => {
                     const isConnected = isPlatformConnected(platform.id)
                     const isSelected = selectedPlatform === platform.id
                     const connection = connections.find(conn => 
                       conn.platform?.toLowerCase() === platform.id.toLowerCase()
                     )
                     const pageName = connection?.page_name || connection?.page_username || connection?.site_name || connection?.wordpress_site_name
                     
                     return (
                       <div
                         key={platform.id}
                         className="flex items-center justify-between py-2"
                       >
                         <span className={`text-sm font-medium ${
                           isDarkMode ? 'text-gray-200' : 'text-gray-900'
                         }`}>
                           {platform.name}
                           {isConnected && pageName && (
                             <span className={`font-normal ml-1 ${
                               isDarkMode ? 'text-gray-400' : 'text-gray-500'
                             }`}>({pageName})</span>
                           )}
                         </span>
                         <div className="flex items-center">
                           {loading && isSelected && (
                             <span className="mr-3 text-xs text-gray-500">
                               {isConnected ? 'Disconnecting...' : 'Connecting...'}
                             </span>
                           )}
                           {/* Toggle Switch */}
                           <div 
                             className="relative inline-block w-12 h-6 cursor-pointer"
                             onClick={() => !loading && handleToggle(platform.id)}
                           >
                             <div
                               className={`relative w-full h-full rounded-full transition-all duration-300 ${
                                 isConnected
                                   ? 'bg-green-500'
                                   : 'bg-gray-300'
                               }`}
                             >
                               <div
                                 className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-md transition-transform duration-300 ${
                                   isConnected
                                     ? 'transform translate-x-6'
                                     : 'transform translate-x-0'
                                 }`}
                               />
                             </div>
                           </div>
                         </div>
                       </div>
                     )
                   })}
                 </div>

                {/* Show message if loading */}
                {loading && platforms.length === 0 && (
                  <div className="text-sm text-gray-500 text-center py-8">
                    Loading platforms...
                  </div>
                )}
              </div>
            )}

            {activeTab === 'billing' && (
              <div>
                <h3 className={`text-sm font-semibold mb-4 ${
                  isDarkMode ? 'text-gray-200' : 'text-gray-700'
                }`}>Billing</h3>
                {billingLoading ? (
                  <div className={`text-sm ${
                    isDarkMode ? 'text-gray-400' : 'text-gray-500'
                  }`}>Loading billing information...</div>
                ) : (
                  <div className="space-y-4">
                    {/* Current Plan */}
                    {subscriptionStatus && (
                      <div className={`p-4 rounded-lg ${
                        isDarkMode ? 'bg-gray-700' : 'bg-gray-50'
                      }`}>
                        <h4 className={`text-xs font-medium mb-3 uppercase ${
                          isDarkMode ? 'text-gray-300' : 'text-gray-600'
                        }`}>Current Plan</h4>
                        <div className="space-y-2">
                          <div>
                            <div className="text-xs text-gray-500 mb-1">Plan</div>
                            <div className={`text-sm font-medium capitalize ${
                              isDarkMode ? 'text-gray-200' : 'text-gray-900'
                            }`}>
                              {subscriptionStatus.plan || 'No active plan'}
                            </div>
                          </div>
                          {subscriptionStatus.status && (
                            <div>
                              <div className={`text-xs mb-1 ${
                                isDarkMode ? 'text-gray-400' : 'text-gray-500'
                              }`}>Status</div>
                              <div className={`text-sm font-medium capitalize ${
                                isDarkMode ? 'text-gray-200' : 'text-gray-900'
                              }`}>
                                {subscriptionStatus.status}
                              </div>
                            </div>
                          )}
                          {subscriptionStatus.billing_cycle && (
                            <div>
                              <div className={`text-xs mb-1 ${
                                isDarkMode ? 'text-gray-400' : 'text-gray-500'
                              }`}>Billing Cycle</div>
                              <div className={`text-sm font-medium capitalize ${
                                isDarkMode ? 'text-gray-200' : 'text-gray-900'
                              }`}>
                                {subscriptionStatus.billing_cycle}
                              </div>
                            </div>
                          )}
                          {subscriptionStatus.subscription_end_date && (
                            <div>
                              <div className="text-xs text-gray-500 mb-1">Renew Date</div>
                              <div className="text-sm font-medium text-gray-900">
                                {formatDate(subscriptionStatus.subscription_end_date)}
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Latest Bill Paid */}
                    {billingHistory && billingHistory.length > 0 && (
                      <div className={`p-4 rounded-lg ${
                        isDarkMode ? 'bg-gray-700' : 'bg-gray-50'
                      }`}>
                        <h4 className={`text-xs font-medium mb-3 uppercase ${
                          isDarkMode ? 'text-gray-300' : 'text-gray-600'
                        }`}>Latest Bill Paid</h4>
                        {(() => {
                          const latestBill = billingHistory[0]
                          return (
                            <div className="space-y-2">
                              <div>
                                <div className={`text-xs mb-1 ${
                                  isDarkMode ? 'text-gray-400' : 'text-gray-500'
                                }`}>Amount</div>
                                <div className={`text-sm font-medium ${
                                  isDarkMode ? 'text-gray-200' : 'text-gray-900'
                                }`}>
                                  {formatCurrency(latestBill.amount)}
                                </div>
                              </div>
                              <div>
                                <div className="text-xs text-gray-500 mb-1">Date</div>
                                <div className="text-sm font-medium text-gray-900">
                                  {subscriptionStatus?.subscription_start_date 
                                    ? formatDate(subscriptionStatus.subscription_start_date)
                                    : formatDate(latestBill.payment_date || latestBill.created_at)}
                                </div>
                              </div>
                              {latestBill.status && (
                                <div>
                                  <div className={`text-xs mb-1 ${
                                isDarkMode ? 'text-gray-400' : 'text-gray-500'
                              }`}>Status</div>
                                  <div className={`text-sm font-medium capitalize ${
                                isDarkMode ? 'text-gray-200' : 'text-gray-900'
                              }`}>
                                    {latestBill.status}
                                  </div>
                                </div>
                              )}
                            </div>
                          )
                        })()}
                        
                        {/* Download Bill Button */}
                        <button
                          onClick={handleDownloadBill}
                          className={`w-full mt-4 flex items-center justify-center gap-2 p-3 border rounded-lg transition-colors ${
                            isDarkMode
                              ? 'border-gray-600 hover:bg-gray-700 text-gray-200'
                              : 'border-gray-200 hover:bg-gray-50 text-gray-900'
                          }`}
                        >
                          <Download className={`w-4 h-4 ${
                            isDarkMode ? 'text-gray-400' : 'text-gray-600'
                          }`} />
                          <span className="text-sm font-medium">Download Bill</span>
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Edit Profile Modal */}
      <EditProfileModal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        onSuccess={() => {
          setIsEditModalOpen(false)
          fetchProfile()
        }}
      />
    </>
  )
}

export default SettingsMenu

