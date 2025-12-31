import React from 'react'
import { Instagram, Facebook, MessageCircle, Hash, Heart, Share, MessageSquare } from 'lucide-react'

const ATSNContentCard = ({ content, platform, contentType, intent, onClick, isDarkMode = false }) => {
  // Platform icons
  const getPlatformIcon = (platformName) => {
    switch (platformName?.toLowerCase()) {
      case 'instagram':
        return <Instagram className="w-5 h-5 text-pink-500" />
      case 'facebook':
        return <Facebook className="w-5 h-5 text-blue-600" />
      case 'linkedin':
        return <div className="w-5 h-5 bg-blue-700 rounded-sm flex items-center justify-center text-white text-xs font-bold">in</div>
      case 'twitter':
        return <div className="w-5 h-5 bg-blue-400 rounded-full flex items-center justify-center text-white text-xs">𝕏</div>
      case 'tiktok':
        return <div className="w-5 h-5 bg-black rounded-sm flex items-center justify-center text-white text-xs">TT</div>
      default:
        return <MessageCircle className="w-5 h-5 text-gray-500" />
    }
  }

  // Platform display name
  const getPlatformDisplayName = (platformName) => {
    switch (platformName?.toLowerCase()) {
      case 'whatsapp business':
        return 'WhatsApp'
      case 'gmail':
        return 'Email'
      default:
        return platformName?.charAt(0).toUpperCase() + platformName?.slice(1)
    }
  }

  return (
    <div
      className={`rounded-xl shadow-lg overflow-hidden max-w-lg w-full cursor-pointer transition-all duration-200 ${
        isDarkMode
          ? 'bg-gray-800 border border-gray-700 shadow-xl hover:bg-gray-700'
          : 'bg-white shadow-lg hover:shadow-xl'
      }`}
      onClick={onClick}
    >
      {/* Header with platform logo and name */}
      <div className={`flex items-center justify-between p-4 border-b ${
        isDarkMode ? 'border-gray-600 bg-gray-900' : 'border-gray-100'
      }`}>
        <div className="flex items-center gap-3">
          {getPlatformIcon(platform)}
          <span className={`font-semibold ${
            isDarkMode ? 'text-gray-100' : 'text-gray-900'
          }`}>
            {getPlatformDisplayName(platform)} | {contentType?.replace('_', ' ')}
          </span>
        </div>
      </div>

      {/* Image on top */}
      {content.media_url && (
        <div className="p-2">
          <img
            src={content.media_url}
            alt={content.title || "Content image"}
            className="w-full aspect-square object-cover rounded-lg"
            onError={(e) => {
              e.target.style.display = 'none'
            }}
          />
        </div>
      )}

      {/* Instagram interaction icons */}
      {content.media_url && platform?.toLowerCase() === 'instagram' && (
        <div className="px-4 pb-2 flex justify-between items-center">
          <div className="flex items-center gap-4">
            <button className={`hover:text-red-500 transition-colors ${
              isDarkMode ? 'text-gray-400' : 'text-gray-700'
            }`}>
              <Heart className="w-5 h-5" />
            </button>
            <button className={`hover:text-blue-500 transition-colors ${
              isDarkMode ? 'text-gray-400' : 'text-gray-700'
            }`}>
              <MessageSquare className="w-5 h-5" />
            </button>
          </div>
          <button className={`hover:text-green-500 transition-colors ${
            isDarkMode ? 'text-gray-400' : 'text-gray-700'
          }`}>
            <Share className="w-5 h-5" />
          </button>
        </div>
      )}

      {/* Content */}
      <div className="p-4">
        {/* Title */}
        {content.title && (
          <h3 className={`text-lg font-bold mb-2 leading-tight ${
            isDarkMode ? 'text-gray-100' : 'text-gray-900'
          }`}>
            {content.title}
          </h3>
        )}

        {/* Content and Hashtags - Hide for view_content and delete_content */}
        {intent !== 'view_content' && intent !== 'delete_content' && (
          <>
            {/* Content text */}
            {content.content && (
              <p className={`text-sm leading-relaxed mb-3 ${
                isDarkMode ? 'text-gray-200' : 'text-gray-700'
              }`}>
                {content.content.length > 150
                  ? `${content.content.substring(0, 150)}...`
                  : content.content
                }
              </p>
            )}

            {/* Hashtags */}
            {content.hashtags && content.hashtags.length > 0 && (
              <p className={`text-sm ${
                isDarkMode ? 'text-blue-400' : 'text-blue-500'
              }`}>
                {content.hashtags.slice(0, 8).map((hashtag, index) => (
                  <span key={index}>
                    {hashtag.startsWith('#') ? hashtag : `#${hashtag}`}
                    {index < Math.min(content.hashtags.length, 8) - 1 ? ' ' : ''}
                  </span>
                ))}
                {content.hashtags.length > 8 && (
                  <span className={isDarkMode ? 'text-gray-500' : 'text-gray-500'}>
                    +{content.hashtags.length - 8} more
                  </span>
                )}
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default ATSNContentCard
