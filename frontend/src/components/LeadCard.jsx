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

const LeadCard = ({ lead, onClick, onDelete, isSelected = false, onSelect = null, selectionMode = false }) => {
  const getStatusConfig = (status) => {
    const configs = {
      new: {
        color: 'from-blue-500 to-blue-600',
        bgColor: 'bg-blue-50',
        textColor: 'text-blue-700',
        borderColor: 'border-blue-200',
        icon: AlertCircle,
        label: 'New'
      },
      contacted: {
        color: 'from-purple-500 to-purple-600',
        bgColor: 'bg-purple-50',
        textColor: 'text-purple-700',
        borderColor: 'border-purple-200',
        icon: MessageCircle,
        label: 'Contacted'
      },
      responded: {
        color: 'from-green-500 to-green-600',
        bgColor: 'bg-green-50',
        textColor: 'text-green-700',
        borderColor: 'border-green-200',
        icon: CheckCircle,
        label: 'Responded'
      },
      qualified: {
        color: 'from-orange-500 to-orange-600',
        bgColor: 'bg-orange-50',
        textColor: 'text-orange-700',
        borderColor: 'border-orange-200',
        icon: CheckCircle,
        label: 'Qualified'
      },
      converted: {
        color: 'from-emerald-500 to-emerald-600',
        bgColor: 'bg-emerald-50',
        textColor: 'text-emerald-700',
        borderColor: 'border-emerald-200',
        icon: CheckCircle,
        label: 'Converted'
      },
      lost: {
        color: 'from-gray-400 to-gray-500',
        bgColor: 'bg-gray-50',
        textColor: 'text-gray-700',
        borderColor: 'border-gray-200',
        icon: XCircle,
        label: 'Lost'
      },
      invalid: {
        color: 'from-red-500 to-red-600',
        bgColor: 'bg-red-50',
        textColor: 'text-red-700',
        borderColor: 'border-red-200',
        icon: XCircle,
        label: 'Invalid'
      }
    }
    return configs[status] || configs.new
  }

  const getPlatformIcon = (platform) => {
    switch (platform) {
      case 'Facebook':
        return <Facebook className="w-3.5 h-3.5" />
      case 'Instagram':
        return <Instagram className="w-3.5 h-3.5" />
      case 'Walk Ins':
        return <LogIn className="w-3.5 h-3.5" />
      case 'Referral':
        return <Users className="w-3.5 h-3.5" />
      case 'Email':
        return <Mail className="w-3.5 h-3.5" />
      case 'Website':
        return <Globe className="w-3.5 h-3.5" />
      case 'Phone Call':
        return <Phone className="w-3.5 h-3.5" />
      case 'Manual Entry':
      default:
        return <User className="w-3.5 h-3.5" />
    }
  }

  const getPlatformColor = (platform) => {
    switch (platform) {
      case 'Facebook':
        return 'from-blue-600 to-blue-800'
      case 'Instagram':
        return 'from-pink-500 via-purple-500 to-pink-600'
      case 'Walk Ins':
        return 'from-green-500 to-green-700'
      case 'Referral':
        return 'from-purple-500 to-purple-700'
      case 'Email':
        return 'from-blue-400 to-blue-600'
      case 'Website':
        return 'from-indigo-500 to-indigo-700'
      case 'Phone Call':
        return 'from-teal-500 to-teal-700'
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
      className={`bg-white rounded-lg shadow-md overflow-hidden ${selectionMode ? 'cursor-default' : 'cursor-pointer'} border-2 ${statusConfig.borderColor} ${isSelected ? 'ring-2 ring-purple-500' : ''}`}
    >
      {/* Header */}
      <div className="bg-white p-2 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-1.5 flex-1 min-w-0">
            {selectionMode && (
              <input
                type="checkbox"
                checked={isSelected}
                onChange={handleCheckboxChange}
                onClick={(e) => e.stopPropagation()}
                className="w-4 h-4 rounded border-gray-300 bg-white text-purple-600 focus:ring-purple-500 focus:ring-2 cursor-pointer flex-shrink-0"
              />
            )}
            <div className="w-6 h-6 rounded-full bg-gray-100 flex items-center justify-center flex-shrink-0">
              {getPlatformIcon(lead.source_platform)}
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="font-semibold text-xs truncate text-gray-900">
                {lead.name || 'Unknown Lead'}
              </h3>
              <div className="flex items-center space-x-0.5 text-[10px] text-gray-600">
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
              className="p-1 bg-gray-100 rounded flex-shrink-0 ml-0.5 hover:bg-gray-200 transition-colors"
              title="Delete lead"
            >
              <Trash2 className="w-3 h-3 text-gray-700" />
            </button>
          )}
        </div>
      </div>

      {/* Follow-up Date */}
      {lead.follow_up_at && (
        <div className="p-1.5 border-t border-gray-200">
          <div className="flex items-center space-x-1 text-[10px] text-gray-600">
            <Calendar className="w-3 h-3" />
            <span className="font-medium">Follow-up:</span>
            <span>{formatFollowUpDate(lead.follow_up_at)}</span>
          </div>
        </div>
      )}

      {/* Remarks Section */}
      {lead.last_remark && (
        <div className={`p-1.5 ${statusConfig.bgColor} border-t ${statusConfig.borderColor}`}>
          <p className="text-[10px] text-gray-700 line-clamp-2">
            {lead.last_remark.charAt(0).toUpperCase() + lead.last_remark.slice(1)}
          </p>
        </div>
      )}

      {/* Content - Only show if form data exists */}
      {lead.form_data && Object.keys(lead.form_data).length > 0 && (
        <div className="p-1.5">
          <p className="text-[10px] text-gray-500">
            {Object.keys(lead.form_data).length} form field{Object.keys(lead.form_data).length !== 1 ? 's' : ''} captured
          </p>
        </div>
      )}
    </div>
  )
}

export default LeadCard

