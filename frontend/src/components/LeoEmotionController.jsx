import React, { useState, useEffect } from 'react';
import { motion, useAnimation } from 'framer-motion';

export const LeoEmotionController = () => {
  const [emotion, setEmotion] = useState('neutral');
  const [isBlinking, setIsBlinking] = useState(false);
  const [mouthShape, setMouthShape] = useState('neutral');
  const controls = useAnimation();

  const emotions = {
    happy: {
      eyeScale: 1.1,
      mouthShape: 'smile',
      colorShift: '#ffeb3b', // Yellow tint
      rotation: 5,
      scale: 1.05
    },
    sad: {
      eyeScale: 0.9,
      mouthShape: 'frown',
      colorShift: '#2196f3', // Blue tint
      rotation: -5,
      scale: 0.95
    },
    excited: {
      eyeScale: 1.2,
      mouthShape: 'open',
      colorShift: '#ff5722', // Orange tint
      rotation: 0,
      scale: 1.1,
      wiggle: true
    },
    neutral: {
      eyeScale: 1,
      mouthShape: 'neutral',
      colorShift: '#ffffff',
      rotation: 0,
      scale: 1
    }
  };

  // Auto blink
  useEffect(() => {
    const blinkTimer = setInterval(() => {
      setIsBlinking(true);
      setTimeout(() => setIsBlinking(false), 150);
    }, 2500 + Math.random() * 1500);

    return () => clearInterval(blinkTimer);
  }, []);

  // Emotion transition
  useEffect(() => {
    const currentEmotion = emotions[emotion];
    controls.start({
      rotate: currentEmotion.rotation,
      scale: currentEmotion.scale,
      transition: {
        duration: 0.5,
        ease: "easeInOut"
      }
    });
    setMouthShape(currentEmotion.mouthShape);
  }, [emotion, controls]);

  return (
    <div className="flex flex-col items-center space-y-6 p-8">
      <motion.div
        animate={controls}
        className="relative"
      >
        {/* Animated background glow */}
        <motion.div
          className="absolute inset-0 rounded-full blur-xl opacity-50"
          animate={{
            backgroundColor: emotions[emotion].colorShift,
            scale: emotions[emotion].wiggle ? [1, 1.2, 1] : 1,
          }}
          transition={{
            backgroundColor: { duration: 0.3 },
            scale: { duration: 0.8, repeat: emotions[emotion].wiggle ? Infinity : 0 }
          }}
        />

        {/* Leo SVG with emotion-based animations */}
        <motion.svg
          viewBox="0 0 421.55 358.27"
          className="w-80 h-80 relative z-10"
          style={{
            filter: `drop-shadow(0 0 20px ${emotions[emotion].colorShift}40)`
          }}
        >
          <defs>
            {/* Animated gradients */}
            <motion.linearGradient
              id="faceGradient"
              animate={{
                x1: emotion === 'excited' ? [0, 100, 0] : 78.51,
                y1: emotion === 'sad' ? [0, 100, 0] : 249.8,
              }}
              transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            >
              <stop offset="0" stopColor="#dc298d"/>
              <stop offset="1" stopColor="#8b2ed8"/>
            </motion.linearGradient>
          </defs>

          <g isolation="isolate">
            {/* Face with animated gradient */}
            <motion.g id="Face">
              <ellipse
                cx="214.31"
                cy="252.65"
                rx="165.18"
                ry="74.18"
                fill="url(#faceGradient)"
              />

              {/* Breathing animation */}
              <motion.ellipse
                cx="214.31"
                cy="252.65"
                rx="165.18"
                ry="74.18"
                fill="url(#faceGradient)"
                animate={{
                  scale: [1, 1.02, 1],
                }}
                transition={{
                  duration: 3,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              />
            </motion.g>

            {/* Eyes with emotion scaling */}
            <motion.g id="Right_Eye">
              <motion.circle
                cx="284.39"
                cy="224.7"
                r="7.57"
                fill="#fff"
                animate={{
                  scaleY: isBlinking ? 0.1 : emotions[emotion].eyeScale,
                  scaleX: emotions[emotion].eyeScale,
                }}
                transition={{
                  scaleY: { duration: isBlinking ? 0.1 : 0.3 },
                  scaleX: { duration: 0.3 }
                }}
              />
            </motion.g>

            <motion.g id="Left_Eye">
              <motion.circle
                cx="160.65"
                cy="224.7"
                r="7.57"
                fill="#fff"
                animate={{
                  scaleY: isBlinking ? 0.1 : emotions[emotion].eyeScale,
                  scaleX: emotions[emotion].eyeScale,
                }}
                transition={{
                  scaleY: { duration: isBlinking ? 0.1 : 0.3 },
                  scaleX: { duration: 0.3 }
                }}
              />
            </motion.g>

            {/* Mouth shapes based on emotion */}
            {mouthShape === 'smile' && (
              <motion.path
                d="M261.06,271.36c-5.35-11.61-11.35-15.64-16.26-16.93-7.61-2-10.55,3.25-22.5,3.25-13.3,0-17.4-6.09-25.28-3.33-4.02,1.41-9.09,5.2-13.04,16.02,3.86,4.73,11.81,12.95,23.55,15.84,6.76,1.66,14.06,1.37,16.48,1.29,1.52-.05,6.73-.28,11.83-1.45,11.56-2.65,20.17-9.66,25.22-14.69Z"
                fill="#fff"
                initial={{ scale: 0.8, y: 10 }}
                animate={{ scale: 1, y: 0 }}
                transition={{ duration: 0.3, ease: "easeOut" }}
              />
            )}

            {mouthShape === 'frown' && (
              <motion.path
                d="M274.69,270.67c-4.42-5.23-11.54-11.93-21.76-14.83-10.46-2.97-13.95.94-31.73.69-19.09-.27-23.31-4.72-34.13-1.64-9.44,2.69-15.9,9.28-19.86,14.39,5.39,6.6,16.47,18.05,32.84,22.08,9.42,2.32,19.6,1.91,22.98,1.8,2.12-.07,9.38-.38,16.49-2.02,16.11-3.7,28.13-13.47,35.16-20.48Z"
                fill="#fff"
                initial={{ scale: 0.8, y: -10 }}
                animate={{ scale: 1, y: 0 }}
                transition={{ duration: 0.3, ease: "easeOut" }}
              />
            )}

            {mouthShape === 'open' && (
              <motion.path
                d="M221.03,235.29c-3.03,0-13.64-.25-14.92,16.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
                fill="#fff"
                animate={{
                  scale: [1, 1.2, 1],
                }}
                transition={{
                  duration: 0.5,
                  repeat: Infinity,
                  ease: "easeInOut"
                }}
              />
            )}
          </g>
        </motion.svg>
      </motion.div>

      {/* Emotion controls */}
      <div className="flex flex-wrap gap-2 justify-center">
        {Object.keys(emotions).map((emotionKey) => (
          <button
            key={emotionKey}
            onClick={() => setEmotion(emotionKey)}
            className={`px-4 py-2 rounded-full capitalize transition-colors ${
              emotion === emotionKey
                ? 'bg-blue-500 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            {emotionKey}
          </button>
        ))}
      </div>

      <div className="text-center">
        <p className="text-lg font-semibold capitalize">{emotion} Leo</p>
        <p className="text-sm text-gray-600">
          Click emotions to see different animations and expressions
        </p>
      </div>
    </div>
  );
};






