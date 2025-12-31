import React, { useState, useEffect, useRef } from 'react';
import { motion, useAnimation } from 'framer-motion';

export const LeoLipSync = () => {
  const [currentMouth, setCurrentMouth] = useState('BMP');
  const [isSpeaking, setIsSpeaking] = useState(false);
  const controls = useAnimation();
  const audioRef = useRef(null);

  // Phoneme to mouth shape mapping
  const phonemeMap = {
    'A': 'A',
    'E': 'E',
    'I': 'I',
    'O': 'O',
    'U': 'U',
    'R': 'R',
    'TH': 'TH',
    'CH': 'CH',
    'SH': 'SH',
    'L': 'L',
    'B': 'BMP',
    'M': 'BMP',
    'P': 'BMP',
    'Q': 'QW',
    'W': 'QW'
  };

  // Mouth shape components
  const mouthShapes = {
    A: (
      <motion.path
        d="M261.06,271.36c-5.35-11.61-11.35-15.64-16.26-16.93-7.61-2-10.55,3.25-22.5,3.25-13.3,0-17.4-6.09-25.28-3.33-4.02,1.41-9.09,5.2-13.04,16.02,3.86,4.73,11.81,12.95,23.55,15.84,6.76,1.66,14.06,1.37,16.48,1.29,1.52-.05,6.73-.28,11.83-1.45,11.56-2.65,20.17-9.66,25.22-14.69Z"
        fill="#fff"
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.1 }}
      />
    ),
    E: (
      <motion.path
        d="M274.11,258.67c-4.74.89-12.28,2.07-21.61,2.41-14.64.53-17.42-1.58-34.26-1.85-16.34-.26-18.72,1.65-32.15.56-9.7-.79-17.55-2.54-22.66-3.89,2.28,4.87,14.1,29.15,34.11,34.35,6.5,1.69,19.02,1.76,22,1.82,3.07.06,13.3.27,19.03-.64,17.9-2.84,30.21-22.69,35.53-32.76Z"
        fill="#fff"
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.1 }}
      />
    ),
    I: (
      <motion.path
        d="M221.03,245.29c-2.03,0-9.64-.25-10.92,12.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
        fill="#fff"
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.1 }}
      />
    ),
    O: (
      <motion.path
        d="M221.03,235.29c-3.03,0-13.64-.25-14.92,16.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
        fill="#fff"
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.1 }}
      />
    ),
    U: (
      <motion.path
        d="M221.03,240.29c-2.53,0-11.64-.25-12.92,14.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
        fill="#fff"
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.1 }}
      />
    ),
    R: (
      <motion.path
        d="M231.03,250.29c-2.03,0-8.64-.25-9.92,10.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
        fill="#fff"
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.1 }}
      />
    ),
    TH: (
      <motion.path
        d="M221.03,255.29c-1.03,0-5.64-.25-6.92,6.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
        fill="#fff"
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.1 }}
      />
    ),
    CH: (
      <motion.path
        d="M211.03,260.29c-0.53,0-3.64-.25-4.92,4.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
        fill="#fff"
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.1 }}
      />
    ),
    SH: (
      <motion.path
        d="M216.03,265.29c-0.83,0-4.64-.25-5.92,5.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
        fill="#fff"
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.1 }}
      />
    ),
    L: (
      <motion.path
        d="M226.03,252.29c-1.53,0-7.64-.25-8.92,8.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
        fill="#fff"
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.1 }}
      />
    ),
    BMP: (
      <motion.path
        d="M221.03,270.29c-0.03,0-0.64-.25-1.92,0.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
        fill="#fff"
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.1 }}
      />
    ),
    QW: (
      <motion.path
        d="M221.03,242.29c-2.73,0-12.64-.25-13.92,15.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
        fill="#fff"
        initial={{ scale: 0.9 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.1 }}
      />
    )
  };

  // Simulate lip sync with text
  const speakText = (text) => {
    if (isSpeaking) return;

    setIsSpeaking(true);
    const words = text.toUpperCase().split('');
    let index = 0;

    const speakInterval = setInterval(() => {
      if (index < words.length) {
        const char = words[index];
        const phoneme = phonemeMap[char] || 'BMP';
        setCurrentMouth(phoneme);

        // Add some randomness to timing
        const delay = Math.random() * 100 + 100; // 100-200ms
        setTimeout(() => index++, delay);
      } else {
        clearInterval(speakInterval);
        setTimeout(() => {
          setCurrentMouth('BMP');
          setIsSpeaking(false);
        }, 500);
      }
    }, 150);
  };

  // Head movement during speech
  useEffect(() => {
    if (isSpeaking) {
      controls.start({
        rotate: [0, 2, -2, 1, -1, 0],
        scale: [1, 1.02, 1],
        transition: {
          duration: 0.8,
          ease: "easeInOut"
        }
      });
    }
  }, [isSpeaking, controls]);

  return (
    <div className="flex flex-col items-center space-y-6 p-8">
      <motion.div
        animate={controls}
        className="relative"
      >
        <svg viewBox="0 0 421.55 358.27" className="w-80 h-80">
          <g isolation="isolate">
            {/* Face */}
            <ellipse cx="214.31" cy="252.65" rx="165.18" ry="74.18" fill="#003340"/>

            {/* Eyes */}
            <circle cx="284.39" cy="224.7" r="7.57" fill="#fff"/>
            <circle cx="160.65" cy="224.7" r="7.57" fill="#fff"/>

            {/* Animated Mouth */}
            <g id="Mouth">
              {mouthShapes[currentMouth] || mouthShapes.BMP}
            </g>

            {/* Simplified hair for demo */}
            <path d="M120.22,116.72S42.16,103.45,0,146.38c0,0,26.54-13.27,64.8-.78,38.25,12.49,95.23,28.89,131.93,8.59,36.69-20.3-3.12-22.64-5.47-22.64l-71.04-14.83Z" fill="#2e3045"/>
          </g>
        </svg>
      </motion.div>

      <div className="flex flex-col items-center space-y-4">
        <div className="flex flex-wrap gap-2 justify-center">
          <button
            onClick={() => speakText("HELLO")}
            disabled={isSpeaking}
            className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Say "HELLO"
          </button>
          <button
            onClick={() => speakText("HOW ARE YOU")}
            disabled={isSpeaking}
            className="px-6 py-3 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Say "HOW ARE YOU"
          </button>
          <button
            onClick={() => speakText("THANKS")}
            disabled={isSpeaking}
            className="px-6 py-3 bg-purple-500 text-white rounded-lg hover:bg-purple-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Say "THANKS"
          </button>
        </div>

        <div className="text-center">
          <p className="text-lg font-semibold">
            Lip Sync Demo
          </p>
          <p className="text-sm text-gray-600">
            Current mouth shape: <span className="font-mono">{currentMouth}</span>
          </p>
          <p className="text-sm text-gray-600">
            Status: <span className={isSpeaking ? "text-green-600" : "text-gray-600"}>
              {isSpeaking ? "Speaking..." : "Ready"}
            </span>
          </p>
        </div>
      </div>
    </div>
  );
};
