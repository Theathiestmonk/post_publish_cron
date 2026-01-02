import React, { useState, useEffect } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { HelmetProvider } from 'react-helmet-async'
// Emily Digital Marketing Agent - Main App Component
import Login from './components/Login'
import SignUp from './components/SignUp'
import ForgotPassword from './components/ForgotPassword'
import EmilyDashboard from './components/EmilyDashboard'
import ContentDashboard from './components/ContentDashboard'
import ContentCalendar from './components/ContentCalendar'
import SocialMediaDashboard from './components/SocialMediaDashboard'
import AnalyticsDashboard from './components/AnalyticsDashboard'
import CampaignsDashboard from './components/CampaignsDashboard'
import AdsDashboard from './components/AdsDashboard'
import BlogDashboard from './components/BlogDashboard'
import LeadsDashboard from './components/LeadsDashboard'
import CreatedContentDashboard from './components/CreatedContentDashboard'
import ATSNDashboard from './components/ATSNDashboard'
import PostSuggestionsDashboard from './components/PostSuggestionsDashboard'
import Chatbot from './components/Chatbot'
import Onboarding from './components/Onboarding'
import Profile from './components/Profile'
import GoogleCallback from './components/GoogleCallback'
import TokenExchangeHandler from './components/TokenExchangeHandler'
import SettingsDashboard from './components/SettingsDashboard'
import AdminDashboard from './components/AdminDashboard'
import AdminProtectedRoute from './components/AdminProtectedRoute'
import ErrorBoundary from './components/ErrorBoundary'
import LoadingBar from './components/LoadingBar'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import { NotificationProvider, useNotifications } from './contexts/NotificationContext'
import { ContentCacheProvider } from './contexts/ContentCacheContext'
import { SocialMediaCacheProvider } from './contexts/SocialMediaCacheContext'
import { onboardingAPI } from './services/onboarding'
import NotificationWindow from './components/NotificationWindow'
//  Components
import LandingPage from './pages/LandingPage.jsx'
import PrivacyPolicy from './pages/PrivacyPolicy.jsx'
import TermsAndConditions from './pages/TermsAndConditions.jsx'
import CancellationAndRefunds from './pages/CancellationAndRefunds.jsx'
import Shipping from './pages/Shipping.jsx'
import ContactUs from './pages/ContactUs.jsx'
import AddBlogPage from './pages/AddBlogPage.jsx'
import BlogListingPage from './pages/BlogListingPage.jsx'
import BlogDetailPage from './pages/BlogDetailPage.jsx'
import BlogProtectedRoute from './components/BlogProtectedRoute.jsx'
// Subscription Components
import SubscriptionSelector from './components/SubscriptionSelector'
import PaymentSuccess from './components/PaymentSuccess'
import MigrationBanner from './components/MigrationBanner'
import BillingDashboard from './components/BillingDashboard'
import { subscriptionAPI } from './services/subscription'

function ProtectedRoute({ children }) {
  const { isAuthenticated, user, loading } = useAuth()
  const [subscriptionStatus, setSubscriptionStatus] = useState(null)
  const [onboardingStatus, setOnboardingStatus] = useState(null)

  useEffect(() => {
    const checkUserStatus = async (retryCount = 0) => {
      if (isAuthenticated && user) {
        try {
          console.log('Checking subscription status for user:', user.id)
          // Check subscription status first
          const subResponse = await subscriptionAPI.getSubscriptionStatus()
          console.log('Subscription status response:', subResponse.data)
          setSubscriptionStatus(subResponse.data)
          
          // Only check onboarding if user has active subscription
          if (subResponse.data.has_active_subscription) {
            console.log('User has active subscription, checking onboarding status')
            const onboardingResponse = await onboardingAPI.getOnboardingStatus()
            setOnboardingStatus(onboardingResponse.data.onboarding_completed ? 'completed' : 'incomplete')
          } else {
            console.log('User does not have active subscription, redirecting to subscription page')
            setOnboardingStatus('subscription_required')
          }
        } catch (error) {
          console.error('Error checking user status:', error)
          // Only set as no subscription if it's a clear 404 or 403 error
          if (error.response?.status === 404 || error.response?.status === 403) {
            // User not found or forbidden - definitely no subscription
            setSubscriptionStatus({ has_active_subscription: false })
            setOnboardingStatus('subscription_required')
          } else {
            // For network errors, 500 errors, etc. - retry with exponential backoff
            // Don't assume no subscription on transient errors
            const maxRetries = 2
            if (retryCount < maxRetries) {
              const delay = Math.pow(2, retryCount) * 1000 // Exponential backoff: 1s, 2s
              console.log(`Network or server error, retrying in ${delay}ms... (attempt ${retryCount + 1}/${maxRetries + 1})`)
              setTimeout(() => {
                checkUserStatus(retryCount + 1)
              }, delay)
              // Retrying, don't do anything yet
              return
            } else {
              // Max retries reached - assume active to prevent false redirect
              // Set error flag but don't redirect
              console.log('Max retries reached, assuming active subscription to prevent false redirect')
              setSubscriptionStatus({ has_active_subscription: true, error: true })
              // Still check onboarding if we assume active
              try {
                const onboardingResponse = await onboardingAPI.getOnboardingStatus()
                setOnboardingStatus(onboardingResponse.data.onboarding_completed ? 'completed' : 'incomplete')
              } catch (onboardingError) {
                console.error('Error checking onboarding status:', onboardingError)
                setOnboardingStatus('completed') // Default to completed to prevent redirect
              }
            }
          }
        }
      }
    }

    checkUserStatus()
  }, [isAuthenticated, user])

  // Show loading while checking authentication
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    console.log('User not authenticated, redirecting to login')
    return <Navigate to="/login" />
  }

  // Check subscription status - only redirect if we've actually checked and confirmed no subscription
  // Also check that it's not an error state (where we assume active to prevent false redirects)
  if (subscriptionStatus !== null && !subscriptionStatus?.has_active_subscription && !subscriptionStatus?.error) {
    console.log('User does not have active subscription, redirecting to subscription page')
    return <Navigate to="/subscription" />
  }

  // Check onboarding status
  if (onboardingStatus === 'incomplete') {
    console.log('User onboarding incomplete, redirecting to onboarding')
    return <Navigate to="/onboarding" />
  }

  console.log('User authenticated with active subscription and completed onboarding')

  return (
    <>
      <MigrationBanner />
      {children}
    </>
  )
}

