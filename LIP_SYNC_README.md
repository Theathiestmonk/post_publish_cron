# 🎭 Leo Lip-Sync Animation System

## Overview
The Leo Lip-Sync Animation System brings Leo, the content creation agent, to life with realistic mouth animations that synchronize with text responses in the ATSN chatbot.

## 🚀 How to Access the Demo

### 1. Navigate to ATSN Dashboard
- Go to `/atsn` in your application
- Log in if required

### 2. Switch to Lip-Sync Demo Tab
- Look for the tab navigation in the header
- Click on **"Lip-Sync Demo"** (🎤 icon)
- The demo interface will load

### 3. Test the Animation
- **Pre-built examples**: Click on any of the sample text buttons
- **Custom text**: Type your own text in the input field and click "Play Custom Text"
- **Watch Leo**: The Leo character will appear in the bottom-right corner and animate

## 🎯 Features

### Real-time Lip Sync
- **15 mouth shapes** mapped to phonemes
- **Natural timing** (~67ms per character)
- **Digraph support** (TH, SH, CH, NG)
- **Head movement** during speech
- **Realistic blinking**

### Phoneme Mapping
| Letters | Mouth Shape | Description |
|---------|-------------|-------------|
| A, E, I, O, U | Individual vowels | Each vowel has unique mouth shape |
| B, M, P | mouthBMP | Bilabial consonants |
| D, T, K, G, S, Z | mouthE | Dental/alveolar consonants |
| TH | mouthTH | Dental fricative |
| SH | mouthSH | Alveolar fricative |
| CH | mouthCH | Postalveolar affricate |
| L | mouthL | Lateral approximant |
| R | mouthR | Rhotic consonant |
| Q, W | mouthQW | Labial-velar approximant |

## 🛠️ Technical Implementation

### Components
- **`LeoLipSyncChat.jsx`** - Main lip-sync component
- **`LipSyncDemo.jsx`** - Interactive demo interface
- **Modified `ATSNChatbot.jsx`** - Integrated lip-sync triggering

### Integration Points
- **Automatic activation** when `agent_name === 'leo'`
- **Text conversion** to phoneme sequence
- **Animation timing** synchronized with natural speech
- **Visual effects** including glow and speaking indicator

### Animation Flow
1. **Text received** → Convert to phonemes
2. **Mouth shapes** animate in sequence
3. **Head movement** adds realism
4. **Blinking** occurs randomly
5. **Animation completes** → Return to neutral

## 🎨 Customization

### Timing Adjustments
```javascript
// In LeoLipSyncChat.jsx
const CHARS_PER_SECOND = 15; // Adjust speech speed
const BASE_DURATION = 1000 / CHARS_PER_SECOND;
```

### Visual Effects
- **Glow color**: Modify the `backgroundColor` in the glow effect
- **Animation scale**: Adjust head movement intensity
- **Blink frequency**: Change random blink intervals

### Adding New Phonemes
1. Add mouth shape to `MouthShapes` object
2. Map letters in `PHONEME_MAP`
3. Update timing logic if needed

## 🎭 Live Demo Examples

Try these texts to see different mouth animations:

- **"Hello! I'm Leo, your content creation assistant."** - Basic greeting
- **"A, E, I, O, U - vowels sound different!"** - Vowel demonstration
- **"B, M, P sounds use the same mouth shape."** - Consonant grouping
- **"TH, SH, CH - different consonants!"** - Digraph examples
- **"QW - question words have unique shapes."** - Special cases

## 🔧 Troubleshooting

### Lip-Sync Not Working
1. **Check agent name**: Ensure response has `agent_name: 'leo'`
2. **Verify text**: Make sure response contains text
3. **Browser console**: Check for animation errors
4. **Network tab**: Confirm API responses include agent info

### Animation Performance
- **Reduce complexity**: Lower animation frequency for better performance
- **Optimize timing**: Adjust `CHARS_PER_SECOND` for smoother animation
- **Browser compatibility**: Test across different browsers

## 📱 Mobile Support
- **Responsive design**: Scales automatically for mobile devices
- **Touch interactions**: All demo buttons work on touch screens
- **Performance optimized**: Reduced effects on smaller screens

## 🚀 Future Enhancements
- **Audio synchronization**: Real speech audio integration
- **Emotion expressions**: Happy, sad, excited animations
- **Multiple languages**: Extended phoneme mapping
- **Gesture animations**: Hand and body movement
- **Personality variations**: Different Leo personalities

---

**Experience the magic**: Switch to the Lip-Sync Demo tab and watch Leo come to life! 🎭✨





