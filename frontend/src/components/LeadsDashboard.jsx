import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { useNotifications } from '../contexts/NotificationContext'
import { leadsAPI } from '../services/leads'
import SideNavbar from './SideNavbar'
import MobileNavigation from './MobileNavigation'
import LeadCard from './LeadCard'
import LeadDetailModal from './LeadDetailModal'
import AddLeadModal from './AddLeadModal'

// Dark mode hook
const useDarkMode = () => {
  const [isDarkMode, setIsDarkMode] = useState(() => {
    // Check localStorage for saved preference, default to light mode
    return localStorage.getItem('darkMode') === 'true'
  })

  useEffect(() => {
    localStorage.setItem('darkMode', isDarkMode.toString())
    // Apply to document for global dark mode
    if (isDarkMode) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }, [isDarkMode])

  // Listen for dark mode changes from navbar
  useEffect(() => {
    const handleStorageChange = (event) => {
      if (event.detail && event.detail.key === 'darkMode') {
        const newValue = event.detail.value === 'true'
        setIsDarkMode(newValue)
      }
    }

    // Also listen for direct localStorage changes (for cross-tab sync)
    const handleLocalStorageChange = (e) => {
      if (e.key === 'darkMode') {
        const newValue = e.newValue === 'true'
        setIsDarkMode(newValue)
      }
    }

    window.addEventListener('localStorageChange', handleStorageChange)
    window.addEventListener('storage', handleLocalStorageChange)

    return () => {
      window.removeEventListener('localStorageChange', handleStorageChange)
      window.removeEventListener('storage', handleLocalStorageChange)
    }
  }, [])

  return [isDarkMode, setIsDarkMode]
}
import {
  Users,
  UserPlus,
  CheckCircle,
  MessageCircle,
  TrendingUp,
  Search,
  Filter,
  RefreshCw,
  Loader2,
  XCircle,
  AlertCircle,
  Facebook,
  Instagram,
  X,
  CalendarDays
} from 'lucide-react'

// Get date range for filtering (moved outside component to prevent recreation)
const getDateRange = (range) => {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())

  switch (range) {
    case 'today':
      return {
        start: today,
        end: new Date(today.getTime() + 24 * 60 * 60 * 1000 - 1)
      }
    case 'this_week': {
      const dayOfWeek = now.getDay()
      const startOfWeek = new Date(today)
      startOfWeek.setDate(today.getDate() - dayOfWeek)
      return {
        start: startOfWeek,
        end: new Date(today.getTime() + 24 * 60 * 60 * 1000 - 1)
      }
    }
    case 'this_month': {
      const startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1)
      return {
        start: startOfMonth,
        end: new Date(today.getTime() + 24 * 60 * 60 * 1000 - 1)
      }
    }
    case 'last_month': {
      const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1)
      const endOfLastMonth = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59, 999)
      return {
        start: lastMonth,
        end: endOfLastMonth
      }
    }
    default:
      return null
  }
}

