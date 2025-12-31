import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';

// Phoneme to mouth shape mapping - comprehensive mapping
const PHONEME_MAP = {
  // Vowels
  'A': 'mouthA',
  'E': 'mouthE',
  'I': 'mouthI',
  'O': 'mouthO',
  'U': 'mouthU',

  // Consonants - mapped to closest vowel sounds
  'B': 'mouthBMP',
  'M': 'mouthBMP',
  'P': 'mouthBMP',
  'D': 'mouthE',
  'T': 'mouthE',
  'K': 'mouthE',
  'G': 'mouthE',
  'F': 'mouthU',
  'V': 'mouthU',
  'TH': 'mouthTH',
  'S': 'mouthE',
  'Z': 'mouthE',
  'SH': 'mouthSH',
  'CH': 'mouthCH',
  'J': 'mouthE',
  'L': 'mouthL',
  'R': 'mouthR',
  'W': 'mouthQW',
  'Q': 'mouthQW',
  'Y': 'mouthE',
  'H': 'mouthA',
  'N': 'mouthE',
  'NG': 'mouthE',

  // Numbers and punctuation (neutral mouth)
  '0': 'neutral',
  '1': 'neutral',
  '2': 'neutral',
  '3': 'neutral',
  '4': 'neutral',
  '5': 'neutral',
  '6': 'neutral',
  '7': 'neutral',
  '8': 'neutral',
  '9': 'neutral',
  '.': 'neutral',
  ',': 'neutral',
  '!': 'neutral',
  '?': 'neutral',
  ':': 'neutral',
  ';': 'neutral',
  '-': 'neutral',
  '_': 'neutral',
  ' ': 'neutral'
};

