import React, { useState, useEffect } from 'react';
import { motion, useAnimation } from 'framer-motion';

// Import your Leo SVG (you'll need to convert it to a React component)
const LeoSVG = ({ eyeScaleY, mouthShape, hairWiggle, ...props }) => {
  return (
    <svg viewBox="0 0 421.55 358.27" {...props}>
      {/* Your Leo SVG content goes here - you can copy from the file */}
      <g isolation="isolate">
        {/* Hair */}
        <motion.g
          id="Hair"
          animate={{
            rotate: hairWiggle ? [0, 2, -2, 0] : 0,
            scale: hairWiggle ? [1, 1.02, 0.98, 1] : 1
          }}
          transition={{
            duration: 2,
            repeat: hairWiggle ? Infinity : 0,
            ease: "easeInOut"
          }}
        >
          {/* Hair paths from your SVG */}
          <path d="M120.22,116.72S42.16,103.45,0,146.38c0,0,26.54-13.27,64.8-.78,38.25,12.49,95.23,28.89,131.93,8.59,36.69-20.3-3.12-22.64-5.47-22.64l-71.04-14.83Z" fill="#2e3045"/>
          {/* Add other hair paths */}
        </motion.g>

        {/* Face */}
        <motion.g
          id="Face"
          animate={{
            scale: [1, 1.02, 1], // Breathing effect
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            ease: "easeInOut"
          }}
        >
          {/* Face elements */}
          <ellipse cx="214.31" cy="252.65" rx="165.18" ry="74.18" fill="#003340"/>
          {/* Add other face elements */}
        </motion.g>

        {/* Eyes */}
        <motion.g id="Right_Eye">
          <motion.circle
            cx="284.39"
            cy="224.7"
            r="7.57"
            fill="#fff"
            animate={{
              scaleY: eyeScaleY || 1,
            }}
            transition={{
              duration: 0.1,
              ease: "easeOut"
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
              scaleY: eyeScaleY || 1,
            }}
            transition={{
              duration: 0.1,
              ease: "easeOut"
            }}
          />
        </motion.g>

        {/* Mouth - conditionally render different shapes */}
        {mouthShape === 'O' && (
          <motion.g id="Mouth_O">
            <motion.path
              d="M221.03,235.29c-3.03,0-13.64-.25-14.92,16.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
              fill="#fff"
              initial={{ scale: 0.8 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.2 }}
            />
          </motion.g>
        )}

        {mouthShape === 'A' && (
          <motion.g id="Mouth_A_E_I">
            <motion.path
              d="M261.06,271.36c-5.35-11.61-11.35-15.64-16.26-16.93-7.61-2-10.55,3.25-22.5,3.25-13.3,0-17.4-6.09-25.28-3.33-4.02,1.41-9.09,5.2-13.04,16.02,3.86,4.73,11.81,12.95,23.55,15.84,6.76,1.66,14.06,1.37,16.48,1.29,1.52-.05,6.73-.28,11.83-1.45,11.56-2.65,20.17-9.66,25.22-14.69Z"
              fill="#fff"
              initial={{ scale: 0.8 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.2 }}
            />
          </motion.g>
        )}

        {/* Default closed mouth */}
        {!mouthShape && (
          <motion.g id="Mouth_Default">
            <motion.path
              d="M221.03,235.29c-3.03,0-13.64-.25-14.92,16.78-.24,3.23,1.21,11.27,1.21,15.91s-2.09,18.82.12,23.7c2.71,5.99,7.52,8.99,14.68,8.99s14.66-5.24,14.68-12.95c.02-8.99-1.36-17.13-1.24-19.74.12-2.48,1.38-11.9.78-16.68-.61-4.78-1.27-16-15.3-16Z"
              fill="#fff"
              initial={{ scale: 0.8 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.2 }}
            />
          </motion.g>
        )}
      </g>
    </svg>
  );
};

export const AnimatedLeo = () => {
  const [eyeScaleY, setEyeScaleY] = useState(1);
  const [mouthShape, setMouthShape] = useState(null);
  const [hairWiggle, setHairWiggle] = useState(false);
  const controls = useAnimation();

  // Blink animation
  useEffect(() => {
    const blinkInterval = setInterval(() => {
      setEyeScaleY(0.1);
      setTimeout(() => setEyeScaleY(1), 150);
    }, 3000 + Math.random() * 2000); // Random blink timing

    return () => clearInterval(blinkInterval);
  }, []);

  // Mouth animation for speech
  const speak = (text) => {
    const phonemes = ['A', 'O', null, 'A', 'O', null]; // Simple phoneme sequence
    let index = 0;

    const speakInterval = setInterval(() => {
      if (index < phonemes.length) {
        setMouthShape(phonemes[index]);
        index++;
      } else {
        clearInterval(speakInterval);
        setMouthShape(null);
      }
    }, 200);
  };

  // Head bob animation
  const headBob = () => {
    controls.start({
      rotate: [0, 5, -5, 0],
      transition: {
        duration: 0.5,
        ease: "easeInOut"
      }
    });
  };

  return (
    <div className="flex flex-col items-center space-y-4">
      <motion.div
        animate={controls}
        className="w-64 h-64"
      >
        <LeoSVG
          eyeScaleY={eyeScaleY}
          mouthShape={mouthShape}
          hairWiggle={hairWiggle}
          className="w-full h-full"
        />
      </motion.div>

      <div className="flex space-x-2">
        <button
          onClick={() => speak("Hello")}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Speak
        </button>
        <button
          onClick={headBob}
          className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
        >
          Nod Head
        </button>
        <button
          onClick={() => setHairWiggle(!hairWiggle)}
          className="px-4 py-2 bg-purple-500 text-white rounded hover:bg-purple-600"
        >
          {hairWiggle ? 'Stop Wiggle' : 'Wiggle Hair'}
        </button>
      </div>
    </div>
  );
};






