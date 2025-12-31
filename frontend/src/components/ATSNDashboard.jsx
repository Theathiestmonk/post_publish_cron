import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { useNotifications } from '../contexts/NotificationContext'
import SideNavbar from './SideNavbar'
import MobileNavigation from './MobileNavigation'
import MainContentLoader from './MainContentLoader'
import ATSNChatbot from './ATSNChatbot'
import LipSyncDemo from './LipSyncDemo'
import { Sparkles, MessageCircle, Mic } from 'lucide-react'

const API_BASE_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

function ATSNDashboard() {
  const { user, logout } = useAuth()
  const { showSuccess, showError, showInfo } = useNotifications()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('chatbot') // 'chatbot' or 'lip-sync'

  // Check user authentication
  useEffect(() => {
    if (!user) {
      navigate('/login')
      return
    }
    setLoading(false)
  }, [user, navigate])


  const handleLogout = async () => {
    try {
      await logout()
      navigate('/login')
    } catch (error) {
      showError('Failed to logout')
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <MainContentLoader />
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Side Navbar */}
      <SideNavbar
        user={user}
        onLogout={handleLogout}
        currentPath="/atsn"
      />

      {/* Mobile Navigation */}
      <MobileNavigation
        user={user}
        onLogout={handleLogout}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden ml-48 xl:ml-64">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-purple-600 to-pink-600 flex items-center justify-center">
                <Sparkles className="w-7 h-7 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">ATSN Agent</h1>
                <p className="text-sm text-gray-600">Content & Lead Management System</p>
              </div>
            </div>

            {/* Tab Navigation */}
            <div className="flex bg-gray-100 rounded-lg p-1">
              <button
                onClick={() => setActiveTab('chatbot')}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'chatbot'
                    ? 'bg-white text-purple-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <MessageCircle className="w-4 h-4" />
                Chatbot
              </button>
              <button
                onClick={() => setActiveTab('lip-sync')}
                className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                  activeTab === 'lip-sync'
                    ? 'bg-white text-purple-600 shadow-sm'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                <Mic className="w-4 h-4" />
                Lip-Sync Demo
              </button>
            </div>
          </div>
        </div>

        {/* Content Area */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'chatbot' && (
            /* Chatbot - Full Height */
            <div className="h-full p-6">
              <ATSNChatbot />
            </div>
          )}

          {activeTab === 'lip-sync' && (
            /* Lip-Sync Demo - Full Height */
            <div className="h-full overflow-y-auto">
              <LipSyncDemo />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ATSNDashboard