// Mouth shape components using the actual Leo SVG mouth paths
const MouthShapes = {
  mouthA: (
    <motion.path
      d="M261.06,271.36c-5.35-11.61-11.35-15.64-16.26-16.93-7.61-2-10.55,3.25-22.5,3.25-13.3,0-17.4-6.09-25.28-3.33-4.02,1.41-9.09,5.2-13.04,16.02,3.86,4.73,11.81,12.95,23.55,15.84,6.76,1.66,14.06,1.37,16.48,1.29,1.52-.05,6.73-.28,11.83-1.45,11.56-2.65,20.17-9.66,25.22-14.69Z"
      fill="#fff"
      initial={{ scale: 0.95 }}
      animate={{ scale: 1 }}
      transition={{ duration: 0.08 }}
    />
  ),
  mouthE: (
    <motion.path
      d="M274.11,258.67c-4.74.89-12.28,2.07-21.61,2.41-14.64.53-17.42-1.58-34.26-1.85-16.34-.26-18.72,1.65-32.15.56-9.7-.79-17.55-2.54-22.66-3.89,2.28,4.87,14.1,29.15,34.11,34.35,6.5,1.69,19.02,1.76,22,1.82,3.07.06,13.3.27,19.03-.64,17.9-2.84,30.21-22.69,35.53-32.76Z"
      fill="#fff"
      initial={{ scale: 0.95 }}
      animate={{ scale: 1 }}
      transition={{ duration: 0.08 }}
    />
  ),
  mouthI: (
    <motion.path
      d="M261.06,271.36c-5.35-11.61-11.35-15.64-16.26-16.93-7.61-2-10.55,3.25-22.5,3.25-13.3,0-17.4-6.09-25.28-3.33-4.02,1.41-9.09,5.2-13.04,16.02,3.86,4.73,11.81,12.95,23.55,15.84,6.76,1.66,14.06,1.37,16.48,1.29,1.52-.05,6.73-.28,11.83-1.45,11.56-2.65,20.17-9.66,25.22-14.69Z"
      fill="#fff"
      initial={{ scale: 0.95 }}
      animate={{ scale: 1 }}
      transition={{ duration: 0.08 }}
    />
  ),
  mouthO: (
    <motion.path
      d="M221.03,235.29c-3.03,0-13.64-.25-14.92,16.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
      fill="#fff"
      initial={{ scale: 0.95 }}
      animate={{ scale: 1 }}
      transition={{ duration: 0.08 }}
    />
  ),
  mouthU: (
    <motion.path
      d="M274.2,276.97c-2.38-4.84-8.44-15.5-20.94-23.63-3.52-2.29-14.8-9.09-30.91-9.56-5.38-.16-17.77-.35-30.72,7.39-13.47,8.05-19.42,19.84-21.44,24.42,6.43,4.29,14.66,8.71,24.69,11.91,4.95,1.58,13.93,4.37,26.03,4.52,9.92.12,17.31-1.59,22.77-2.89,7.59-1.81,18.45-5.24,30.52-12.16Z"
      fill="#fff"
      initial={{ scale: 0.95 }}
      animate={{ scale: 1 }}
      transition={{ duration: 0.08 }}
    />
  ),
  mouthR: (
    <motion.path
      d="M162.46,269.13c4.94,5.84,8.23,10.69,19.65,13.94,11.68,3.32,15.58-1.05,35.44-.77,21.32.3,26.04,5.27,38.11,1.83,10.55-3,18.01-10.2,22.43-15.91-10.97-9.48-20.72-12.52-28.05-13.36-13.05-1.49-16.25,4.25-33.26,3.98-16.2-.26-19.83-5.58-31.27-3.43-10.59,1.99-18.27,8.57-23.06,13.74Z"
      fill="#fff"
      initial={{ scale: 0.95 }}
      animate={{ scale: 1 }}
      transition={{ duration: 0.08 }}
    />
  ),
  mouthTH: (
    <motion.path
      d="M275.42,274.58c-4.28-5.06-11.17-11.55-21.06-14.36-10.13-2.88-13.5.91-30.72.67-18.48-.26-22.57-4.56-33.03-1.58-9.14,2.6-15.39,8.98-19.22,13.93,5.22,6.39,15.94,17.48,31.79,21.37,9.12,2.24,18.97,1.85,22.25,1.75,2.05-.07,9.08-.37,15.96-1.95,15.6-3.58,27.23-13.04,34.03-19.83Z"
      fill="#fff"
      initial={{ scale: 0.95 }}
      animate={{ scale: 1 }}
      transition={{ duration: 0.08 }}
    />
  ),
  mouthCH: (
    <motion.path
      d="M282.26,271.31c-4.71-5.57-7.85-10.2-18.74-13.29-11.14-3.16-14.86,1-33.81.74-20.34-.28-24.84-5.02-36.36-1.74-10.06,2.87-17.18,9.73-21.4,15.18,10.12,5.81,17.59,8.7,24.23,10.19,9.17,2.07,16.3,2.1,30.56,2.15,13.13.05,19.7.08,27.44-1.6,11.83-2.57,22.1-7.69,28.08-11.61Z"
      fill="#fff"
      initial={{ scale: 0.95 }}
      animate={{ scale: 1 }}
      transition={{ duration: 0.08 }}
    />
  ),
  mouthSH: (
    <motion.path
      d="M282.26,271.31c-4.71-5.57-7.85-10.2-18.74-13.29-11.14-3.16-14.86,1-33.81.74-20.34-.28-24.84-5.02-36.36-1.74-10.06,2.87-17.18,9.73-21.4,15.18,10.12,5.81,17.59,8.7,24.23,10.19,9.17,2.07,16.3,2.1,30.56,2.15,13.13.05,19.7.08,27.44-1.6,11.83-2.57,22.1-7.69,28.08-11.61Z"
      fill="#fff"
      initial={{ scale: 0.95 }}
      animate={{ scale: 1 }}
      transition={{ duration: 0.08 }}
    />
  ),
  mouthL: (
    <motion.path
      d="M268.19,277.07c-2.13-7.09-7.38-20.17-19.68-26.28-5.67-2.82-12.06-3.04-24.84-3.49-14.71-.52-22.06-.78-28.54,2.26-12.82,6-18.11,19.83-20.07,26.31,4.67,5.72,14.27,15.64,28.45,19.13,8.16,2.01,16.98,1.66,19.92,1.56,1.84-.06,8.13-.33,14.29-1.75,13.96-3.21,24.37-11.67,30.47-17.75Z"
      fill="#fff"
      initial={{ scale: 0.95 }}
      animate={{ scale: 1 }}
      transition={{ duration: 0.08 }}
    />
  ),
  mouthBMP: (
    <motion.path
      d="M167.77,270.72c2.33.26,4.67.44,7,.57,2.58.14,5.49.17,6.97.12,4.7-.1,8.27-.85,13.87-1.5,4.67-.55,9.39-.82,14.07-1.16,4.69-.34,9.38-.65,14.08-.9,2.35-.12,4.71-.2,7.07-.21,1.18,0,2.36.04,3.54.07,1.18.04,2.36.11,3.53.17,4.71.27,9.4.69,14.07,1.28,4.64.59,9.33,1.34,13.94,2.08,2.32.37,4.63.74,6.94,1.07,2.49.4,4.79.59,6.97.67l.02.2c-2.37.24-4.34.32-7.08.15-2.67-.14-5.1-.33-7.05-.52-4.67-.46-3.21-.3-14-1.51-4.65-.53-9.29-1.1-13.95-1.52-4.66-.41-9.31-.7-13.99-.82-4.68-.13-9.38-.02-14.04.44-2.33.24-4.65.56-6.96.95-2.31.39-4.61.82-6.92,1.22-8.02,1.39-11.24,1.45-14.11,1.4-2.03-.03-5.01-.29-7.08-.62-2.34-.35-4.66-.8-6.93-1.44l.04-.2Z"
      fill="#fff"
      initial={{ scale: 0.95 }}
      animate={{ scale: 1 }}
      transition={{ duration: 0.08 }}
    />
  ),
  mouthQW: (
    <motion.path
      d="M256.03,265.75c-1.85-3.51-5.43-9.21-11.77-14.25-3.81-3.03-11.31-8.99-22.41-9.12-11.98-.15-20.14,6.59-22.42,8.53-5.9,5.02-8.76,10.79-10.07,13.98-.03,2.23-.04,22.74,15.23,33.22,1.82,1.25,7.75,5.2,16.29,5.56,11.54.48,19.59-5.95,21.99-7.94,13.11-10.81,13.19-27.5,13.16-29.98Z"
      fill="#fff"
      initial={{ scale: 0.95 }}
      animate={{ scale: 1 }}
      transition={{ duration: 0.08 }}
    />
  ),
  neutral: (
    <motion.path
      d="M221.03,235.29c-3.03,0-13.64-.25-14.92,16.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
      fill="#fff"
      initial={{ scale: 0.95 }}
      animate={{ scale: 1 }}
      transition={{ duration: 0.08 }}
    />
  )
};