function AppContent() {
  const { notifications, removeNotification, markAsRead } = useNotifications()

  return (
    <Router>
      <Routes>
        {/*  Routes */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/privacy" element={<PrivacyPolicy />} />
        <Route path="/terms" element={<TermsAndConditions />} />
        <Route path="/cancellation-refunds" element={<CancellationAndRefunds />} />
        <Route path="/shipping" element={<Shipping />} />
        <Route path="/contact" element={<ContactUs />} />
        <Route 
          path="/add-blog" 
          element={
            <BlogProtectedRoute>
              <AddBlogPage />
            </BlogProtectedRoute>
          } 
        />
        <Route path="/blog" element={<BlogListingPage />} />
        <Route path="/blog/:slug" element={<BlogDetailPage />} />
        
        {/* App Routes */}
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<SignUp />} />
        <Route path="/reset-password" element={<ForgotPassword />} />
        
        {/* Subscription Routes */}
        <Route path="/subscription" element={<SubscriptionSelector />} />
        <Route path="/payment/success" element={<PaymentSuccess />} />
        <Route 
          path="/dashboard" 
          element={
            <ProtectedRoute>
              <EmilyDashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/emily" 
          element={
            <ProtectedRoute>
              <EmilyDashboard />
            </ProtectedRoute>
          } 
        />
        <Route
          path="/content"
          element={
            <ProtectedRoute>
              <ContentDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/created-content"
          element={
            <ProtectedRoute>
              <CreatedContentDashboard />
            </ProtectedRoute>
          }
        />
        <Route 
          path="/calendar" 
          element={
            <ProtectedRoute>
              <ContentCalendar />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/social" 
          element={
            <ProtectedRoute>
              <SocialMediaDashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/analytics" 
          element={
            <ProtectedRoute>
              <AnalyticsDashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/campaigns" 
          element={
            <ProtectedRoute>
              <CampaignsDashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/ads" 
          element={
            <ProtectedRoute>
              <AdsDashboard />
            </ProtectedRoute>
          } 
        />
        <Route
          path="/leads"
          element={
            <ProtectedRoute>
              <LeadsDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/post-suggestions"
          element={
            <ProtectedRoute>
              <PostSuggestionsDashboard />
            </ProtectedRoute>
          }
        />
        <Route 
          path="/blogs" 
          element={
            <ProtectedRoute>
              <BlogDashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/atsn" 
          element={
            <ProtectedRoute>
              <ATSNDashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/chatbot" 
          element={
            <ProtectedRoute>
              <Chatbot />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/onboarding" 
          element={<Onboarding />} 
        />
        <Route 
          path="/profile" 
          element={
            <ProtectedRoute>
              <Profile />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/google-callback" 
          element={<GoogleCallback />} 
        />
        <Route 
          path="/auth/callback" 
          element={<TokenExchangeHandler />} 
        />
        <Route 
          path="/billing" 
          element={
            <ProtectedRoute>
              <BillingDashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/settings" 
          element={
            <ProtectedRoute>
              <SettingsDashboard />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/admin" 
          element={
            <AdminProtectedRoute>
              <AdminDashboard />
            </AdminProtectedRoute>
          } 
        />
      </Routes>
      
      {/* Global Notification Window */}
      <NotificationWindow 
        notifications={notifications}
        onClose={removeNotification}
        onMarkAsRead={markAsRead}
      />
    </Router>
  )
}

function App() {
  return (
    <HelmetProvider>
      <ErrorBoundary>
        <AuthProvider>
          <NotificationProvider>
            <ContentCacheProvider>
              <SocialMediaCacheProvider>
                <AppContent />
              </SocialMediaCacheProvider>
            </ContentCacheProvider>
          </NotificationProvider>
        </AuthProvider>
      </ErrorBoundary>
    </HelmetProvider>
  )
}

export default App