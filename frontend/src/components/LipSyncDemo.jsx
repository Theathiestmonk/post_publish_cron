import React, { useState } from 'react';
import LeoLipSyncChat from './LeoLipSyncChat';

const LipSyncDemo = () => {
  const [demoText, setDemoText] = useState('');
  const [isPlaying, setIsPlaying] = useState(false);

  const demoTexts = [
    "Hello! I'm Leo, your content creation assistant.",
    "I can help you create amazing social media posts.",
    "Let me show you how lip-sync animation works!",
    "This is a comprehensive phoneme mapping system.",
    "A, E, I, O, U - vowels sound different!",
    "B, M, P sounds use the same mouth shape.",
    "TH, SH, CH - different consonants!",
    "QW - question words have unique shapes.",
    "Thank you for trying the lip-sync demo!"
  ];

  const playDemo = (text) => {
    if (isPlaying) return;
    setDemoText(text);
    setIsPlaying(true);
  };

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold text-center mb-8">Leo Lip-Sync Animation Demo</h1>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {/* Demo Controls */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold mb-4">Try Different Texts:</h2>

          {demoTexts.map((text, index) => (
            <button
              key={index}
              onClick={() => playDemo(text)}
              disabled={isPlaying}
              className="w-full p-4 text-left bg-white border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <div className="font-medium">{text}</div>
              <div className="text-sm text-gray-500 mt-1">
                Phonemes: {text.split('').filter(char => char !== ' ').length} characters
              </div>
            </button>
          ))}

          {/* Custom Text Input */}
          <div className="mt-6">
            <label className="block text-sm font-medium mb-2">Custom Text:</label>
            <input
              type="text"
              value={demoText}
              onChange={(e) => setDemoText(e.target.value)}
              placeholder="Type your own text to animate..."
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={() => playDemo(demoText)}
              disabled={!demoText.trim() || isPlaying}
              className="mt-2 w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Play Custom Text
            </button>
          </div>
        </div>

          {/* Leo Character Display */}
        <div className="space-y-4">
          <h2 className="text-xl font-semibold mb-4">Leo Character:</h2>

          <div className="bg-white p-6 rounded-lg border border-gray-200 flex flex-col items-center">
            <div className="relative">
              {/* Debug: Show component state */}
              <div className="mb-2 text-xs bg-gray-100 p-2 rounded">
                Debug: text="{demoText}", isPlaying={isPlaying ? 'true' : 'false'}
              </div>

              {/* Leo Animation - Embedded in the column */}
              <LeoLipSyncChat
                text={demoText}
                isSpeaking={isPlaying}
                agentName="leo"
                onAnimationComplete={() => setIsPlaying(false)}
              />

              {/* Fallback display when not animating */}
              {(!demoText || !isPlaying) && (
                <div className="w-48 h-48 bg-gray-50 border-2 border-dashed border-gray-300 rounded-lg flex items-center justify-center">
                  <div className="text-center text-gray-500">
                    <div className="text-4xl mb-2">🤖</div>
                    <div className="text-sm">Leo will appear here</div>
                    <div className="text-xs mt-1">Click a text button to start</div>
                  </div>
                </div>
              )}
            </div>

            {/* Status indicator */}
            <div className="mt-4 text-center">
              <div className={`inline-block px-3 py-1 rounded-full text-sm ${
                isPlaying ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
              }`}>
                {isPlaying ? '🎭 Speaking...' : '😴 Waiting'}
              </div>
            </div>
          </div>

          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="font-medium mb-3">Phoneme Mapping:</h3>
            <div className="grid grid-cols-1 gap-2 text-sm">
              <div><strong>A,E,I,O,U</strong> → Individual vowels</div>
              <div><strong>B,M,P</strong> → mouthBMP</div>
              <div><strong>D,T,K,G,S,Z</strong> → mouthE</div>
              <div><strong>TH,SH,CH</strong> → Special sounds</div>
              <div><strong>L,R,Q,W</strong> → Unique shapes</div>
            </div>
          </div>

          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <h3 className="font-medium mb-3">Animation Features:</h3>
            <div className="text-sm space-y-1">
              <div>⚡ Real-time lip sync</div>
              <div>🎭 15 mouth shapes</div>
              <div>👁️ Realistic blinking</div>
              <div>🎯 Head movement</div>
              <div>✨ Glow effects</div>
            </div>
          </div>
        </div>
      </div>


      {/* Current Status */}
      <div className="mt-8 text-center space-y-2">
        <div className="inline-block px-4 py-2 bg-gray-100 rounded-lg">
          <span className="text-sm">
            Status: {isPlaying ? '🎭 Animating...' : '🎯 Ready to animate'}
            {demoText && (
              <span className="ml-2 text-gray-600">
                ({demoText.length} characters)
              </span>
            )}
          </span>
        </div>
        {demoText && (
          <div className="text-sm text-gray-600 max-w-2xl mx-auto">
            <strong>Current Text:</strong> "{demoText}"
          </div>
        )}
      </div>
    </div>
  );
};

export default LipSyncDemo;