// Text to phonemes converter
const textToPhonemes = (text) => {
  if (!text) return [];

  const upperText = text.toUpperCase();
  const phonemes = [];

  for (let i = 0; i < upperText.length; i++) {
    const char = upperText[i];
    const nextChar = upperText[i + 1] || '';

    // Handle digraphs first
    if (char === 'T' && nextChar === 'H') {
      phonemes.push('TH');
      i++; // Skip next character
    } else if (char === 'S' && nextChar === 'H') {
      phonemes.push('SH');
      i++;
    } else if (char === 'C' && nextChar === 'H') {
      phonemes.push('CH');
      i++;
    } else if (char === 'N' && nextChar === 'G') {
      phonemes.push('NG');
      i++;
    } else {
      // Handle single characters
      phonemes.push(PHONEME_MAP[char] || 'neutral');
    }
  }

  return phonemes;
};

// Lip sync timing - characters per second for natural speech
const CHARS_PER_SECOND = 15;
const BASE_DURATION = 1000 / CHARS_PER_SECOND; // ~67ms per character

const LeoLipSyncChat = ({
  text,
  isSpeaking = false,
  agentName = 'leo',
  onAnimationComplete = () => {},
  avatarMode = false
}) => {
  const [currentMouth, setCurrentMouth] = useState('neutral');
  const [isBlinking, setIsBlinking] = useState(false);
  const animationRef = useRef(null);

  // Text to phonemes converter
  const textToPhonemes = (text) => {
    if (!text) return [];

    const upperText = text.toUpperCase();
    const phonemes = [];

    for (let i = 0; i < upperText.length; i++) {
      const char = upperText[i];
      const nextChar = upperText[i + 1] || '';

      // Handle digraphs first
      if (char === 'T' && nextChar === 'H') {
        phonemes.push('TH');
        i++; // Skip next character
      } else if (char === 'S' && nextChar === 'H') {
        phonemes.push('SH');
        i++;
      } else if (char === 'C' && nextChar === 'H') {
        phonemes.push('CH');
        i++;
      } else if (char === 'N' && nextChar === 'G') {
        phonemes.push('NG');
        i++;
      } else {
        // Handle single characters
        const PHONEME_MAP = {
          'A': 'mouthA', 'E': 'mouthE', 'I': 'mouthI', 'O': 'mouthR', 'U': 'mouthU',
          'B': 'mouthBMP', 'M': 'mouthBMP', 'P': 'mouthBMP',
          'D': 'mouthE', 'T': 'mouthE', 'K': 'mouthE', 'G': 'mouthE',
          'F': 'mouthU', 'V': 'mouthU', 'TH': 'mouthTH', 'S': 'mouthE', 'Z': 'mouthE',
          'SH': 'mouthSH', 'CH': 'mouthCH', 'J': 'mouthE', 'L': 'mouthL', 'R': 'mouthR',
          'W': 'mouthQW', 'Q': 'mouthQW', 'Y': 'mouthE', 'H': 'mouthA', 'N': 'mouthE'
        };
        phonemes.push(PHONEME_MAP[char] || 'neutral');
      }
    }
    return phonemes;
  };

  // Mouth shapes
  const MouthShapes = {
    mouthA: <path d="M261.06,271.36c-5.35-11.61-11.35-15.64-16.26-16.93-7.61-2-10.55,3.25-22.5,3.25-13.3,0-17.4-6.09-25.28-3.33-4.02,1.41-9.09,5.2-13.04,16.02,3.86,4.73,11.81,12.95,23.55,15.84,6.76,1.66,14.06,1.37,16.48,1.29,1.52-.05,6.73-.28,11.83-1.45,11.56-2.65,20.17-9.66,25.22-14.69Z" fill="#fff"/>,
    mouthE: <path d="M274.11,258.67c-4.74.89-12.28,2.07-21.61,2.41-14.64.53-17.42-1.58-34.26-1.85-16.34-.26-18.72,1.65-32.15.56-9.7-.79-17.55-2.54-22.66-3.89,2.28,4.87,14.1,29.15,34.11,34.35,6.5,1.69,19.02,1.76,22,1.82,3.07.06,13.3.27,19.03-.64,17.9-2.84,30.21-22.69,35.53-32.76Z" fill="#fff"/>,
    mouthO: <path d="M221.03,235.29c-3.03,0-13.64-.25-14.92,16.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z" fill="#fff"/>,
    neutral: <path d="M274.11,258.67c-4.74.89-12.28,2.07-21.61,2.41-14.64.53-17.42-1.58-34.26-1.85-16.34-.26-18.72,1.65-32.15.56-9.7-.79-17.55-2.54-22.66-3.89,2.28,4.87,14.1,29.15,34.11,34.35,6.5,1.69,19.02,1.76,22,1.82,3.07.06,13.3.27,19.03-.64,17.9-2.84,30.21-22.69,35.53-32.76Z" fill="#fff"/>
  };

  // Lip-sync animation effect
  useEffect(() => {
    if (!text || !isSpeaking) {
      setCurrentMouth('neutral');
      return;
    }

    const phonemes = textToPhonemes(text);
    let currentIndex = 0;
    const BASE_DURATION = 67; // ~67ms per character

    const animateNextPhoneme = () => {
      if (currentIndex < phonemes.length) {
        const phoneme = phonemes[currentIndex];
        setCurrentMouth(phoneme);

        let duration = BASE_DURATION;
        if (phoneme === 'neutral') duration = BASE_DURATION * 0.8;
        if (['mouthBMP', 'mouthQW'].includes(phoneme)) duration = BASE_DURATION * 1.5;

        animationRef.current = setTimeout(() => {
          currentIndex++;
          animateNextPhoneme();
        }, duration);
      } else {
        setCurrentMouth('neutral');
        onAnimationComplete();
      }
    };

    animateNextPhoneme();

    return () => {
      if (animationRef.current) {
        clearTimeout(animationRef.current);
      }
    };
  }, [text, isSpeaking, onAnimationComplete]);

  // Eye blinking effect
  useEffect(() => {
    const blinkInterval = setInterval(() => {
      setIsBlinking(true);
      setTimeout(() => setIsBlinking(false), 150);
    }, 2500 + Math.random() * 1500); // Random blink timing

    return () => clearInterval(blinkInterval);
  }, []);

  return (
    <div className={`${avatarMode ? 'w-8 h-8' : 'w-32 h-32 bg-gray-100 border-2 border-gray-300 rounded-lg'} flex items-center justify-center relative`}>
      {/* Leo Character SVG */}
      <svg viewBox="0 0 421.55 358.27" className="w-full h-full absolute inset-0">
        <defs>
          <linearGradient id="linear-gradient" x1="350.54" y1="256.96" x2="369.13" y2="256.96" gradientUnits="userSpaceOnUse">
            <stop offset="0" stop-color="#dc298d"/>
            <stop offset="1" stop-color="#8b2ed8"/>
          </linearGradient>
          <linearGradient id="linear-gradient-2" x1="59.53" y1="257.4" x2="79.57" y2="257.4" xlinkHref="#linear-gradient"/>
          <linearGradient id="linear-gradient-3" x1="78.51" y1="249.8" x2="350.11" y2="249.8" xlinkHref="#linear-gradient"/>
        </defs>
        <g isolation="isolate">
          <motion.g
            id="Hair"
            animate={{
              rotate: [0, 1, -1, 0],
              scale: [1, 1.02, 0.98, 1],
            }}
            transition={{
              duration: 3,
              repeat: Infinity,
              ease: "easeInOut"
            }}
          >
            <g id="Hair-2" data-name="Hair">
              <g>
                <path d="M120.22,116.72S42.16,103.45,0,146.38c0,0,26.54-13.27,64.8-.78,38.25,12.49,95.23,28.89,131.93,8.59,36.69-20.3-3.12-22.64-5.47-22.64l-71.04-14.83Z" fill="#2e3045"/>
                <path d="M64.8,145.6c38.25,12.49,95.23,28.89,131.93,8.59,3.79-2.1,6.72-3.99,9.01-5.72-7.41-3.87-18.43-6.33-30.87,1.82-22.64,14.83-78.84-3.9-117.87-12.49-27.84-6.13-45.75,2.05-53.73,7.24,8.18-3.03,31.15-9.35,61.53.57Z" fill="#1c1a36"/>
              </g>
              <g>
                <path d="M311.84,161.09s-42.42,20.17-111.02,18.79c0,0,62.42-4.15,86.6-21.99,0,0-134.26,50.15-231.82-67.33,0,0,51.66,26.23,78.94,25.48,0,0-25.64-14.41-44.79-27.77-19.27-13.46-54.02-25.88-67.49-28.19,0,0,71.95-6.16,137.55,16.86,0,0-57.7-18.51-76.5-61.71,0,0,26.71,23.95,59.91,29.79,33.14,5.83,58.56,15.93,72.7,27.64,0,0-26.4-25.59-28.04-68.23,0,0,3.77,24.79,26.49,41.23,22.53,16.3,41.55,27.2,48.11,39.06,0,0-17.18-28.41,1.56-84.7,0,0-6.37,38.22,4.3,54.27,10.58,15.9,28.34,40.78,30.32,46.69,0,0-.02-38.09,51.09-75.08,0,0-24.64,31.49-26.58,53.77-1.92,22.01,8.75,39.48,8.31,57.74,0,0-4.53-37.87,32.86-75.06,0,0-19.91,20.73-18.52,45.25,1.37,24.19.07,37.83-5.09,47.63,0,0,25.12-15.5,26.8-44.27,0,0,4.82,30.54-19.14,58.78,0,0,53.73-17.41,73.18,53.36,0,0-34.96-44.82-77.06-31.74l-15.57.39-17.09-30.62Z" fill="#2e3045"/>
                <path d="M150.28,146.29c2.93-8.27,10.45-11.46,16.2-16.78,6.49-6,4.21-11.12,9.05-17.84,4.15-5.74,15.01-10.55,21.39-10.48-7.71-4.39-3.59-8.44,1.72-10.88-.58-.49-1.15-.98-1.69-1.49,0-.02.02-.04.02-.06,1.48.15,2.98.3,4.46.44,1.71-.58,3.36-.98,4.59-1.15,7.87-1.09,15.61-1.53,23.61-1.75,17.7-.5,28.56-1.02,42.12,8.48l-.27-1c.55.44,1.09.89,1.63,1.36,1.49-5.4,7.2-12.23,12.93-14.77-1.13-1.68-2.29-3.4-3.47-5.13-4.37,4.17-9.63,6.98-15.68,7.41-2.09.14-3.99-.19-5.8-.76.81,1.84,1.38,2.82,1.38,2.82-.56-1.01-1.24-2.02-1.98-3.02-4.75-1.67-8.87-4.94-13.86-5.67-7.38-1.08-10.25,5.58-17.59,6.74-8.23,1.3-14.12-6.47-22.75-3.14-5.14,1.99-10.73,7.8-14.7,11.97-6.21,6.52-9.15,6.56-16.59,10.57-10.08,5.44-4.43,9.2-7.43,17.55-2.5,6.95-10.99,9.68-16.51,12.61-7.1,3.77-8.62,6.88-13.51,12.24-2.29,2.52-4.88,4.1-7.67,5.11,6.39,3.03,12.76,5.64,19.07,7.85-.28-3.74.03-7.49,1.34-11.21Z" fill="#618f8f"/>
              </g>
            </g>
          </motion.g>
          <g id="Face">
            <g id="Face-2" data-name="Face">
              <g>
                <g>
                  <ellipse cx="214.31" cy="252.65" rx="165.18" ry="74.18" fill="#003340"/>
                  <g>
                    <path d="M360.21,287.47c-2.93,2.47-6.16,4.86-9.67,7.15,8.56-24.62,12.26-51.95,11.37-75.32,2.7,2.4,5.11,4.88,7.23,7.43-.08,19.27-3,40.55-8.92,60.73Z" fill="url(#linear-gradient)"/>
                    <path d="M59.53,226.68c2.12-2.55,4.55-5.04,7.26-7.45-1.39,23.59,3.34,51.39,12.77,76.34-3.66-2.31-7.03-4.72-10.09-7.22-6.61-20.57-10.05-42.21-9.95-61.68Z" fill="url(#linear-gradient-2)"/>
                  </g>
                </g>
                <path d="M169.41,357.73c30.6-4.25,61.64-4.9,92.48-1.9,70.94,6.89,96.19-99.37,86.07-152.85-5.16-27.27-35.55-46.81-61.21-52.88-46.51-11-96.19-11.69-142.94-1.88-25.08,5.34-49.9,22.36-59.66,46.82-20.4,51.09,15.96,172.31,85.26,162.7Z" fill="url(#linear-gradient-3)"/>
                <path d="M84.15,195.03c4.83-12.09,13.33-22.36,23.73-30.3-3.49,4.65-6.4,9.71-8.57,15.14-20.4,51.09,15.96,172.31,85.26,162.7,30.6-4.24,61.64-4.9,92.48-1.9,16.83,1.64,31.09-3.1,42.91-11.98-14.07,18.14-33.28,29.55-58.07,27.14-30.85-3-61.89-2.35-92.48,1.9-69.3,9.62-105.66-111.61-85.26-162.7Z" fill="#a3b6bf" mixBlendMode="multiply" opacity=".46"/>
                <path d="M277.34,190.53c-41.92-3.26-84.03-3.26-125.94,0-67.22,5.22-90.36,116.33,31.22,132.98,38.57,5.28,84.88,2.52,118.68-18.42,52.93-32.79,34.06-110.05-23.95-114.56Z" fill="#c7d8ea"/>
                <path d="M216.29,324c-11.01,0-22.26-.78-33.43-2.31-63.86-8.75-85.69-43.25-84.83-72.62.88-30.03,23.88-54.41,53.51-56.71,20.81-1.62,41.95-2.44,62.83-2.44h0c20.88,0,42.01.82,62.83,2.44,25.35,1.97,45.63,19.28,51.67,44.11,6.34,26.07-4.86,52.39-28.54,67.06-27.31,16.92-60.77,20.47-84.04,20.47h0Z" fill="#003340"/>
              </g>
              <g mixBlendMode="screen" opacity=".34">
                <path d="M226.03,163.59c.72,6.36,19.97,9.42,42.64,12.35,22.7,2.73,42.11,4.49,44.37-1.5,2.29-5.83-15.79-18.1-41.53-21.27-25.72-3.26-46.27,4.2-45.48,10.41Z" fill="#a2bfdc"/>
              </g>
            </g>
          </g>
          <g id="Right_Eye" data-name="Right Eye">
            <motion.circle
              cx="284.39"
              cy="224.7"
              r="7.57"
              fill="#fff"
              animate={{
                scaleY: isBlinking ? 0.1 : 1,
              }}
              transition={{ duration: 0.1 }}
            />
          </g>
          <g id="Left_Eye" data-name="Left Eye">
            <motion.circle
              cx="160.65"
              cy="224.7"
              r="7.57"
              fill="#fff"
              animate={{
                scaleY: isBlinking ? 0.1 : 1,
              }}
              transition={{ duration: 0.1 }}
            />
          </g>
          {/* Animated Mouth */}
          <g id="Mouth">
            {MouthShapes[currentMouth] || MouthShapes.neutral}
          </g>
        </g>
      </svg>

      {/* Speaking indicator - only show in demo mode */}
      {isSpeaking && !avatarMode && (
        <div className="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
      )}

      {/* Debug info overlay - only show in demo mode */}
      {!avatarMode && (
        <div className="absolute bottom-1 left-1 text-xs bg-black bg-opacity-50 text-white px-1 py-0.5 rounded">
          mouth: {currentMouth}
        </div>
      )}
    </div>
  );
};

export default LeoLipSyncChat;
