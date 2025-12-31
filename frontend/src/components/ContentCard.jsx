import React, { useState } from 'react';
import { Copy, Edit, Eye, Heart, MessageCircle, Share, Calendar, Hash, Image as ImageIcon, Video, FileText, Layers, ChevronLeft, ChevronRight, Play } from 'lucide-react';

const ContentCard = ({ content, platform, contentType, onEdit, onCopy, onPreview, minimal = false }) => {
  const [copied, setCopied] = useState(false);
  const [showFullContent, setShowFullContent] = useState(false);
  const [currentCarouselIndex, setCurrentCarouselIndex] = useState(0);

  const handleCopy = async () => {
    try {
      let textToCopy = '';

      // Handle different content types for copying
      if (contentType?.toLowerCase() === 'email' && content.email_subject && content.email_body) {
        textToCopy = `Subject: ${content.email_subject}\n\n${content.email_body}`;
      } else if ((contentType?.toLowerCase() === 'short video' || contentType?.toLowerCase() === 'long video') && (content.short_video_script || content.long_video_script)) {
        textToCopy = content.short_video_script || content.long_video_script;
      } else if (contentType?.toLowerCase() === 'message' && content.message) {
        textToCopy = content.message;
      } else {
        textToCopy = content.content || content;
      }

      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy content:', err);
    }
  };

  const getPlatformIcon = (platform) => {
    switch (platform?.toLowerCase()) {
      case 'instagram': return '📷';
      case 'facebook': return '📘';
      case 'twitter': return '🐦';
      case 'linkedin': return '💼';
      case 'tiktok': return '🎵';
      case 'pinterest': return '📌';
      case 'whatsapp business': return '💬';
      default: return '📱';
    }
  };

  const getContentTypeIcon = (contentType) => {
    switch (contentType?.toLowerCase()) {
      case 'story': return <FileText className="w-4 h-4" />;
      case 'post': return <MessageCircle className="w-4 h-4" />;
      case 'reel': return <Video className="w-4 h-4" />;
      case 'short video': return <Video className="w-4 h-4" />;
      case 'long video': return <Video className="w-4 h-4" />;
      case 'video': return <Video className="w-4 h-4" />;
      case 'image': return <ImageIcon className="w-4 h-4" />;
      case 'carousel': return <Layers className="w-4 h-4" />;
      case 'email': return <FileText className="w-4 h-4" />;
      case 'message': return <MessageCircle className="w-4 h-4" />;
      default: return <FileText className="w-4 h-4" />;
    }
  };

  const getPlatformColor = (platform) => {
    switch (platform?.toLowerCase()) {
      case 'instagram': return 'from-pink-500 to-purple-600';
      case 'facebook': return 'from-blue-600 to-blue-800';
      case 'twitter': return 'from-sky-400 to-sky-600';
      case 'linkedin': return 'from-blue-700 to-blue-900';
      case 'tiktok': return 'from-black to-gray-800';
      case 'pinterest': return 'from-red-500 to-red-700';
      case 'whatsapp business': return 'from-green-500 to-green-700';
      default: return 'from-gray-500 to-gray-700';
    }
  };

  const contentText = content.content || content;
  const title = content.title || `${contentType} for ${platform}`;
  const hashtags = content.hashtags || [];
  const mediaUrl = content.media_url || content.mediaUrl;
  
  // Check if the media file is a video
  const isVideoFile = (url) => {
    if (!url) return false;
    const videoExtensions = ['.mp4', '.avi', '.mov', '.wmv', '.webm', '.mkv'];
    return videoExtensions.some(ext => url.toLowerCase().includes(ext));
  };
  
  // Determine if media is a video
  const isVideo = content.post_type === 'video' || 
                  content.content_type?.toLowerCase() === 'video' ||
                  contentType?.toLowerCase() === 'video' ||
                  content.metadata?.media_type === 'video' ||
                  (mediaUrl && isVideoFile(mediaUrl));
  
  // Check if this is a carousel post - enhanced detection
  const isCarousel = content.post_type === 'carousel' || 
                     contentType?.toLowerCase() === 'carousel' ||
                     content.content_type?.toLowerCase() === 'carousel' ||
                     content.selected_content_type?.toLowerCase() === 'carousel' ||
                     (content.metadata && content.metadata.carousel_images && content.metadata.carousel_images.length > 0) ||
                     (content.carousel_images && content.carousel_images.length > 0) ||
                     (content.metadata && content.metadata.total_images && content.metadata.total_images > 1);
  
  // Get carousel images from various possible locations
  let carouselImages = [];
  if (isCarousel) {
    // Check multiple locations for carousel images
    if (content.carousel_images && Array.isArray(content.carousel_images) && content.carousel_images.length > 0) {
      carouselImages = content.carousel_images.map(img => typeof img === 'string' ? img : (img.url || img));
    } else if (content.metadata?.carousel_images && Array.isArray(content.metadata.carousel_images) && content.metadata.carousel_images.length > 0) {
      carouselImages = content.metadata.carousel_images.map(img => typeof img === 'string' ? img : (img.url || img));
    } else if (content.metadata?.images && Array.isArray(content.metadata.images) && content.metadata.images.length > 0) {
      carouselImages = content.metadata.images.map(img => typeof img === 'string' ? img : (img.url || img));
    } else if (content.images && Array.isArray(content.images) && content.images.length > 0) {
      // Also check content_images relationship if available
      carouselImages = content.images.map(img => typeof img === 'object' && img.image_url ? img.image_url : (typeof img === 'string' ? img : img));
    }
  }
  
  const carouselImageCount = carouselImages.length;
  
  // Determine post type for proper rendering
  const getPostType = () => {
    if (isCarousel) return 'carousel';
    if (isVideo) return 'video';
    if (content.post_type === 'image' || mediaUrl) return 'image';
    return 'text';
  };
  
  const postType = getPostType();
  
  // Helper functions for carousel navigation
  const nextCarouselImage = (e) => {
    e.stopPropagation();
    setCurrentCarouselIndex((prev) => (prev + 1) % carouselImageCount);
  };
  
  const prevCarouselImage = (e) => {
    e.stopPropagation();
    setCurrentCarouselIndex((prev) => (prev - 1 + carouselImageCount) % carouselImageCount);
  };
  
  const goToCarouselImage = (index) => {
    setCurrentCarouselIndex(index);
  };

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden hover:shadow-xl transition-all duration-300">
      {/* Media First (for minimal mode) */}
      {minimal && (isCarousel && carouselImages.length > 0 ? (
        <div className="relative group">
          <div className="relative overflow-hidden h-32 bg-gray-100 rounded-t-xl">
            <div
              className="flex transition-transform duration-300 ease-in-out h-full"
              style={{ transform: `translateX(-${currentCarouselIndex * 100}%)` }}
            >
              {carouselImages.map((img, index) => {
                const imageUrl = typeof img === 'string' ? img : (img.url || img);
                return (
                  <div key={index} className="min-w-full h-full flex-shrink-0">
                    <img
                      src={imageUrl}
                      alt={`Carousel image ${index + 1}`}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.target.style.display = 'none';
                      }}
                    />
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      ) : mediaUrl && (
        <div className="relative group h-32 bg-gray-100 rounded-t-xl overflow-hidden">
          {isVideo ? (
            <video
              src={mediaUrl}
              className="w-full h-full object-cover"
              controls={false}
              preload="metadata"
              muted
              playsInline
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
          ) : (
            <img
              src={mediaUrl}
              alt="Content media"
              className="w-full h-full object-cover"
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
          )}
        </div>
      ))}

      {/* Header */}
      <div className={`${minimal ? 'bg-white border-b border-gray-100' : `bg-gradient-to-r ${getPlatformColor(platform)}`} p-4 ${minimal ? 'text-gray-900' : 'text-white'}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3 flex-1 min-w-0">
            {!minimal && <span className="text-2xl flex-shrink-0">{getPlatformIcon(platform)}</span>}
            <div className="flex-1 min-w-0">
              <h3 className={`${minimal ? 'font-normal text-sm' : 'font-semibold text-lg'} truncate overflow-hidden whitespace-nowrap text-ellipsis`}>{title}</h3>
              {!minimal && (
                <div className="flex items-center space-x-2 text-sm opacity-90">
                  {getContentTypeIcon(contentType)}
                  <span className="capitalize">{contentType}</span>
                  <span>•</span>
                  <span className="capitalize">{platform}</span>
                </div>
              )}
              {minimal && (
                <div className="flex items-center space-x-2 text-xs text-gray-600 mt-1">
                  <span className="capitalize">{contentType}</span>
                  <span>•</span>
                  <span className="capitalize">{platform}</span>
                </div>
              )}
            </div>
          </div>
          {!minimal && (
            <div className="flex items-center space-x-2">
              <button
                onClick={handleCopy}
                className="p-2 bg-white/20 rounded-lg hover:bg-white/30 transition-colors"
                title="Copy content"
              >
                {copied ? (
                  <span className="text-xs">✓</span>
                ) : (
                  <Copy className="w-4 h-4" />
                )}
              </button>
              {onEdit && (
                <button
                  onClick={() => onEdit(content)}
                  className="p-2 bg-white/20 rounded-lg hover:bg-white/30 transition-colors"
                  title="Edit content"
                >
                  <Edit className="w-4 h-4" />
                </button>
              )}
              {onPreview && (
                <button
                  onClick={() => onPreview(content)}
                  className="p-2 bg-white/20 rounded-lg hover:bg-white/30 transition-colors"
                  title="Preview content"
                >
                  <Eye className="w-4 h-4" />
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Media Preview - Only for non-minimal mode */}
      {!minimal && (isCarousel && carouselImages.length > 0 ? (
        <div className="relative group">
          {/* Carousel Slider */}
          <div className="relative overflow-hidden h-64 bg-gray-100">
            <div
              className="flex transition-transform duration-300 ease-in-out h-full"
              style={{ transform: `translateX(-${currentCarouselIndex * 100}%)` }}
            >
              {carouselImages.map((img, index) => {
                const imageUrl = typeof img === 'string' ? img : (img.url || img);
                return (
                  <div key={index} className="min-w-full h-full flex-shrink-0">
                    <img
                      src={imageUrl}
                      alt={`Carousel image ${index + 1}`}
                      className="w-full h-full object-cover"
                      onError={(e) => {
                        e.target.style.display = 'none';
                      }}
                    />
                  </div>
                );
              })}
            </div>

            {/* Navigation Arrows */}
            {carouselImageCount > 1 && (
              <>
                <button
                  onClick={prevCarouselImage}
                  className="absolute left-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 text-white p-2 rounded-full transition-all opacity-0 group-hover:opacity-100"
                  aria-label="Previous image"
                >
                  <ChevronLeft className="w-5 h-5" />
                </button>
                <button
                  onClick={nextCarouselImage}
                  className="absolute right-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 text-white p-2 rounded-full transition-all opacity-0 group-hover:opacity-100"
                  aria-label="Next image"
                >
                  <ChevronRight className="w-5 h-5" />
                </button>
              </>
            )}

            {/* Image Counter Badge */}
            <div className="absolute top-2 right-2 bg-black/50 text-white px-2 py-1 rounded text-xs flex items-center gap-1">
              <Layers className="w-3 h-3" />
              <span>{currentCarouselIndex + 1}/{carouselImageCount}</span>
            </div>

            {/* Carousel Indicator Dots - Enhanced visibility */}
            {carouselImageCount > 1 && (
              <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-2 z-10">
                {carouselImages.map((_, index) => (
                  <button
                    key={index}
                    onClick={(e) => {
                      e.stopPropagation();
                      goToCarouselImage(index);
                    }}
                    className={`rounded-full transition-all duration-300 ${
                      index === currentCarouselIndex
                        ? 'bg-white w-8 h-2 shadow-lg'
                        : 'bg-white/60 hover:bg-white/80 w-2 h-2'
                    }`}
                    aria-label={`Go to image ${index + 1}`}
                    title={`Image ${index + 1} of ${carouselImageCount}`}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      ) : mediaUrl && (
        <div className="relative group cursor-pointer" onClick={() => onPreview && onPreview(content)}>
          {isVideo ? (
            <video
              src={mediaUrl}
              className="w-full h-48 object-cover"
              controls={false}
              preload="metadata"
              muted
              playsInline
              onError={(e) => {
                e.target.style.display = 'none';
              }}
            />
          ) : (
          <img
            src={mediaUrl}
            alt="Content media"
            className="w-full h-48 object-cover"
            onError={(e) => {
              e.target.style.display = 'none';
            }}
          />
          )}
          {isVideo && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/20 group-hover:bg-black/30 transition-colors">
              <div className="bg-white/90 rounded-full p-3 shadow-lg group-hover:scale-110 transition-transform">
                <Play className="w-6 h-6 text-purple-600 fill-purple-600" />
              </div>
            </div>
          )}
          <div className="absolute top-2 right-2 bg-black/50 text-white px-2 py-1 rounded text-xs flex items-center gap-1">
            {isVideo ? (
              <>
                <Video className="w-3 h-3" />
                <span>Video</span>
              </>
            ) : (
              <>
                <ImageIcon className="w-3 h-3" />
                <span>Image</span>
              </>
            )}
          </div>
        </div>
      ))}

      {/* Content - Hidden in minimal mode */}
      {!minimal && (
        <div className="p-4">
          <div className="space-y-3">
            {/* Handle different content types */}
            {contentType?.toLowerCase() === 'email' && content.email_subject && content.email_body ? (
              <div className="space-y-3">
                <div>
                  <h4 className="font-semibold text-gray-900 mb-2">📧 Subject:</h4>
                  <div className="text-gray-800 bg-gray-50 p-3 rounded-lg border-l-4 border-blue-400">
                    {content.email_subject}
                  </div>
                </div>
                <div>
                  <h4 className="font-semibold text-gray-900 mb-2">📝 Email Body:</h4>
                  <div className="text-gray-800 leading-relaxed">
                    {showFullContent ? content.email_body : content.email_body.substring(0, 200)}
                    {content.email_body.length > 200 && (
                      <button
                        onClick={() => setShowFullContent(!showFullContent)}
                        className="ml-2 text-pink-500 hover:text-pink-600 font-medium"
                      >
                        {showFullContent ? 'Show less' : '...Show more'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ) : (contentType?.toLowerCase() === 'short video' || contentType?.toLowerCase() === 'long video') && content.short_video_script || content.long_video_script ? (
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">🎬 Video Script:</h4>
                <div className="text-gray-800 leading-relaxed bg-gray-50 p-3 rounded-lg border-l-4 border-purple-400">
                  {showFullContent ? (content.short_video_script || content.long_video_script) : (content.short_video_script || content.long_video_script).substring(0, 200)}
                  {(content.short_video_script || content.long_video_script).length > 200 && (
                    <button
                      onClick={() => setShowFullContent(!showFullContent)}
                      className="ml-2 text-pink-500 hover:text-pink-600 font-medium"
                    >
                      {showFullContent ? 'Show less' : '...Show more'}
                    </button>
                  )}
                </div>
              </div>
            ) : contentType?.toLowerCase() === 'message' && content.message ? (
              <div>
                <h4 className="font-semibold text-gray-900 mb-2">💬 Message:</h4>
                <div className="text-gray-800 leading-relaxed bg-gray-50 p-3 rounded-lg border-l-4 border-green-400">
                  {content.message}
                </div>
              </div>
            ) : (
              <div className="text-gray-800 leading-relaxed">
                {showFullContent ? contentText : contentText.substring(0, 200)}
                {contentText.length > 200 && (
                  <button
                    onClick={() => setShowFullContent(!showFullContent)}
                    className="ml-2 text-pink-500 hover:text-pink-600 font-medium"
                  >
                    {showFullContent ? 'Show less' : '...Show more'}
                  </button>
                )}
              </div>
            )}

            {/* Call to Action */}
            {content.call_to_action && (
              <div className="bg-blue-50 border-l-4 border-blue-400 p-3 rounded-r-lg">
                <p className="text-sm text-blue-800 font-medium">
                  💬 {content.call_to_action}
                </p>
              </div>
            )}

            {/* Engagement Hooks */}
            {content.engagement_hooks && (
              <div className="bg-green-50 border-l-4 border-green-400 p-3 rounded-r-lg">
                <p className="text-sm text-green-800 font-medium">
                  🎯 {content.engagement_hooks}
                </p>
              </div>
            )}

            {/* Image Caption */}
            {content.image_caption && (
              <div className="bg-gray-50 border-l-4 border-gray-400 p-3 rounded-r-lg">
                <p className="text-sm text-gray-700 italic">
                  📷 {content.image_caption}
                </p>
              </div>
            )}

            {/* Visual Elements */}
            {content.visual_elements && content.visual_elements.length > 0 && (
              <div className="bg-purple-50 border-l-4 border-purple-400 p-3 rounded-r-lg">
                <p className="text-sm text-purple-800 font-medium mb-2">
                  🎨 Visual Elements:
                </p>
                <div className="flex flex-wrap gap-1">
                  {content.visual_elements.map((element, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs"
                    >
                      {element}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Hashtags */}
            {hashtags && hashtags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {hashtags.map((tag, index) => (
                  <span
                    key={index}
                    className="inline-flex items-center px-2 py-1 bg-pink-100 text-pink-700 rounded-full text-xs font-medium"
                  >
                    <Hash className="w-3 h-3 mr-1" />
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Footer - Hidden in minimal mode */}
      {!minimal && (
        <div className="px-4 py-3 bg-gray-50 border-t border-gray-200">
          <div className="flex items-center justify-between text-sm text-gray-500">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-1">
                <Heart className="w-4 h-4" />
                <span>0</span>
              </div>
              <div className="flex items-center space-x-1">
                <MessageCircle className="w-4 h-4" />
                <span>0</span>
              </div>
              <div className="flex items-center space-x-1">
                <Share className="w-4 h-4" />
                <span>0</span>
              </div>
            </div>
            <div className="flex items-center space-x-1">
              <Calendar className="w-4 h-4" />
              <span>Draft</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ContentCard;
