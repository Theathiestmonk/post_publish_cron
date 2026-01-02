import React from 'react'
import { 
  User, 
  Mail, 
  Phone, 
  Facebook, 
  Instagram, 
  MessageCircle, 
  CheckCircle,
  XCircle,
  AlertCircle,
  Trash2,
  Globe,
  Users,
  LogIn,
  Calendar
} from 'lucide-react'

const LeadCard = ({ lead, onClick, onDelete, isSelected = false, onSelect = null, selectionMode = false, isDarkMode = false }) => {
  const getStatusConfig = (status) => {
    const configs = {
      new: {
        color: 'from-green-400 to-green-500',
        bgColor: isDarkMode ? 'bg-green-900/20' : 'bg-green-100',
        textColor: isDarkMode ? 'text-green-300' : 'text-green-800',
        borderColor: isDarkMode ? 'border-green-800' : 'border-green-300',
        icon: AlertCircle,
        label: 'New'
      },
      contacted: {
        color: 'from-green-500 to-green-600',
        bgColor: isDarkMode ? 'bg-green-900/30' : 'bg-green-200',
        textColor: isDarkMode ? 'text-green-300' : 'text-green-900',
        borderColor: isDarkMode ? 'border-green-700' : 'border-green-400',
        icon: MessageCircle,
        label: 'Contacted'
      },
      responded: {
        color: 'from-green-600 to-green-700',
        bgColor: isDarkMode ? 'bg-green-900/40' : 'bg-green-300',
        textColor: isDarkMode ? 'text-green-200' : 'text-green-950',
        borderColor: isDarkMode ? 'border-green-600' : 'border-green-500',
        icon: CheckCircle,
        label: 'Responded'
      },
      qualified: {
        color: 'from-amber-600 to-amber-700',
        bgColor: isDarkMode ? 'bg-amber-900/20' : 'bg-amber-100',
        textColor: isDarkMode ? 'text-amber-300' : 'text-amber-800',
        borderColor: isDarkMode ? 'border-amber-800' : 'border-amber-300',
        icon: CheckCircle,
        label: 'Qualified'
      },
      converted: {
        color: 'from-amber-700 to-amber-800',
        bgColor: isDarkMode ? 'bg-amber-900/30' : 'bg-amber-200',
        textColor: isDarkMode ? 'text-amber-200' : 'text-amber-900',
        borderColor: isDarkMode ? 'border-amber-700' : 'border-amber-400',
        icon: CheckCircle,
        label: 'Converted'
      },
      lost: {
        color: 'from-amber-800 to-amber-900',
        bgColor: isDarkMode ? 'bg-amber-900/40' : 'bg-amber-300',
        textColor: isDarkMode ? 'text-amber-100' : 'text-amber-950',
        borderColor: isDarkMode ? 'border-amber-600' : 'border-amber-500',
        icon: XCircle,
        label: 'Lost'
      },
      invalid: {
        color: 'from-red-500 to-red-600',
        bgColor: isDarkMode ? 'bg-red-900/20' : 'bg-red-50',
        textColor: isDarkMode ? 'text-red-400' : 'text-red-700',
        borderColor: isDarkMode ? 'border-red-700' : 'border-red-300',
        icon: XCircle,
        label: 'Invalid'
      }
    }
    return configs[status] || configs.new
  }

  const getPlatformIcon = (platform) => {
    switch (platform) {
      case 'Facebook':
        return <Facebook className="w-6 h-6" />
      case 'Instagram':
        return <Instagram className="w-6 h-6" />
      case 'Walk Ins':
        return <LogIn className="w-6 h-6" />
      case 'Referral':
        return <Users className="w-6 h-6" />
      case 'Email':
        return <Mail className="w-6 h-6" />
      case 'Website':
        return <Globe className="w-6 h-6" />
      case 'Phone Call':
        return <Phone className="w-6 h-6" />
      case 'Manual Entry':
      default:
        return <User className="w-6 h-6" />
    }
  }

  const getPlatformColor = (platform) => {
    switch (platform) {
      case 'Facebook':
        return 'from-green-600 to-green-800'
      case 'Instagram':
        return 'from-amber-500 via-green-500 to-amber-600'
      case 'Walk Ins':
        return 'from-green-500 to-green-700'
      case 'Referral':
        return 'from-amber-600 to-amber-800'
      case 'Email':
        return 'from-green-400 to-green-600'
      case 'Website':
        return 'from-amber-500 to-amber-700'
      case 'Phone Call':
        return 'from-green-600 to-amber-700'
      case 'Manual Entry':
      default:
        return 'from-gray-500 to-gray-700'
    }
  }

  const formatTimeAgo = (dateString) => {
    if (!dateString) return 'Unknown'
    
    const date = new Date(dateString)
    const now = new Date()
    const diffInMinutes = Math.floor((now - date) / (1000 * 60))
    const diffInHours = Math.floor(diffInMinutes / 60)
    const diffInDays = Math.floor(diffInHours / 24)
    
    if (diffInMinutes < 1) return 'Just now'
    if (diffInMinutes < 60) return `${diffInMinutes}m ago`
    if (diffInHours < 24) return `${diffInHours}h ago`
    if (diffInDays === 1) return 'Yesterday'
    if (diffInDays < 7) return `${diffInDays}d ago`
    
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric'
    })
  }

  const formatFollowUpDate = (dateString) => {
    if (!dateString) return null
    
    const date = new Date(dateString)
    const now = new Date()
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
    const followUpDate = new Date(date.getFullYear(), date.getMonth(), date.getDate())
    const diffInDays = Math.floor((followUpDate - today) / (1000 * 60 * 60 * 24))
    
    if (diffInDays === 0) return 'Today'
    if (diffInDays === 1) return 'Tomorrow'
    if (diffInDays === -1) return 'Yesterday'
    if (diffInDays < 0) return `${Math.abs(diffInDays)} days ago`
    if (diffInDays <= 7) return `In ${diffInDays} days`
    
    return date.toLocaleDateString('en-US', { 
      month: 'short', 
      day: 'numeric',
      year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined
    })
  }

  const statusConfig = getStatusConfig(lead.status)
  const StatusIcon = statusConfig.icon
  const platformColor = getPlatformColor(lead.source_platform)

  const handleCardClick = (e) => {
    // Don't trigger onClick if clicking on checkbox or delete button
    if (e.target.closest('input[type="checkbox"]') || e.target.closest('button')) {
      return
    }
    if (onClick && !selectionMode) {
      onClick(lead)
    }
  }

  const handleCheckboxChange = (e) => {
    e.stopPropagation()
    if (onSelect) {
      onSelect(lead.id, e.target.checked)
    }
  }

  return (
    <div
      onClick={handleCardClick}
      className={`${isDarkMode ? 'bg-gray-800' : 'bg-white'} rounded-lg shadow-md overflow-hidden ${selectionMode ? 'cursor-default' : 'cursor-pointer'} border-2 ${statusConfig.borderColor} ${isSelected ? 'ring-2 ring-green-500' : ''}`}
    >
      {/* Header */}
      <div className={`${isDarkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} p-2 border-b`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-1.5 flex-1 min-w-0">
            {selectionMode && (
              <input
                type="checkbox"
                checked={isSelected}
                onChange={handleCheckboxChange}
                onClick={(e) => e.stopPropagation()}
                className={`w-4 h-4 rounded ${isDarkMode ? 'border-gray-600 bg-gray-700 text-green-400 focus:ring-green-400' : 'border-gray-300 bg-white text-green-600 focus:ring-green-500'} focus:ring-2 cursor-pointer flex-shrink-0`}
              />
            )}
            <div className={`w-9 h-9 rounded-full ${isDarkMode ? 'bg-green-700' : 'bg-green-200'} flex items-center justify-center flex-shrink-0 ${isDarkMode ? 'text-green-100' : 'text-green-800'}`}>
              {getPlatformIcon(lead.source_platform)}
            </div>
            <div className="min-w-0 flex-1">
              <h3 className={`font-semibold text-lg truncate ${isDarkMode ? 'text-gray-100' : 'text-gray-900'}`}>
                {(lead.name || 'Unknown Lead').charAt(0).toUpperCase() + (lead.name || 'Unknown Lead').slice(1)}
              </h3>
              <div className={`flex items-center space-x-0.5 text-base ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
                <span className="capitalize truncate">{lead.source_platform}</span>
                <span>•</span>
                <span className="truncate">{formatTimeAgo(lead.created_at)}</span>
              </div>
            </div>
          </div>
          {!selectionMode && onDelete && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onDelete(lead)
              }}
              className={`p-1 ${isDarkMode ? 'bg-gray-700 hover:bg-gray-600' : 'bg-gray-100 hover:bg-gray-200'} rounded flex-shrink-0 ml-0.5 transition-colors`}
              title="Delete lead"
            >
              <Trash2 className={`w-3 h-3 ${isDarkMode ? 'text-gray-300' : 'text-gray-700'}`} />
            </button>
          )}
        </div>
      </div>

      {/* Follow-up Date */}
      {lead.follow_up_at && (
        <div className={`p-1.5 border-t ${isDarkMode ? 'border-gray-700' : 'border-gray-200'}`}>
          <div className={`flex items-center space-x-1 text-base ${isDarkMode ? 'text-gray-300' : 'text-gray-600'}`}>
            <Calendar className="w-5 h-5" />
            <span className="font-medium">Follow-up:</span>
            <span>{formatFollowUpDate(lead.follow_up_at)}</span>
          </div>
        </div>
      )}

      {/* Remarks Section */}
      {lead.last_remark && (
        <div className={`p-1.5 ${statusConfig.bgColor} border-t ${statusConfig.borderColor}`}>
          <p className={`text-base ${isDarkMode ? 'text-gray-300' : 'text-gray-700'} line-clamp-2`}>
            {lead.last_remark.charAt(0).toUpperCase() + lead.last_remark.slice(1)}
          </p>
        </div>
      )}

      {/* Content - Only show if form data exists */}
      {lead.form_data && Object.keys(lead.form_data).length > 0 && (
        <div className="p-1.5">
          <p className={`text-base ${isDarkMode ? 'text-gray-300' : 'text-gray-500'}`}>
            {Object.keys(lead.form_data).length} form field{Object.keys(lead.form_data).length !== 1 ? 's' : ''} captured
          </p>
        </div>
      )}
    </div>
  )
}

export default LeadCard

