const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

class BlogService {
  async getAuthToken() {
    // Try multiple token sources
    let token = localStorage.getItem('authToken') || 
                localStorage.getItem('token') || 
                localStorage.getItem('access_token')
    
    if (!token) {
      // Try to get token from Supabase session
      try {
        const { supabase } = await import('../lib/supabase')
        const { data: { session } } = await supabase.auth.getSession()
        token = session?.access_token || null
        
        // If we got a token from Supabase, store it in localStorage
        if (token) {
          localStorage.setItem('authToken', token)
        }
      } catch (error) {
        console.error('Error getting Supabase token:', error)
        return null
      }
    }
    
    // If we still don't have a token, try to refresh the session
    if (!token) {
      try {
        const { supabase } = await import('../lib/supabase')
        const { data: { session }, error } = await supabase.auth.refreshSession()
        
        if (error) {
          console.error('Error refreshing session:', error)
          // Clear invalid tokens
          localStorage.removeItem('authToken')
          localStorage.removeItem('token')
          localStorage.removeItem('access_token')
          return null
        }
        
        token = session?.access_token || null
        if (token) {
          localStorage.setItem('authToken', token)
        }
      } catch (error) {
        console.error('Error refreshing session:', error)
        // Clear all tokens
        localStorage.removeItem('authToken')
        localStorage.removeItem('token')
        localStorage.removeItem('access_token')
        return null
      }
    }
    
    return token
  }

