import React, { useState, useEffect, useRef } from 'react'

const CharacterCard = ({ agentName, isVisible = false, position = { x: 0, y: 0 }, likesCount = 0, tasksCount = 0, isDarkMode = false }) => {
  const getAgentInfo = (name) => {
    switch (name?.toLowerCase()) {
      case 'emily':
        return {
          logo: '/emily_icon.png',
          name: 'Emily',
          abilities: 'Content Manager | Social Media Specialist. Helps businesses optimize their content strategy by suggesting, publishing, searching, and managing posts across all platforms.'
        }
      case 'leo':
        return {
          logo: '/leo_logo.jpg',
          name: 'Leo',
          abilities: 'Content Creator | Creative Director. Specializes in crafting engaging content, writing compelling copy, and designing visuals that drive audience engagement.'
        }
      case 'chase':
        return {
          logo: '/chase_logo.png',
          name: 'Chase',
          abilities: 'Lead Manager | Customer Success Specialist. Focuses on lead nurturing, customer relationship management, and driving sales conversions through strategic follow-ups.'
        }
      case 'atsn':
        return {
          logo: null, // Combined logo handled in renderAgentIcon
          name: 'ATSN Team',
          abilities: 'Your complete business automation solution. Emily manages content strategy, Leo creates engaging content, and Chase nurtures leads - working together to grow your business.'
        }
      case 'orio':
        return {
          logo: null, // No logo for Orio yet
          name: 'Orio',
          abilities: 'Data Analyst | Business Intelligence Expert. Provides actionable insights through advanced analytics to help optimize business performance and ROI.'
        }
      default:
        return {
          logo: '/emily_icon.png',
          name: 'Emily',
          abilities: 'Content Manager | Social Media Specialist. Helps businesses optimize their content strategy by suggesting, publishing, searching, and managing posts across all platforms.'
        }
    }
  }

  const agentInfo = getAgentInfo(agentName)
  const cardRef = useRef(null)
  const [adjustedPosition, setAdjustedPosition] = useState({ x: position.x, y: position.y })

  useEffect(() => {
    if (!isVisible || !cardRef.current) return

    const card = cardRef.current
    const cardRect = card.getBoundingClientRect()
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    // Card dimensions (approximate)
    const cardWidth = 448 // min-w-[28rem] = 448px
    const cardHeight = 200 // approximate height

    let newX = position.x
    let newY = position.y

    // Check horizontal boundaries
    if (position.x - cardWidth / 2 < 0) {
      // Too far left, align to left edge
      newX = cardWidth / 2 + 10
    } else if (position.x + cardWidth / 2 > viewportWidth) {
      // Too far right, align to right edge
      newX = viewportWidth - cardWidth / 2 - 10
    }

    // Check vertical boundaries
    if (position.y - cardHeight - 20 < 0) {
      // Too high, show below cursor instead
      newY = position.y + 20
    } else {
      // Normal position above cursor
      newY = position.y - 8
    }

    setAdjustedPosition({ x: newX, y: newY })
  }, [isVisible, position])

  if (!isVisible) return null

  return (
    <div
      ref={cardRef}
      className={`fixed z-50 backdrop-blur-md rounded-xl shadow-2xl p-5 min-w-[28rem] max-w-lg pointer-events-none ${
        isDarkMode
          ? 'bg-gray-900/90 border border-gray-700/50'
          : 'bg-white/90 border border-white/20'
      }`}
      style={{
        left: adjustedPosition.x,
        top: adjustedPosition.y,
        transform: position.y - adjustedPosition.y > 0 ? 'translate(-50%, -100%)' : 'translate(-50%, 20px)',
      }}
    >
      <div className="flex items-start gap-5">
        {/* Agent Logo */}
        <div className="flex-shrink-0">
          {agentName?.toLowerCase() === 'atsn' ? (
            <div className={`w-20 h-20 rounded-full bg-gradient-to-br from-purple-500 via-blue-500 to-green-500 flex items-center justify-center relative overflow-hidden border-2 shadow-lg ${
              isDarkMode ? 'border-gray-600/50' : 'border-white/30'
            }`}>
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="w-16 h-16 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm">
                  <div className="grid grid-cols-2 gap-1">
                    <img src="/emily_icon.png" alt="E" className="w-5 h-5 rounded-full object-cover" />
                    <img src="/leo_logo.jpg" alt="L" className="w-5 h-5 rounded-full object-cover" />
                    <img src="/chase_logo.png" alt="C" className="w-5 h-5 rounded-full object-cover" />
                    <div className="w-5 h-5 rounded-full bg-white/30 flex items-center justify-center">
                      <span className="text-xs font-bold text-white">A</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : agentInfo.logo ? (
            <img
              src={agentInfo.logo}
              alt={`${agentInfo.name} logo`}
              className={`w-20 h-20 rounded-full object-cover border-2 shadow-lg ${
                isDarkMode ? 'border-gray-600/50' : 'border-white/30'
              }`}
            />
          ) : (
            <div className={`w-20 h-20 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white text-2xl font-bold border-2 shadow-lg ${
              isDarkMode ? 'border-gray-600/50' : 'border-white/30'
            }`}>
              O
            </div>
          )}
        </div>

        {/* Agent Description */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-2">
            <h3 className={`text-lg font-bold ${
              isDarkMode ? 'text-white' : 'text-gray-900'
            }`}>
              {agentInfo.name}
            </h3>
            <span className="text-yellow-500 font-bold text-sm">★★★★★</span>
            <span className={`text-sm font-normal ${
              isDarkMode ? 'text-gray-300' : 'text-gray-600'
            }`}>
              {likesCount} likes | {tasksCount} tasks
            </span>
          </div>
          <div className={`text-sm leading-relaxed ${
            isDarkMode ? 'text-gray-300' : 'text-gray-600'
          }`}>
            {agentInfo.abilities}
          </div>
        </div>
      </div>

            {/* Tooltip arrow */}
            {position.y - adjustedPosition.y > 0 ? (
              // Arrow pointing down (card above cursor)
              <>
                <div
                  className={`absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent ${
                    isDarkMode ? 'border-t-gray-900/90' : 'border-t-white/90'
                  }`}
                  style={{ marginTop: '-1px' }}
                ></div>
                <div
                  className={`absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent ${
                    isDarkMode ? 'border-t-gray-700/50' : 'border-t-white/20'
                  }`}
                  style={{ marginTop: '0px' }}
                ></div>
              </>
            ) : (
              // Arrow pointing up (card below cursor)
              <>
                <div
                  className={`absolute bottom-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-b-4 border-transparent ${
                    isDarkMode ? 'border-b-gray-900/90' : 'border-b-white/90'
                  }`}
                  style={{ marginBottom: '-1px' }}
                ></div>
                <div
                  className={`absolute bottom-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-b-4 border-transparent ${
                    isDarkMode ? 'border-b-gray-700/50' : 'border-b-white/20'
                  }`}
                  style={{ marginBottom: '0px' }}
                ></div>
              </>
            )}
    </div>
  )
}

export default CharacterCard
