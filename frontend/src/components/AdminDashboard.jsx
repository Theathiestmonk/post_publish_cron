import React, { useState, useEffect, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useNotifications } from '../contexts/NotificationContext'
import { adminAPI } from '../services/admin'
import SideNavbar from './SideNavbar'
import MobileNavigation from './MobileNavigation'
import LoadingBar from './LoadingBar'
import { 
  DollarSign, 
  Database, 
  Users, 
  TrendingUp, 
  Filter, 
  Download, 
  RefreshCw,
  Calendar,
  Search,
  X,
  ChevronDown,
  Play
} from 'lucide-react'

const AdminDashboard = () => {
  const { user } = useAuth()
  const { showError, showSuccess } = useNotifications()

  // State
  const [loading, setLoading] = useState(true)
  const [isAdmin, setIsAdmin] = useState(false)
  const [adminChecked, setAdminChecked] = useState(false)
  const [tokenUsage, setTokenUsage] = useState([])
  const [stats, setStats] = useState(null)
  const [usersList, setUsersList] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(50)
  const [runEmbeddingLoading, setRunEmbeddingLoading] = useState(false)
  
  // Calculate default dates (last 7 days)
  const getDefaultDates = () => {
    const today = new Date()
    const sevenDaysAgo = new Date()
    sevenDaysAgo.setDate(today.getDate() - 7)
    
    return {
      start_date: sevenDaysAgo.toISOString().split('T')[0], // YYYY-MM-DD
      end_date: today.toISOString().split('T')[0] // YYYY-MM-DD
    }
  }

  // Filters
  const [filters, setFilters] = useState(() => {
    const defaultDates = getDefaultDates()
    return {
      user_id: [],
      feature_type: [],
      model_name: [],
      start_date: defaultDates.start_date,
      end_date: defaultDates.end_date
    }
  })
  const [showFilters, setShowFilters] = useState(false)
  const [openDropdowns, setOpenDropdowns] = useState({
    user: false,
    feature: false,
    model: false,
    download: false
  })
  const dropdownRefs = {
    user: useRef(null),
    feature: useRef(null),
    model: useRef(null),
    download: useRef(null)
  }
  
  // Available options for filters
  const [availableUsers, setAvailableUsers] = useState([])
  const [availableFeatureTypes, setAvailableFeatureTypes] = useState([])
  const [availableModels, setAvailableModels] = useState([])

  // Check admin status and load data only when user is authenticated and is admin
  useEffect(() => {
    if (user) {
      checkAdminAccess()
    }
  }, [user])

  // Fetch data when filters change (only if user is admin)
  useEffect(() => {
    if (user && isAdmin) {
      fetchData()
      fetchStats()
      fetchUsers()
    }
  }, [page, pageSize, filters, isAdmin])

  // Fetch all available options for filters (only once on mount if admin)
  useEffect(() => {
    if (user && isAdmin) {
      fetchAllOptions()
    }
  }, [user, isAdmin])

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      Object.keys(dropdownRefs).forEach(key => {
        if (dropdownRefs[key].current && !dropdownRefs[key].current.contains(event.target)) {
          setOpenDropdowns(prev => ({ ...prev, [key]: false }))
        }
      })
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  const checkAdminAccess = async () => {
    try {
      setLoading(true)
      const response = await adminAPI.checkAdminStatus()
      const adminStatus = response.data?.is_admin || false
      setIsAdmin(adminStatus)
      setAdminChecked(true)

      if (!adminStatus) {
        showError('Admin access required. You do not have permission to view this dashboard.')
      }
    } catch (error) {
      console.error('Error checking admin status:', error)
      showError('Failed to verify admin access')
      setIsAdmin(false)
      setAdminChecked(true)
    } finally {
      setLoading(false)
    }
  }

  const fetchData = async () => {
    if (!isAdmin) return

    try {
      setLoading(true)
      const result = await adminAPI.getTokenUsage({
        userId: filters.user_id.length > 0 ? filters.user_id : null,
        featureType: filters.feature_type.length > 0 ? filters.feature_type : null,
        modelName: filters.model_name.length > 0 ? filters.model_name : null,
        startDate: filters.start_date || null,
        endDate: filters.end_date || null,
        limit: pageSize,
        offset: (page - 1) * pageSize
      })
      
      if (result.error) {
        showError(result.error)
        return
      }
      
      // API returns array directly
      const data = Array.isArray(result) ? result : []
      setTokenUsage(data)
      // Note: Total count should come from backend with count query
      // For now, we'll use the length, but ideally backend should return total count
      setTotal(data.length)
    } catch (error) {
      showError('Failed to load token usage data')
      console.error('Error fetching token usage:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchStats = async () => {
    if (!isAdmin) return

    try {
      const result = await adminAPI.getTokenUsageStats(
        filters.start_date || null,
        filters.end_date || null,
        filters.user_id.length > 0 ? filters.user_id : null,
        filters.feature_type.length > 0 ? filters.feature_type : null,
        filters.model_name.length > 0 ? filters.model_name : null
      )
      
      if (result.error) {
        console.error('Error fetching stats:', result.error)
        return
      }
      
      setStats(result)
    } catch (error) {
      console.error('Error fetching stats:', error)
    }
  }

  const fetchUsers = async () => {
    if (!isAdmin) return

    try {
      const result = await adminAPI.getUsers(
        filters.start_date || null,
        filters.end_date || null
      )
      
      if (result.error) {
        console.error('Error fetching users:', result.error)
        return
      }
      
      // API returns array directly
      const users = Array.isArray(result) ? result : []
      setAvailableUsers(users)
      setUsersList(users)
    } catch (error) {
      console.error('Error fetching users:', error)
    }
  }

  const fetchAllOptions = async () => {
    if (!isAdmin) return

    try {
      // Fetch all data without filters to get all available options
      const result = await adminAPI.getTokenUsage({
        userId: null,
        featureType: null,
        modelName: null,
        startDate: null,
        endDate: null,
        limit: 1000, // Get a large sample to extract unique values
        offset: 0
      })
      
      if (result.error) {
        console.error('Error fetching options:', result.error)
        return
      }
      
      const data = Array.isArray(result) ? result : []
      
      // Extract unique values for filter options
      const featureTypes = [...new Set(data.map(item => item.feature_type).filter(Boolean))]
      const models = [...new Set(data.map(item => item.model_name).filter(Boolean))]
      
      setAvailableFeatureTypes(featureTypes.sort())
      setAvailableModels(models.sort())
    } catch (error) {
      console.error('Error fetching filter options:', error)
    }
  }

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }))
    setPage(1) // Reset to first page when filter changes
  }

  const handleMultiSelectChange = (key, value, checked) => {
    setFilters(prev => ({
      ...prev,
      [key]: checked
        ? [...prev[key], value]
        : prev[key].filter(item => item !== value)
    }))
    setPage(1) // Reset to first page when filter changes
  }

  const clearFilters = () => {
    const defaultDates = getDefaultDates()
    setFilters({
      user_id: [],
      feature_type: [],
      model_name: [],
      start_date: defaultDates.start_date,
      end_date: defaultDates.end_date
    })
    setPage(1)
  }

  const toggleDropdown = (dropdown) => {
    setOpenDropdowns(prev => ({
      ...prev,
      [dropdown]: !prev[dropdown]
    }))
  }

  const removeFilter = (key, value) => {
    setFilters(prev => ({
      ...prev,
      [key]: prev[key].filter(item => item !== value)
    }))
    setPage(1)
  }

  const handleExport = async (format) => {
    try {
      const exportFilters = {
        userId: filters.user_id.length > 0 ? filters.user_id : null,
        featureType: filters.feature_type.length > 0 ? filters.feature_type : null,
        modelName: filters.model_name.length > 0 ? filters.model_name : null,
        startDate: filters.start_date || null,
        endDate: filters.end_date || null
      }
      const result = await adminAPI.exportTokenUsage(format, exportFilters)
      if (result.error) {
        showError(result.error)
      } else {
        showSuccess(`Data exported successfully as ${format.toUpperCase()}`)
      }
    } catch (error) {
      showError('Failed to export data')
      console.error('Export error:', error)
    }
  }

  const handleRunFaqEmbeddings = async () => {
    try {
      setRunEmbeddingLoading(true)
      const result = await adminAPI.runFaqEmbeddings()
      const processed = result?.processed ?? 0
      showSuccess(`FAQ embeddings processed: ${processed}`)
    } catch (error) {
      console.error('Failed to run FAQ embeddings:', error)
      showError('Failed to run FAQ embeddings')
    } finally {
      setRunEmbeddingLoading(false)
    }
  }

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 6,
      maximumFractionDigits: 6
    }).format(amount)
  }

  const formatNumber = (num) => {
    return new Intl.NumberFormat('en-US').format(num)
  }

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const totalPages = Math.ceil(total / pageSize)

  // Redirect if not logged in
  if (!user) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Please log in to access the admin dashboard</h2>
          <p className="text-gray-600">You need to be logged in with admin privileges to view this page.</p>
        </div>
      </div>
    )
  }

  // Show loading while checking admin status
  if (!adminChecked) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Verifying Admin Access</h2>
          <p className="text-gray-600">Please wait while we verify your admin privileges...</p>
        </div>
      </div>
    )
  }

  // Show access denied if not admin
  if (!isAdmin) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Access Denied</h2>
          <p className="text-gray-600">You do not have admin privileges to access this dashboard.</p>
          <p className="text-sm text-gray-500 mt-2">Contact your administrator if you believe this is an error.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <SideNavbar />
      <MobileNavigation />
      
      <div className="lg:ml-64 p-4 sm:p-6 lg:p-8">
        <div className="max-w-7xl mx-auto">
          {/* Header */}
          <div className="mb-6">
            <h1 className="text-3xl font-bold text-gray-900 mb-2">Admin Dashboard</h1>
            <p className="text-gray-600">Monitor token usage and costs across all users</p>
          </div>

          {/* Stats Cards */}
          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Total Cost</p>
                    <p className="text-2xl font-bold text-gray-900">{formatCurrency(stats.total_cost)}</p>
                  </div>
                  <DollarSign className="w-8 h-8 text-green-500" />
                </div>
              </div>
              
              <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Total Tokens</p>
                    <p className="text-2xl font-bold text-gray-900">{formatNumber(stats.total_tokens)}</p>
                  </div>
                  <Database className="w-8 h-8 text-blue-500" />
                </div>
              </div>
              
              <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Total Requests</p>
                    <p className="text-2xl font-bold text-gray-900">{formatNumber(stats.total_requests)}</p>
                  </div>
                  <TrendingUp className="w-8 h-8 text-purple-500" />
                </div>
              </div>
              
              <div className="bg-white rounded-lg shadow p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Active Users</p>
                    <p className="text-2xl font-bold text-gray-900">
                      {stats.by_user && stats.by_user.length > 0
                        ? formatNumber(stats.by_user.length)
                        : formatNumber(0)}
                    </p>
                  </div>
                  <Users className="w-8 h-8 text-pink-500" />
                </div>
              </div>
            </div>
          )}

          {/* Filters and Actions */}
          <div className="bg-white rounded-lg shadow mb-6 p-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowFilters(!showFilters)}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors"
                >
                  <Filter className="w-4 h-4" />
                  Filters
                </button>
                
                {(filters.user_id.length > 0 || filters.feature_type.length > 0 || filters.model_name.length > 0 || filters.start_date || filters.end_date) && (
                  <button
                    onClick={clearFilters}
                    className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-900 transition-colors"
                  >
                    <X className="w-4 h-4" />
                    Clear
                  </button>
                )}
              </div>
              
              <div className="flex items-center gap-2">
                <button
                  onClick={fetchData}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-500 hover:bg-blue-600 text-white rounded-lg transition-colors"
                >
                  <RefreshCw className="w-4 h-4" />
                  Refresh
                </button>
                <button
                  onClick={handleRunFaqEmbeddings}
                  disabled={runEmbeddingLoading}
                  className="flex items-center gap-2 px-4 py-2 bg-purple-500 hover:bg-purple-600 text-white rounded-lg transition-colors text-sm"
                >
                  <Play className="w-4 h-4" />
                  {runEmbeddingLoading ? 'Running FAQ embeddings...' : 'Run FAQ embeddings'}
                </button>
                
                {/* Unified Download Dropdown */}
                <div className="relative" ref={dropdownRefs.download}>
                  <button
                    onClick={() => toggleDropdown('download')}
                    className="flex items-center gap-2 px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg transition-colors text-sm"
                  >
                    <Download className="w-4 h-4" />
                    Download
                    <ChevronDown className="w-4 h-4" />
                  </button>
                  {openDropdowns.download && (
                    <div className="absolute right-0 mt-2 w-48 bg-white border border-gray-300 rounded-lg shadow-lg z-20">
                      <div className="py-1">
                        <button
                          onClick={() => {
                            handleExport('csv')
                            setOpenDropdowns(prev => ({ ...prev, download: false }))
                          }}
                          className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                        >
                          <Download className="w-4 h-4" />
                          Download as CSV
                        </button>
                        <button
                          onClick={() => {
                            handleExport('json')
                            setOpenDropdowns(prev => ({ ...prev, download: false }))
                          }}
                          className="w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                        >
                          <Download className="w-4 h-4" />
                          Download as JSON
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Filter Panel */}
            {showFilters && (
              <div className="mt-4 space-y-4 pt-4 border-t">
                {/* Selected Filters Display */}
                {(filters.user_id.length > 0 || filters.feature_type.length > 0 || filters.model_name.length > 0) && (
                  <div className="flex flex-wrap gap-2">
                    {filters.user_id.map(userId => {
                      const user = availableUsers.find(u => u.user_id === userId)
                      return (
                        <span
                          key={`user-${userId}`}
                          className="inline-flex items-center gap-1 px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs"
                        >
                          User: {user?.name || user?.email || userId}
                          <button
                            onClick={() => removeFilter('user_id', userId)}
                            className="hover:text-blue-900"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </span>
                      )
                    })}
                    {filters.feature_type.map(feature => (
                      <span
                        key={`feature-${feature}`}
                        className="inline-flex items-center gap-1 px-2 py-1 bg-purple-100 text-purple-800 rounded-full text-xs"
                      >
                        Feature: {feature}
                        <button
                          onClick={() => removeFilter('feature_type', feature)}
                          className="hover:text-purple-900"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                    {filters.model_name.map(model => (
                      <span
                        key={`model-${model}`}
                        className="inline-flex items-center gap-1 px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs"
                      >
                        Model: {model}
                        <button
                          onClick={() => removeFilter('model_name', model)}
                          className="hover:text-green-900"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
                  {/* User Multi-Select */}
                  <div className="relative" ref={dropdownRefs.user}>
                    <label className="block text-sm font-medium text-gray-700 mb-1">User</label>
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => toggleDropdown('user')}
                        className="w-full px-3 py-2 text-left border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent bg-white flex items-center justify-between"
                      >
                        <span className="text-gray-700">
                          {filters.user_id.length === 0
                            ? 'All Users'
                            : `${filters.user_id.length} selected`}
                        </span>
                        <Search className="w-4 h-4 text-gray-400" />
                      </button>
                      {openDropdowns.user && (
                        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                          <div className="p-2">
                            {availableUsers.map(u => (
                              <label
                                key={u.user_id}
                                className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer"
                              >
                                <input
                                  type="checkbox"
                                  checked={filters.user_id.includes(u.user_id)}
                                  onChange={(e) => handleMultiSelectChange('user_id', u.user_id, e.target.checked)}
                                  className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                                />
                                <span className="ml-2 text-sm text-gray-700">
                                  {u.name || u.email} ({formatCurrency(u.total_cost)})
                                </span>
                              </label>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Feature Type Multi-Select */}
                  <div className="relative" ref={dropdownRefs.feature}>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Feature Type</label>
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => toggleDropdown('feature')}
                        className="w-full px-3 py-2 text-left border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent bg-white flex items-center justify-between"
                      >
                        <span className="text-gray-700">
                          {filters.feature_type.length === 0
                            ? 'All Features'
                            : `${filters.feature_type.length} selected`}
                        </span>
                        <Search className="w-4 h-4 text-gray-400" />
                      </button>
                      {openDropdowns.feature && (
                        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                          <div className="p-2">
                            {availableFeatureTypes.map(ft => (
                              <label
                                key={ft}
                                className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer"
                              >
                                <input
                                  type="checkbox"
                                  checked={filters.feature_type.includes(ft)}
                                  onChange={(e) => handleMultiSelectChange('feature_type', ft, e.target.checked)}
                                  className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                                />
                                <span className="ml-2 text-sm text-gray-700">{ft}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Model Multi-Select */}
                  <div className="relative" ref={dropdownRefs.model}>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Model</label>
                    <div className="relative">
                      <button
                        type="button"
                        onClick={() => toggleDropdown('model')}
                        className="w-full px-3 py-2 text-left border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent bg-white flex items-center justify-between"
                      >
                        <span className="text-gray-700">
                          {filters.model_name.length === 0
                            ? 'All Models'
                            : `${filters.model_name.length} selected`}
                        </span>
                        <Search className="w-4 h-4 text-gray-400" />
                      </button>
                      {openDropdowns.model && (
                        <div className="absolute z-10 w-full mt-1 bg-white border border-gray-300 rounded-lg shadow-lg max-h-60 overflow-y-auto">
                          <div className="p-2">
                            {availableModels.map(m => (
                              <label
                                key={m}
                                className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer"
                              >
                                <input
                                  type="checkbox"
                                  checked={filters.model_name.includes(m)}
                                  onChange={(e) => handleMultiSelectChange('model_name', m, e.target.checked)}
                                  className="w-4 h-4 text-purple-600 border-gray-300 rounded focus:ring-purple-500"
                                />
                                <span className="ml-2 text-sm text-gray-700">{m}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Start Date</label>
                    <input
                      type="date"
                      value={filters.start_date}
                      onChange={(e) => handleFilterChange('start_date', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    />
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">End Date</label>
                    <input
                      type="date"
                      value={filters.end_date}
                      onChange={(e) => handleFilterChange('end_date', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Data Table */}
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Feature</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Model</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Input Tokens</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Output Tokens</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Total Tokens</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Cost</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {loading ? (
                    <tr>
                      <td colSpan="8" className="px-6 py-8 text-center">
                        <LoadingBar />
                      </td>
                    </tr>
                  ) : tokenUsage.length === 0 ? (
                    <tr>
                      <td colSpan="8" className="px-6 py-8 text-center text-gray-500">
                        No token usage data found
                      </td>
                    </tr>
                  ) : (
                    tokenUsage.map((usage) => {
                      // Get user info from usersList
                      const userInfo = usersList.find(u => u.user_id === usage.user_id) || {}
                      return (
                        <tr key={usage.id} className="hover:bg-gray-50">
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="text-sm font-medium text-gray-900">{userInfo.name || userInfo.email || usage.user_id}</div>
                            <div className="text-sm text-gray-500">{userInfo.email || ''}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className="px-2 py-1 text-xs font-medium bg-purple-100 text-purple-800 rounded-full">
                              {usage.feature_type}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{usage.model_name}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 text-right">{formatNumber(usage.input_tokens)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 text-right">{formatNumber(usage.output_tokens)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 text-right">{formatNumber(usage.total_tokens)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-green-600 text-right">{formatCurrency(usage.total_cost)}</td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{formatDate(usage.created_at)}</td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="bg-gray-50 px-6 py-4 flex items-center justify-between border-t border-gray-200">
                <div className="text-sm text-gray-700">
                  Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, total)} of {formatNumber(total)} results
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                  >
                    Previous
                  </button>
                  <span className="px-4 py-2 text-sm text-gray-700">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                    className="px-4 py-2 border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default AdminDashboard