  async makeRequest(endpoint, options = {}, requireAuth = true) {
    let token = await this.getAuthToken()
    const url = `${API_URL}${endpoint}`
    
    console.log('Blog service request:', { url, token: token ? 'present' : 'missing', requireAuth })
    
    const defaultOptions = {
      headers: {
        'Content-Type': 'application/json'
      }
    }
    
    // Only add auth token if available and required
    if (token && requireAuth) {
      defaultOptions.headers['Authorization'] = `Bearer ${token}`
    } else if (token && !requireAuth) {
      // Optional: include token if available even for public requests
      defaultOptions.headers['Authorization'] = `Bearer ${token}`
    }
    
    if (requireAuth && !token) {
      console.error('No authentication token found for protected endpoint')
      // Try one more time to get session before giving up
      try {
        const { supabase } = await import('../lib/supabase')
        const { data: { session } } = await supabase.auth.getSession()
        if (session?.access_token) {
          token = session.access_token
          localStorage.setItem('authToken', token)
          defaultOptions.headers['Authorization'] = `Bearer ${token}`
        } else {
          // Only redirect if we're absolutely sure there's no session
          console.error('No session available, redirecting to login')
          localStorage.removeItem('authToken')
          localStorage.removeItem('token')
          localStorage.removeItem('access_token')
          window.location.href = '/login'
          throw new Error('Authentication required. Please log in.')
        }
      } catch (error) {
        console.error('Error checking session:', error)
        // Only redirect if session check fails completely
        localStorage.removeItem('authToken')
        localStorage.removeItem('token')
        localStorage.removeItem('access_token')
        window.location.href = '/login'
        throw new Error('Authentication required. Please log in.')
      }
    }

    try {
      const response = await fetch(url, { ...defaultOptions, ...options })
      console.log('Blog service response:', { status: response.status, ok: response.ok })
      
      if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Unknown error' }))
        console.error('Blog service error:', error)
        
        // Handle authentication errors with token refresh
        if (response.status === 401 && requireAuth) {
          console.log('🔄 401 error in blog service, attempting to refresh session...')
          
          // Try to refresh the session before logging out
          try {
            const { supabase } = await import('../lib/supabase')
            const { data: { session }, error: sessionError } = await supabase.auth.getSession()
            
            if (session?.access_token && !sessionError) {
              // Got a fresh token, retry the request
              console.log('✅ Session refreshed, retrying blog request...')
              const retryOptions = {
                ...defaultOptions,
                ...options,
                headers: {
                  ...defaultOptions.headers,
                  ...options.headers,
                  'Authorization': `Bearer ${session.access_token}`
                }
              }
              localStorage.setItem('authToken', session.access_token)
              
              const retryResponse = await fetch(url, retryOptions)
              if (retryResponse.ok) {
                return retryResponse.json()
              }
              // If retry also fails with 401, then logout
              if (retryResponse.status === 401) {
                console.error('❌ Retry also failed with 401, redirecting to login')
                localStorage.removeItem('authToken')
                localStorage.removeItem('token')
                localStorage.removeItem('access_token')
                window.location.href = '/login'
                throw new Error('Authentication failed. Please log in again.')
              }
            } else {
              // No valid session, logout
              console.error('❌ No valid session after 401, redirecting to login')
              localStorage.removeItem('authToken')
              localStorage.removeItem('token')
              localStorage.removeItem('access_token')
              window.location.href = '/login'
              throw new Error('Authentication failed. Please log in again.')
            }
          } catch (refreshError) {
            console.error('❌ Session refresh failed:', refreshError)
            // Only logout if refresh completely fails
            localStorage.removeItem('authToken')
            localStorage.removeItem('token')
            localStorage.removeItem('access_token')
            window.location.href = '/login'
            throw new Error('Authentication failed. Please log in again.')
          }
        }
        
        throw new Error(error.detail || `HTTP ${response.status}`)
      }

      return response.json()
    } catch (error) {
      console.error('Blog service fetch error:', error)
      // Don't redirect on network errors or other non-auth errors
      if (error.message?.includes('Authentication') || error.message?.includes('401')) {
        throw error // Already handled above
      }
      throw error
    }
  }

  // Blog Posts
  async getBlogs(params = {}) {
    const queryParams = new URLSearchParams()
    
    if (params.status) queryParams.append('status', params.status)
    if (params.site_id) queryParams.append('site_id', params.site_id)
    if (params.limit) queryParams.append('limit', params.limit)
    if (params.offset) queryParams.append('offset', params.offset)
    
    const queryString = queryParams.toString()
    const endpoint = `/api/blogs${queryString ? `?${queryString}` : ''}`
    
    return this.makeRequest(endpoint)
  }

  async getBlog(blogId) {
    return this.makeRequest(`/api/blogs/${blogId}`)
  }

  async getBlogBySlug(slug) {
    // Public endpoint - no auth required
    // Use query parameter to avoid issues with special characters in path
    const encodedSlug = encodeURIComponent(slug);
    return this.makeRequest(`/api/blogs/public/by-slug?slug=${encodedSlug}`, {}, false)
  }

  async createBlog(blogData) {
    // Public endpoint - no auth required
    return this.makeRequest('/api/blogs', {
      method: 'POST',
      body: JSON.stringify(blogData)
    }, false) // requireAuth = false
  }

  async getPublicBlogs(params = {}) {
    const queryParams = new URLSearchParams()
    
    if (params.status) queryParams.append('status', params.status)
    if (params.limit) queryParams.append('limit', params.limit)
    if (params.offset) queryParams.append('offset', params.offset)
    
    const queryString = queryParams.toString()
    const endpoint = `/api/blogs/public${queryString ? `?${queryString}` : ''}`
    
    // Public endpoint - no auth required
    return this.makeRequest(endpoint, {}, false)
  }

  async getAllBlogs(params = {}) {
    // Get all blogs (published and draft) for admin page
    const queryParams = new URLSearchParams()
    
    if (params.limit) queryParams.append('limit', params.limit)
    if (params.offset) queryParams.append('offset', params.offset)
    
    const queryString = queryParams.toString()
    const endpoint = `/api/blogs/public/all${queryString ? `?${queryString}` : ''}`
    
    // Public endpoint - no auth required
    return this.makeRequest(endpoint, {}, false)
  }

  async generateBlogs() {
    return this.makeRequest('/api/blogs/generate', {
      method: 'POST'
    })
  }

  async updateBlog(blogId, blogData) {
    return this.makeRequest(`/api/blogs/${blogId}`, {
      method: 'PUT',
      body: JSON.stringify(blogData)
    })
  }

  async updateBlogPublic(blogId, blogData) {
    // Public endpoint for admin page
    return this.makeRequest(`/api/blogs/public/${blogId}`, {
      method: 'PUT',
      body: JSON.stringify(blogData)
    }, false)
  }

  async deleteBlog(blogId) {
    return this.makeRequest(`/api/blogs/${blogId}`, {
      method: 'DELETE'
    })
  }

  async deleteBlogPublic(blogId) {
    // Public endpoint for admin page
    return this.makeRequest(`/api/blogs/public/${blogId}`, {
      method: 'DELETE'
    }, false)
  }

  async publishBlog(blogId) {
    return this.makeRequest(`/api/blogs/${blogId}/publish`, {
      method: 'POST'
    })
  }

  async generateBlogImage(blogId) {
    // Public endpoint for admin page
    return this.makeRequest(`/api/blogs/public/${blogId}/generate-image`, {
      method: 'POST'
    }, false)
  }

  async generateTagsCategories(content, title = null) {
    return this.makeRequest('/api/blogs/generate-tags-categories', {
      method: 'POST',
      body: JSON.stringify({ content, title })
    })
  }

  async checkTagsCategoriesRelevance(content, title = null, existingCategories = [], existingTags = []) {
    return this.makeRequest('/api/blogs/check-tags-categories-relevance', {
      method: 'POST',
      body: JSON.stringify({ 
        content, 
        title,
        existing_categories: existingCategories,
        existing_tags: existingTags
      })
    })
  }

  async generateFromTitle(title, existingContent = null, existingExcerpt = null) {
    return this.makeRequest('/api/blogs/generate-from-title', {
      method: 'POST',
      body: JSON.stringify({ 
        title,
        existing_content: existingContent,
        existing_excerpt: existingExcerpt
      })
    })
  }

  // Blog Statistics
  async getBlogStats() {
    return this.makeRequest('/api/blogs/stats/')
  }

  // WordPress Sites (for blog creation)
  async getWordPressSites() {
    return this.makeRequest('/connections/platform/?platform=wordpress')
  }
}

export const blogService = new BlogService()
