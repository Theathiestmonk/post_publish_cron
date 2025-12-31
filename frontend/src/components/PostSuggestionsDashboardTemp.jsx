import React from 'react'
import { useAuth } from '../contexts/AuthContext'
import SideNavbar from './SideNavbar'
import MobileNavigation from './MobileNavigation'

const PostSuggestionsDashboard = () => {
  console.log('PostSuggestionsDashboard rendering...')

  const { user, profile } = useAuth()

  console.log('User:', user)
  console.log('Profile:', profile)

  if (!user) {
    console.log('User not authenticated, showing login message')
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-4">Not Authenticated</h1>
          <p className="text-gray-600">Please log in to access the dashboard.</p>
        </div>
      </div>
    )
  }

  console.log('User authenticated, rendering main component')

  return (
    <div className="h-screen bg-white overflow-hidden md:overflow-auto">
      {/* Mobile Navigation */}
      <MobileNavigation />

      {/* Side Navbar */}
      <SideNavbar />

      {/* Main Content */}
      <div className="md:ml-48 xl:ml-64 p-4">
        <h1 className="text-2xl font-bold mb-4">Post Suggestions Dashboard</h1>
        <p>This is a test to see if the component renders.</p>
        <p>User: {user?.email || 'No user'}</p>
        <p>Profile: {profile?.name || 'No profile'}</p>
      </div>
    </div>
  )
}

export default PostSuggestionsDashboard