const LeadsDashboard = () => {
  const { user } = useAuth()
  const { showSuccess, showError, showInfo } = useNotifications()
  const [isDarkMode, setIsDarkMode] = useDarkMode()
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedLead, setSelectedLead] = useState(null)
  const [showDetailModal, setShowDetailModal] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
  const [importingCSV, setImportingCSV] = useState(false)
  const [filterStatus, setFilterStatus] = useState('all')
  const [filterPlatform, setFilterPlatform] = useState('all')
  const [filterDateRange, setFilterDateRange] = useState('today')
  const [customStartDate, setCustomStartDate] = useState('')
  const [customEndDate, setCustomEndDate] = useState('')
  const [showCustomDatePicker, setShowCustomDatePicker] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [showFilterDropdown, setShowFilterDropdown] = useState(false)
  const [lastFetchTime, setLastFetchTime] = useState(null)
  const [pollingInterval, setPollingInterval] = useState(null)
  const [selectionMode, setSelectionMode] = useState(false)
  const [selectedLeadIds, setSelectedLeadIds] = useState(new Set())
  const [deletingBulk, setDeletingBulk] = useState(false)
  const leadsRef = useRef([])
  const lastFetchTimeRef = useRef(null)

  const fetchLeads = useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setLoading(true)

      const params = {}
      if (filterStatus !== 'all') {
        params.status = filterStatus
      }
      if (filterPlatform !== 'all') {
        params.source_platform = filterPlatform
      }
      params.limit = 100
      params.offset = 0

      const response = await leadsAPI.getLeads(params)
      const fetchedLeads = response.data || []

      // Check for new leads using refs to avoid dependency issues
      const previousLeads = leadsRef.current
      const previousFetchTime = lastFetchTimeRef.current

      if (previousFetchTime && previousLeads.length > 0) {
        const newLeads = fetchedLeads.filter(newLead => {
          const newLeadTime = new Date(newLead.created_at)
          return newLeadTime > previousFetchTime && !previousLeads.find(l => l.id === newLead.id)
        })

        if (newLeads.length > 0) {
          showInfo(
            'New Lead!',
            `${newLeads.length} new lead${newLeads.length > 1 ? 's' : ''} received`,
            {
              type: 'lead',
              leadIds: newLeads.map(l => l.id)
            }
          )
        }
      }

      // Update state and refs
      setLeads(fetchedLeads)
      leadsRef.current = fetchedLeads
      const now = new Date()
      setLastFetchTime(now)
      lastFetchTimeRef.current = now

    } catch (error) {
      console.error('Error fetching leads:', error)
      showError('Error', 'Failed to fetch leads. Please try again.')
    } finally {
      if (showLoading) setLoading(false)
    }
  }, [filterStatus, filterPlatform, showError, showInfo])

  // Clear leads data on logout
  useEffect(() => {
    if (!user) {
      setLeads([])
      setLastFetchTime(null)
      setSelectedLead(null)
      setShowDetailModal(false)
      setSelectedLeadIds(new Set())
      setSelectionMode(false)
    }
  }, [user])

  // Clear polling interval on logout
  useEffect(() => {
    if (!user && pollingInterval) {
      clearInterval(pollingInterval)
      setPollingInterval(null)
    }
  }, [user, pollingInterval])

  // Initial fetch and refetch when filters change
  useEffect(() => {
    if (user) {
      fetchLeads()
    }
  }, [user, filterStatus, filterPlatform, fetchLeads])

  // Handle leadId from URL query parameter (for opening lead from chatbot link)
  useEffect(() => {
    if (!user || !leads.length) return

    const urlParams = new URLSearchParams(window.location.search)
    const leadId = urlParams.get('leadId')

    if (leadId) {
      // Find the lead in the leads list
      const lead = leads.find(l => l.id === leadId)
      if (lead) {
        setSelectedLead(lead)
        setShowDetailModal(true)
        // Remove leadId from URL to prevent reopening on refresh
        const newUrl = window.location.pathname + window.location.search.replace(/[?&]leadId=[^&]*/, '').replace(/^\?/, '?').replace(/\?$/, '')
        window.history.replaceState({}, '', newUrl || window.location.pathname)
      }
    }
  }, [user, leads])

  // Close filter dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (showFilterDropdown && !event.target.closest('.filter-dropdown-container')) {
        setShowFilterDropdown(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [showFilterDropdown])

  // Set up polling for new leads
  useEffect(() => {
    if (!user) return

    const interval = setInterval(() => {
      fetchLeads(false) // Don't show loading spinner for polling
    }, 30000) // Poll every 30 seconds

    setPollingInterval(interval)

    return () => {
      clearInterval(interval)
    }
  }, [user, fetchLeads])

  const handleLeadClick = (lead) => {
    setSelectedLead(lead)
    setShowDetailModal(true)
  }

  const handleDeleteLead = async (lead) => {
    if (!window.confirm(`Are you sure you want to delete "${lead.name || 'this lead'}"? This action cannot be undone.`)) {
      return
    }

    try {
      await leadsAPI.deleteLead(lead.id)
      showSuccess('Lead Deleted', 'Lead has been deleted successfully')
      // Refresh leads list
      await fetchLeads(false)
      // Close modal if the deleted lead was selected
      if (selectedLead && selectedLead.id === lead.id) {
        setShowDetailModal(false)
        setSelectedLead(null)
      }
      // Remove from selection if in selection mode
      if (selectionMode) {
        setSelectedLeadIds(prev => {
          const newSet = new Set(prev)
          newSet.delete(lead.id)
          return newSet
        })
      }
    } catch (error) {
      console.error('Error deleting lead:', error)
      showError('Error', 'Failed to delete lead')
    }
  }

  const handleToggleSelectionMode = () => {
    setSelectionMode(!selectionMode)
    if (selectionMode) {
      setSelectedLeadIds(new Set())
    }
  }

  const handleSelectLead = (leadId, isSelected) => {
    setSelectedLeadIds(prev => {
      const newSet = new Set(prev)
      if (isSelected) {
        newSet.add(leadId)
      } else {
        newSet.delete(leadId)
      }
      return newSet
    })
  }

  const handleSelectAll = () => {
    if (selectedLeadIds.size === filteredLeads.length) {
      setSelectedLeadIds(new Set())
    } else {
      setSelectedLeadIds(new Set(filteredLeads.map(lead => lead.id)))
    }
  }

  const handleBulkDelete = async () => {
    if (selectedLeadIds.size === 0) {
      showError('Error', 'No leads selected')
      return
    }

    if (!window.confirm(`Are you sure you want to delete ${selectedLeadIds.size} lead(s)? This action cannot be undone.`)) {
      return
    }

    try {
      setDeletingBulk(true)
      const leadIdsArray = Array.from(selectedLeadIds)
      const result = await leadsAPI.bulkDeleteLeads(leadIdsArray)

      if (result.data.success) {
        showSuccess(
          'Leads Deleted',
          `Successfully deleted ${result.data.success_count} lead(s)${result.data.failed_count > 0 ? `. ${result.data.failed_count} failed.` : ''}`
        )
        // Refresh leads list
        await fetchLeads(false)
        // Clear selection
        setSelectedLeadIds(new Set())
        // Exit selection mode if all selected leads are deleted
        if (result.data.failed_count === 0) {
          setSelectionMode(false)
        }
      } else {
        showError('Error', 'Failed to delete some leads')
      }
    } catch (error) {
      console.error('Error bulk deleting leads:', error)
      showError('Error', 'Failed to delete leads')
    } finally {
      setDeletingBulk(false)
    }
  }

  const handleCSVImport = async (file) => {
    if (!file) {
      showError('Error', 'Please select a CSV file')
      return
    }

    if (!file.name.endsWith('.csv')) {
      showError('Error', 'Please select a valid CSV file')
      return
    }

    try {
      setImportingCSV(true)
      const response = await leadsAPI.importLeadsCSV(file)
      const result = response.data || response

      if (result.success) {
        const hasErrors = result.errors > 0
        const hasDuplicates = result.duplicates > 0

        if (hasErrors && hasDuplicates) {
          showInfo(
            'Import Completed with Warnings',
            `Successfully imported ${result.created} out of ${result.total_rows} leads. ${result.duplicates} duplicate(s) skipped, ${result.errors} error(s) occurred.`,
            { duration: 6000 }
          )
          if (result.error_details && result.error_details.length > 0) {
            console.warn('Import errors:', result.error_details)
          }
          if (result.duplicate_details && result.duplicate_details.length > 0) {
            console.warn('Duplicate leads:', result.duplicate_details)
          }
        } else if (hasDuplicates) {
          showInfo(
            'Import Completed',
            `Successfully imported ${result.created} out of ${result.total_rows} leads. ${result.duplicates} duplicate(s) skipped.`,
            { duration: 5000 }
          )
          if (result.duplicate_details && result.duplicate_details.length > 0) {
            console.warn('Duplicate leads:', result.duplicate_details)
          }
        } else if (hasErrors) {
          showInfo(
            'Import Completed with Errors',
            `Successfully imported ${result.created} out of ${result.total_rows} leads. ${result.errors} error(s) occurred.`,
            { duration: 5000 }
          )
          if (result.error_details && result.error_details.length > 0) {
            console.warn('Import errors:', result.error_details)
          }
        } else {
          showSuccess('Import Successful', `Successfully imported ${result.created} leads`)
        }

        // Refresh leads list
        await fetchLeads(false)
      } else {
        showError('Import Failed', result.message || 'Failed to import leads')
      }
    } catch (error) {
      console.error('Error importing CSV:', error)
      const errorMessage = error.response?.data?.detail || error.message || 'Failed to import CSV file'
      showError('Import Failed', errorMessage)
    } finally {
      setImportingCSV(false)
    }
  }

  const handleCloseModal = () => {
    setShowDetailModal(false)
    setSelectedLead(null)
    // Refresh leads after modal closes in case status was updated
    fetchLeads(false)
  }

  const handleRefresh = () => {
    fetchLeads()
    showSuccess('Refreshed', 'Leads list updated')
  }

  const filteredLeads = useMemo(() => {
    return leads.filter(lead => {
      // Status filter
      if (filterStatus !== 'all' && lead.status !== filterStatus) {
        return false
      }

      // Date range filter
      if (filterDateRange !== 'all') {
        let dateRange = null

        if (filterDateRange === 'custom' && customStartDate && customEndDate) {
          // Use custom date range
          dateRange = {
            start: new Date(customStartDate + 'T00:00:00'),
            end: new Date(customEndDate + 'T23:59:59')
          }
        } else {
          // Use predefined date range
          dateRange = getDateRange(filterDateRange)
        }

        if (dateRange) {
          const leadDate = new Date(lead.created_at)
          if (leadDate < dateRange.start || leadDate > dateRange.end) {
            return false
          }
        }
      }

      // Search query filter
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        const matchesName = lead.name?.toLowerCase().includes(query)
        const matchesEmail = lead.email?.toLowerCase().includes(query)
        const matchesPhone = lead.phone_number?.toLowerCase().includes(query)
        if (!matchesName && !matchesEmail && !matchesPhone) {
          return false
        }
      }

      return true
    })
  }, [leads, filterStatus, filterDateRange, customStartDate, customEndDate, searchQuery])

  const dateRangeFilters = [
    { value: 'today', label: 'Today' },
    { value: 'this_week', label: 'This Week' },
    { value: 'this_month', label: 'This Month' },
    { value: 'last_month', label: 'Last Month' },
    { value: 'all', label: 'All Time' },
    { value: 'custom', label: 'Custom Range' }
  ]

  const statusFilters = [
    { value: 'new', label: 'New' },
    { value: 'contacted', label: 'Contacted' },
    { value: 'responded', label: 'Responded' },
    { value: 'qualified', label: 'Qualified' },
    { value: 'converted', label: 'Converted' },
    { value: 'lost', label: 'Lost' },
    { value: 'invalid', label: 'Invalid' }
  ]

  const getStatusConfig = (status) => {
    const configs = {
      new: {
        color: 'from-blue-500 to-blue-600',
        bgColor: 'bg-blue-50',
        textColor: isDarkMode ? 'text-blue-400' : 'text-blue-700',
        borderColor: isDarkMode ? 'border-blue-700' : 'border-blue-300',
        icon: AlertCircle,
        label: 'New'
      },
      contacted: {
        color: 'from-purple-500 to-purple-600',
        bgColor: 'bg-purple-50',
        textColor: isDarkMode ? 'text-purple-400' : 'text-purple-700',
        borderColor: isDarkMode ? 'border-purple-700' : 'border-purple-300',
        icon: MessageCircle,
        label: 'Contacted'
      },
      responded: {
        color: 'from-green-500 to-green-600',
        bgColor: 'bg-green-50',
        textColor: isDarkMode ? 'text-green-400' : 'text-green-700',
        borderColor: isDarkMode ? 'border-green-700' : 'border-green-300',
        icon: CheckCircle,
        label: 'Responded'
      },
      qualified: {
        color: 'from-orange-500 to-orange-600',
        bgColor: 'bg-orange-50',
        textColor: isDarkMode ? 'text-orange-400' : 'text-orange-700',
        borderColor: isDarkMode ? 'border-orange-700' : 'border-orange-300',
        icon: CheckCircle,
        label: 'Qualified'
      },
      converted: {
        color: 'from-emerald-500 to-emerald-600',
        bgColor: 'bg-emerald-50',
        textColor: isDarkMode ? 'text-emerald-400' : 'text-emerald-700',
        borderColor: isDarkMode ? 'border-emerald-700' : 'border-emerald-300',
        icon: CheckCircle,
        label: 'Converted'
      },
      lost: {
        color: 'from-gray-400 to-gray-500',
        bgColor: 'bg-gray-50',
        textColor: isDarkMode ? 'text-gray-400' : 'text-gray-700',
        borderColor: isDarkMode ? 'border-gray-600' : 'border-gray-300',
        icon: XCircle,
        label: 'Lost'
      },
      invalid: {
        color: 'from-red-500 to-red-600',
        bgColor: 'bg-red-50',
        textColor: isDarkMode ? 'text-red-400' : 'text-red-700',
        borderColor: isDarkMode ? 'border-red-700' : 'border-red-300',
        icon: XCircle,
        label: 'Invalid'
      }
    }
    return configs[status] || configs.new
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-red-600 mb-4">Not Authenticated</h1>
          <p className="text-gray-600">Please log in to access leads.</p>
        </div>
      </div>
    )
  }

  return (
    <div className={`min-h-screen ${isDarkMode ? 'bg-gray-900' : 'bg-gray-50'}`}>
      <SideNavbar />
      <MobileNavigation
        setShowCustomContentChatbot={() => { }}
        handleGenerateContent={() => { }}
        generating={false}
        fetchingFreshData={false}
      />

      <div className="md:ml-48 xl:ml-64 flex flex-col min-h-screen">
        {/* Header */}
        <div className={`shadow-sm border-b sticky top-0 z-20 ${
          isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white'
        }`}>
          <div className="px-4 lg:px-6 py-3 lg:py-4">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 md:gap-4">
              {/* Date Range Filter */}
              <div className="flex items-center gap-2 overflow-x-auto flex-1">
                {dateRangeFilters.map((filter) => (
                  <button
                    key={filter.value}
                    onClick={() => {
                      setFilterDateRange(filter.value)
                      if (filter.value === 'custom') {
                        setShowCustomDatePicker(true)
                      }
                    }}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap flex-shrink-0 ${filterDateRange === filter.value
                      ? 'bg-gradient-to-r from-green-500 to-emerald-600 text-white shadow-md'
                      : isDarkMode
                      ? 'bg-gray-700 text-gray-200 hover:bg-gray-600 border border-gray-600'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200 border border-gray-200'
                      }`}
                  >
                    {filter.label}
                  </button>
                ))}
              </div>

              {/* Custom Date Picker */}
              {filterDateRange === 'custom' && (
                <div className="flex items-center gap-2 flex-shrink-0">
                  <div className="flex items-center gap-1">
                    <CalendarDays className={`w-4 h-4 ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`} />
                    <input
                      type="date"
                      value={customStartDate}
                      onChange={(e) => setCustomStartDate(e.target.value)}
                      className={`px-3 py-1.5 text-sm border rounded-md focus:outline-none focus:ring-2 transition-colors ${
                        isDarkMode
                          ? 'bg-gray-700 border-gray-600 text-gray-200 focus:ring-green-500 focus:border-green-500'
                          : 'bg-white border-gray-300 text-gray-900 focus:ring-green-500 focus:border-green-500'
                      }`}
                      placeholder="Start date"
                    />
                  </div>
                  <span className={`text-sm ${isDarkMode ? 'text-gray-400' : 'text-gray-500'}`}>to</span>
                  <div className="flex items-center gap-1">
                    <input
                      type="date"
                      value={customEndDate}
                      onChange={(e) => setCustomEndDate(e.target.value)}
                      className={`px-3 py-1.5 text-sm border rounded-md focus:outline-none focus:ring-2 transition-colors ${
                        isDarkMode
                          ? 'bg-gray-700 border-gray-600 text-gray-200 focus:ring-green-500 focus:border-green-500'
                          : 'bg-white border-gray-300 text-gray-900 focus:ring-green-500 focus:border-green-500'
                      }`}
                      placeholder="End date"
                    />
                    {(customStartDate || customEndDate) && (
                      <button
                        onClick={() => {
                          setCustomStartDate('')
                          setCustomEndDate('')
                        }}
                        className={`p-1 rounded transition-colors ${
                          isDarkMode
                            ? 'text-gray-400 hover:text-gray-200 hover:bg-gray-600'
                            : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'
                        }`}
                        title="Clear date filter"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              )}

              {/* Search - Inline with Filter */}
              <div className="flex-1 max-w-xs relative filter-dropdown-container">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                <input
                  type="text"
                  placeholder="Search by name, email, or phone..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className={`w-full pl-10 pr-10 py-2 text-sm border rounded-lg focus:ring-2 ${
                    isDarkMode
                      ? 'bg-gray-700 border-gray-600 text-gray-200 focus:ring-green-500 focus:border-green-500 placeholder-gray-400'
                      : 'border-gray-300 focus:ring-blue-500 focus:border-transparent'
                  }`}
                />
                <button
                  onClick={() => setShowFilterDropdown(!showFilterDropdown)}
                  className={`absolute right-2 top-1/2 transform -translate-y-1/2 p-1 rounded transition-colors ${
                    filterPlatform !== 'all'
                      ? 'text-green-600'
                      : isDarkMode
                      ? 'text-gray-500 hover:text-gray-300'
                      : 'text-gray-400 hover:text-gray-600'
                    }`}
                >
                  <Filter className="w-4 h-4" />
                </button>
                {showFilterDropdown && (
                  <div className={`absolute right-0 mt-2 w-48 rounded-lg shadow-lg z-50 max-h-96 overflow-y-auto ${
                    isDarkMode
                      ? 'bg-gray-800 border border-gray-700 shadow-gray-900/50'
                      : 'bg-white border border-gray-200'
                  }`}>
                    <button
                      onClick={() => {
                        setFilterPlatform('all')
                        setShowFilterDropdown(false)
                      }}
                      className={`w-full text-left px-4 py-2 text-sm first:rounded-t-lg ${filterPlatform === 'all'
                        ? 'bg-green-100 text-green-700 font-medium'
                        : isDarkMode
                        ? 'text-gray-200 hover:bg-gray-700'
                        : 'text-gray-700 hover:bg-gray-50'
                        }`}
                    >
                      All Platforms
                    </button>
                    <button
                      onClick={() => {
                        setFilterPlatform('facebook')
                        setShowFilterDropdown(false)
                      }}
                      className={`w-full text-left px-4 py-2 text-sm ${
                        filterPlatform === 'facebook'
                          ? 'bg-green-100 text-green-700 font-medium'
                          : isDarkMode
                          ? 'text-gray-200 hover:bg-gray-700'
                          : 'text-gray-700 hover:bg-gray-50'
                        }`}
                    >
                      Facebook
                    </button>
                    <button
                      onClick={() => {
                        setFilterPlatform('instagram')
                        setShowFilterDropdown(false)
                      }}
                      className={`w-full text-left px-4 py-2 text-sm ${
                        filterPlatform === 'instagram'
                          ? 'bg-green-100 text-green-700 font-medium'
                          : isDarkMode
                          ? 'text-gray-200 hover:bg-gray-700'
                          : 'text-gray-700 hover:bg-gray-50'
                        }`}
                    >
                      Instagram
                    </button>
                    <button
                      onClick={() => {
                        setFilterPlatform('walk_ins')
                        setShowFilterDropdown(false)
                      }}
                      className={`w-full text-left px-4 py-2 text-sm ${
                        filterPlatform === 'walk_ins'
                          ? 'bg-green-100 text-green-700 font-medium'
                          : isDarkMode
                          ? 'text-gray-200 hover:bg-gray-700'
                          : 'text-gray-700 hover:bg-gray-50'
                        }`}
                    >
                      Walk Ins
                    </button>
                    <button
                      onClick={() => {
                        setFilterPlatform('referral')
                        setShowFilterDropdown(false)
                      }}
                      className={`w-full text-left px-4 py-2 text-sm ${
                        filterPlatform === 'referral'
                          ? 'bg-green-100 text-green-700 font-medium'
                          : isDarkMode
                          ? 'text-gray-200 hover:bg-gray-700'
                          : 'text-gray-700 hover:bg-gray-50'
                        }`}
                    >
                      Referral
                    </button>
                    <button
                      onClick={() => {
                        setFilterPlatform('email')
                        setShowFilterDropdown(false)
                      }}
                      className={`w-full text-left px-4 py-2 text-sm ${
                        filterPlatform === 'email'
                          ? 'bg-green-100 text-green-700 font-medium'
                          : isDarkMode
                          ? 'text-gray-200 hover:bg-gray-700'
                          : 'text-gray-700 hover:bg-gray-50'
                        }`}
                    >
                      Email
                    </button>
                    <button
                      onClick={() => {
                        setFilterPlatform('website')
                        setShowFilterDropdown(false)
                      }}
                      className={`w-full text-left px-4 py-2 text-sm ${
                        filterPlatform === 'website'
                          ? 'bg-green-100 text-green-700 font-medium'
                          : isDarkMode
                          ? 'text-gray-200 hover:bg-gray-700'
                          : 'text-gray-700 hover:bg-gray-50'
                        }`}
                    >
                      Website
                    </button>
                    <button
                      onClick={() => {
                        setFilterPlatform('phone_call')
                        setShowFilterDropdown(false)
                      }}
                      className={`w-full text-left px-4 py-2 text-sm last:rounded-b-lg ${
                        filterPlatform === 'phone_call'
                          ? 'bg-green-100 text-green-700 font-medium'
                          : isDarkMode
                          ? 'text-gray-200 hover:bg-gray-700'
                          : 'text-gray-700 hover:bg-gray-50'
                        }`}
                    >
                      Phone Call
                    </button>
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center space-x-2 flex-shrink-0">
                {selectionMode && (
                  <>
                    <button
                      onClick={handleSelectAll}
                      className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-lg hover:from-green-600 hover:to-emerald-700 transition-all duration-200 shadow-lg hover:shadow-xl"
                    >
                      <CheckCircle className="w-4 h-4" />
                      <span>{selectedLeadIds.size === filteredLeads.length ? 'Deselect All' : 'Select All'}</span>
                    </button>
                    {selectedLeadIds.size > 0 && (
                      <button
                        onClick={handleBulkDelete}
                        disabled={deletingBulk}
                        className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-red-500 to-red-600 text-white rounded-lg hover:from-red-600 hover:to-red-700 transition-all duration-200 disabled:opacity-50 shadow-lg hover:shadow-xl"
                      >
                        {deletingBulk ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <XCircle className="w-4 h-4" />
                        )}
                        <span>Delete ({selectedLeadIds.size})</span>
                      </button>
                    )}
                    <button
                      onClick={handleToggleSelectionMode}
                      className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-all duration-200 shadow-lg hover:shadow-xl ${
                        isDarkMode
                          ? 'bg-gray-600 text-gray-200 hover:bg-gray-500'
                          : 'bg-gray-500 text-white hover:bg-gray-600'
                      }`}
                    >
                      <X className="w-4 h-4" />
                      <span>Cancel</span>
                    </button>
                  </>
                )}
                {!selectionMode && (
                  <>
                    <button
                      onClick={() => setShowAddModal(true)}
                      className={`p-2 rounded-lg transition-all duration-200 shadow-md hover:shadow-lg border ${
                        isDarkMode
                          ? 'bg-gray-700 text-gray-200 hover:bg-gray-600 border-gray-600'
                          : 'bg-white text-black hover:bg-gray-100 border-gray-200'
                      }`}
                      title="Add Lead"
                    >
                      <UserPlus className="w-5 h-5" />
                    </button>
                    <button
                      onClick={handleRefresh}
                      disabled={loading}
                      className={`p-2 rounded-lg transition-all duration-200 disabled:opacity-50 shadow-md hover:shadow-lg border ${
                        isDarkMode
                          ? 'bg-gray-700 text-gray-200 hover:bg-gray-600 border-gray-600'
                          : 'bg-white text-black hover:bg-gray-100 border-gray-200'
                      }`}
                      title="Refresh"
                    >
                      <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Leads Board - Column Layout by Status */}
        <div className="flex-1 px-4 lg:px-6 py-6 overflow-x-hidden">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <p className={`text-lg ${isDarkMode ? 'text-gray-400' : 'text-gray-600'}`}>Loading leads...</p>
            </div>
          ) : filteredLeads.length === 0 ? (
            <div className="text-center py-12">
              <Users className={`w-16 h-16 mx-auto mb-4 ${
                isDarkMode ? 'text-gray-600' : 'text-gray-300'
              }`} />
              <h3 className={`text-lg font-semibold mb-2 ${
                isDarkMode ? 'text-gray-100' : 'text-gray-900'
              }`}>
                {searchQuery ? 'No leads found' : 'No leads yet'}
              </h3>
              <p className={`${
                isDarkMode ? 'text-gray-400' : 'text-gray-500'
              }`}>
                {searchQuery
                  ? 'Try adjusting your search or filters'
                  : 'Leads from your Facebook and Instagram ads will appear here'}
              </p>
            </div>
          ) : (
            <div className="flex gap-2 w-full">
              {statusFilters
                .filter(statusFilter => statusFilter.value !== 'all') // Exclude 'all' from column view
                .map((statusFilter) => {
                  const columnLeads = filteredLeads.filter(lead => lead.status === statusFilter.value)
                  const statusConfig = getStatusConfig(statusFilter.value)
                  const StatusIcon = statusConfig.icon

                  return (
                    <div key={statusFilter.value} className="flex-1 min-w-0">
                      {/* Column Header */}
                      <div className="mb-2">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-1.5">
                            <StatusIcon className={`w-3 h-3 ${statusConfig.textColor}`} />
                            <h3 className={`font-semibold text-sm ${statusConfig.textColor}`}>{statusFilter.label}</h3>
                          </div>
                          <span className={`text-sm font-medium ${statusConfig.textColor}`}>
                            {columnLeads.length}
                          </span>
                        </div>
                      </div>
                      {/* Line after column title */}
                      <div className={`mb-2 border-b ${statusConfig.borderColor}`}></div>

                      {/* Column Cards */}
                      <div className={`space-y-1.5 max-h-[calc(100vh-180px)] overflow-y-auto pb-4 custom-scrollbar ${
                        isDarkMode ? 'dark-mode' : 'light-mode'
                      }`}>
                        {columnLeads.length === 0 ? (
                          <div className={`text-center py-8 text-sm ${
                            isDarkMode ? 'text-gray-400' : 'text-gray-500'
                          }`}>
                            No {statusFilter.label.toLowerCase()} leads
                          </div>
                        ) : (
                          columnLeads.map((lead) => (
                            <LeadCard
                              key={lead.id}
                              lead={lead}
                              onClick={handleLeadClick}
                              onDelete={handleDeleteLead}
                              isSelected={selectedLeadIds.has(lead.id)}
                              onSelect={handleSelectLead}
                              isDarkMode={isDarkMode}
                              selectionMode={selectionMode}
                            />
                          ))
                        )}
                      </div>
                    </div>
                  )
                })}
            </div>
          )}
        </div>
      </div>

      {/* Lead Detail Modal */}
      {showDetailModal && selectedLead && (
        <LeadDetailModal
          lead={selectedLead}
          onClose={handleCloseModal}
          onUpdate={fetchLeads}
          isDarkMode={isDarkMode}
        />
      )}

      {/* Add Lead Modal */}
      <AddLeadModal
        isOpen={showAddModal}
        onClose={() => setShowAddModal(false)}
        onSuccess={async (data) => {
          if (data && data.type === 'csv') {
            // Handle CSV import
            await handleCSVImport(data.file)
            setShowAddModal(false)
          } else {
            // Handle regular lead creation
            await fetchLeads(false)
            setShowAddModal(false)
          }
        }}
        isImporting={importingCSV}
        isDarkMode={isDarkMode}
      />
    </div>
  )
}

export default LeadsDashboard

