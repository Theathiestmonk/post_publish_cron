import React, { useState, useEffect, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useNotifications } from '../contexts/NotificationContext'
import { contentAPI } from '../services/content'
import { onboardingAPI } from '../services/onboarding'
import SideNavbar from './SideNavbar'
import MobileNavigation from './MobileNavigation'
import { Facebook, Instagram, Linkedin, Youtube, Building2, Hash, FileText, Video, X } from 'lucide-react'

const PostSuggestionsDashboard = () => {
  console.log('PostSuggestionsDashboard rendering...')

  const { user } = useAuth()

  // Custom scrollbar styles
  const scrollbarStyles = `
    .scrollbar-transparent::-webkit-scrollbar {
      height: 8px;
      background: transparent;
    }
    .scrollbar-transparent::-webkit-scrollbar-track {
      background: transparent;
    }
    .scrollbar-transparent::-webkit-scrollbar-thumb {
      background: rgba(156, 163, 175, 0.3);
      border-radius: 4px;
    }
    .scrollbar-transparent::-webkit-scrollbar-thumb:hover {
      background: rgba(156, 163, 175, 0.5);
    }
    .scrollbar-transparent {
      scrollbar-width: thin;
      scrollbar-color: rgba(156, 163, 175, 0.3) transparent;
    }
  `
  const { showError } = useNotifications()

  // Profile state
  const [profile, setProfile] = useState(null)
  const [loadingProfile, setLoadingProfile] = useState(true)

  // State for different sections
  const [suggestedPosts, setSuggestedPosts] = useState([])
  const [suggestedBlogs, setSuggestedBlogs] = useState([])
  const [suggestedVideos, setSuggestedVideos] = useState([])


  // Filter states
  const [postsFilter, setPostsFilter] = useState('all')

  // Fetch profile data
  const fetchProfile = async () => {
    try {
      setLoadingProfile(true)
      const response = await onboardingAPI.getProfile()
      setProfile(response.data)
      console.log('Fetched profile:', response.data)
    } catch (error) {
      console.error('Error fetching profile:', error)
      setProfile(null)
    } finally {
      setLoadingProfile(false)
    }
  }

  // Get available platforms from user profile
  const getAvailablePlatforms = () => {
    console.log('Profile social_media_platforms:', profile?.social_media_platforms)
    if (!profile?.social_media_platforms) {
      console.log('No social_media_platforms found in profile')
      return []
    }

    // Parse the platforms from profile - could be array or string
    let platforms = []
    try {
      if (typeof profile.social_media_platforms === 'string') {
        platforms = JSON.parse(profile.social_media_platforms)
      } else if (Array.isArray(profile.social_media_platforms)) {
        platforms = profile.social_media_platforms
      }
    } catch (error) {
      console.error('Error parsing social media platforms:', error)
      return []
    }

    // Filter out invalid entries and ensure we have strings
    return platforms.filter(platform => platform && typeof platform === 'string')
  }

  console.log('User:', user)
  console.log('Profile:', profile)

  // Fetch suggested posts using the same API as ContentDashboard
  const fetchSuggestedPosts = async () => {
    try {
      const result = await contentAPI.getAllContent(50, 0)

      if (result.error) throw new Error(result.error)

      const posts = result.data || []
      console.log('Fetched posts data:', posts.slice(0, 3)) // Log first 3 posts to see structure
      setSuggestedPosts(posts)
    } catch (error) {
      console.error('Error fetching suggested posts:', error)
      showError('Failed to load suggested posts')
    }
  }

  // Fetch suggested blogs using the same API, then filter for Blog channel
  const fetchSuggestedBlogs = async () => {
    try {
      const result = await contentAPI.getAllContent(50, 0)

      if (result.error) throw new Error(result.error)

      // Filter for Blog channel content
      const blogs = (result.data || []).filter(content =>
        content.channel?.toLowerCase() === 'blog'
      )

      setSuggestedBlogs(blogs.slice(0, 10))
    } catch (error) {
      console.error('Error fetching suggested blogs:', error)
      showError('Failed to load suggested blogs')
    }
  }

  // Fetch suggested videos (placeholder)
  const fetchSuggestedVideos = async () => {
    try {
      // Placeholder - to be implemented
      setSuggestedVideos([])
    } catch (error) {
      console.error('Error fetching suggested videos:', error)
    }
  }

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

      showSuccess('Message copied to clipboard')
    } catch (error) {
      console.error('Error copying message:', error)
      showError('Failed to copy message')
    }
  }

  // Filter posts by platform
  const getFilteredPosts = () => {
    if (postsFilter === 'all') return suggestedPosts

    return suggestedPosts.filter(post => {
      const postPlatform = post.platform?.toLowerCase()?.trim() || ''
      const filterPlatform = postsFilter.toLowerCase().trim()

      // Handle Twitter/X normalization
      if (filterPlatform === 'twitter' && (postPlatform === 'x' || postPlatform === 'twitter')) {
        return true
      }

      return postPlatform === filterPlatform
    })
  }

  // State to track which container mouse is over
  const [activeContainer, setActiveContainer] = useState(null)

  // Global wheel handler - prevent default and scroll horizontally
  const handleGlobalWheel = useRef((e) => {
    console.log('Global wheel event triggered, activeContainer:', !!activeContainer)
    if (activeContainer) {
      console.log('Preventing default and scrolling horizontally')
      e.preventDefault()
      e.stopImmediatePropagation()

      const scrollAmount = e.deltaY * 0.8 // Adjust scroll sensitivity
      activeContainer.scrollLeft += scrollAmount
      console.log('Scrolled by:', scrollAmount, 'new scrollLeft:', activeContainer.scrollLeft)
    }
  })

  // Handle mouse entering cards section
  const handleMouseEnter = (e) => {
    console.log('Mouse entered cards section')
    const container = e.currentTarget
    setActiveContainer(container)
    document.body.style.overflow = 'hidden'
    // Add global wheel listener with capture
    window.addEventListener('wheel', handleGlobalWheel.current, {
      passive: false,
      capture: true,
      once: false
    })
    console.log('Added global wheel listener')
  }

  // Handle mouse leaving cards section
  const handleMouseLeave = (e) => {
    console.log('Mouse left cards section')
    setActiveContainer(null)
    document.body.style.overflow = 'auto'
    // Remove global wheel listener
    window.removeEventListener('wheel', handleGlobalWheel.current, { capture: true })
    console.log('Removed global wheel listener')
  }

  // Platform icon helper
  const getPlatformIcon = (platform) => {
    const platformLower = platform?.toLowerCase()
    switch (platformLower) {
      case 'facebook':
        return <Facebook className="w-4 h-4" />
      case 'instagram':
        return <Instagram className="w-4 h-4" />
      case 'linkedin':
        return <Linkedin className="w-4 h-4" />
      case 'youtube':
        return <Youtube className="w-4 h-4" />
      case 'x':
      case 'twitter':
        return <X className="w-4 h-4" />
      case 'google business':
      case 'google':
        return <Building2 className="w-4 h-4" />
      default:
        return <Hash className="w-4 h-4" />
    }
  }

  // Status color helper
  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'published':
        return 'text-green-600'
      case 'scheduled':
        return 'text-blue-600'
      case 'draft':
        return 'text-gray-600'
      default:
        return 'text-gray-500'
    }
  }

  useEffect(() => {
    if (user) {
      fetchProfile()
      fetchSuggestedPosts()
      fetchSuggestedBlogs()
      fetchSuggestedVideos()
    }
  }, [user])

  // Cleanup: restore scrolling and remove listeners when component unmounts
  useEffect(() => {
    return () => {
      document.body.style.overflow = 'auto'
      window.removeEventListener('wheel', handleGlobalWheel.current, { capture: true })
    }
  }, [])

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
      {/* Custom scrollbar styles */}
      <style dangerouslySetInnerHTML={{ __html: scrollbarStyles }} />

      {/* Mobile Navigation */}
      <MobileNavigation />

      {/* Side Navbar */}
      <SideNavbar />

      {/* Main Content */}
      <div className="md:ml-48 xl:ml-64 p-4 lg:p-6 overflow-y-auto">
        <div className="space-y-8">

          {/* Section 1: Suggested Posts */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold text-gray-900">Suggested Posts</h2>
            </div>

            {/* Platform Filter Buttons */}
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => setPostsFilter('all')}
                className={`px-4 py-2 rounded-lg border transition-all text-sm font-medium ${
                  postsFilter === 'all'
                    ? 'bg-purple-50 border-purple-300 text-purple-700 shadow-sm'
                    : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50 hover:border-gray-300'
                }`}
              >
                All Platforms
              </button>
              {getAvailablePlatforms().map((platform) => {
                const platformKey = platform.toLowerCase()
                const isSelected = postsFilter === platformKey

                return (
                  <button
                    key={platformKey}
                    onClick={() => setPostsFilter(platformKey)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-all text-sm font-medium ${
                      isSelected
                        ? 'bg-purple-50 border-purple-300 text-purple-700 shadow-sm'
                        : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50 hover:border-gray-300'
                    }`}
                  >
                    {getPlatformIcon(platform)}
                    <span className="capitalize">{platform}</span>
                  </button>
                )
              })}
            </div>

            <div
              className="overflow-x-auto pb-4 scrollbar-transparent"
              onMouseEnter={handleMouseEnter}
              onMouseLeave={handleMouseLeave}
            >
                <div className="flex gap-4" style={{ minWidth: 'max-content' }}>
                  {getFilteredPosts().length > 0 ? (
                    getFilteredPosts().map((post) => {
                      const contentPlatform = post.platform?.toLowerCase().trim() || ''
                      const normalizedPlatform = contentPlatform === 'twitter' ? 'x' : contentPlatform

                      return (
                        <div
                          key={post.id}
                          className="flex-shrink-0 w-80 bg-white rounded-xl shadow-md border border-gray-200 p-4 hover:shadow-lg transition-shadow cursor-pointer"
                        >
                          <div className="flex items-center gap-2 mb-3">
                            {getPlatformIcon(normalizedPlatform)}
                            <span className="text-sm font-medium text-gray-700 capitalize">
                              {normalizedPlatform}
                            </span>
                            <span className={`text-xs px-2 py-1 rounded-full ${getStatusColor(post.status)} bg-gray-100`}>
                              {post.status || 'Draft'}
                            </span>
                          </div>

                              {(post.primary_image_url || post.media_url || post.image_url) && (
                                <img
                                  src={post.primary_image_url || post.media_url || post.image_url}
                                  alt="Post preview"
                                  className="w-full aspect-square object-cover rounded-lg mb-3"
                                  onError={(e) => {
                                    console.log('Post image failed to load:', e.target.src, 'for post:', post.id)
                                    e.target.style.display = 'none'
                                  }}
                                />
                              )}

                              <h3 className="font-semibold text-gray-900 mb-2 line-clamp-2">
                                {post.title || 'Untitled Post'}
                              </h3>

                              <p className="text-sm text-gray-600 line-clamp-3 mb-3">
                                {post.content || post.description || 'No content available'}
                              </p>

                          <div className="flex items-center justify-between text-xs text-gray-500">
                            <span>{new Date(post.scheduled_date || post.created_at).toLocaleDateString()}</span>
                            <button className="text-purple-600 hover:text-purple-700 font-medium">
                              View Details →
                            </button>
                          </div>
                        </div>
                      )
                    })
                  ) : (
                    <div className="flex items-center justify-center py-8 text-gray-500">
                      Loading suggested content...
                    </div>
                  )}
                </div>
              </div>
          </div>

          {/* Section 2: Suggested Blogs */}
          <div className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900">Suggested Blogs</h2>

            <div
              className="overflow-x-auto pb-4 scrollbar-transparent"
              onMouseEnter={handleMouseEnter}
              onMouseLeave={handleMouseLeave}
            >
                <div className="flex gap-4" style={{ minWidth: 'max-content' }}>
                  {suggestedBlogs.length > 0 ? (
                    suggestedBlogs.map((blog) => (
                      <div
                        key={blog.id}
                        className="flex-shrink-0 w-80 bg-white rounded-xl shadow-md border border-gray-200 p-4 hover:shadow-lg transition-shadow cursor-pointer"
                      >
                        <div className="flex items-center gap-2 mb-3">
                          <FileText className="w-4 h-4 text-blue-600" />
                          <span className="text-sm font-medium text-gray-700">Blog Post</span>
                          <span className={`text-xs px-2 py-1 rounded-full ${getStatusColor(blog.status)} bg-gray-100`}>
                            {blog.status || 'Draft'}
                          </span>
                        </div>

                              {(blog.primary_image_url || blog.media_url || blog.image_url) && (
                                <img
                                  src={blog.primary_image_url || blog.media_url || blog.image_url}
                                  alt="Blog preview"
                                  className="w-full h-32 object-cover rounded-lg mb-3"
                                  onError={(e) => {
                                    console.log('Blog image failed to load:', e.target.src)
                                    e.target.style.display = 'none'
                                  }}
                                />
                              )}

                              <h3 className="font-semibold text-gray-900 mb-2 line-clamp-2">
                                {blog.title || 'Untitled Blog'}
                              </h3>

                              <p className="text-sm text-gray-600 line-clamp-3 mb-3">
                                {blog.content || blog.description || 'No content available'}
                              </p>

                        <div className="flex items-center justify-between text-xs text-gray-500">
                          <span>{new Date(blog.scheduled_date || blog.created_at).toLocaleDateString()}</span>
                          <button className="text-purple-600 hover:text-purple-700 font-medium">
                            View Details →
                          </button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="flex items-center justify-center py-8 text-gray-500">
                      Loading suggested content...
                    </div>
                  )}
                </div>
              </div>
          </div>

          {/* Section 3: Suggested Videos */}
          <div className="space-y-4">
            <h2 className="text-2xl font-bold text-gray-900">Suggested Videos</h2>

            <div className="bg-white rounded-xl shadow-md border border-gray-200 p-8">
                <div className="text-center">
                  <Video className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">Coming Soon</h3>
                  <p className="text-gray-600">
                    Video suggestions will be available in a future update.
                  </p>
                </div>
              </div>
          </div>

        </div>
      </div>
    </div>
  )
}

export default PostSuggestionsDashboard
