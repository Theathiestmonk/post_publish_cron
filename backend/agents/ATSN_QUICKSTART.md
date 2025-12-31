# ATSN Agent - Quick Start Guide

## ⚡ 5-Minute Setup

### Step 1: Install Dependencies (1 min)

```bash
cd "/Users/macbookpro/Documents/sab fresh/Agent_Emily"
pip install langgraph pydantic google-generativeai
```

### Step 2: Set API Key (1 min)

```bash
export GEMINI_API_KEY="your-api-key-here"
```

Get your API key: https://makersuite.google.com/app/apikey

### Step 3: Run Examples (3 min)

```bash
python backend/agents/atsn.py
```

## 🎯 Task Flow Examples

### Create Content Flow

```
User: "Create an Instagram post about AI"
  ↓
🤖 Classifying intent... ✓ Intent: create_content
  ↓
🤖 Constructing payload with task-specific examples...
  ↓
🤖 Found: channel=Social Media, platform=Instagram, content_idea="AI trends..."
  ↓
🤖 Missing: content_type, media
  ↓
🤖 "What type of content?
    • Post
    • Short video
    • Long video"
  ↓
User: "Post"
  ↓
🤖 "Include media?
    • Generate (AI-generated)
    • Upload (your own)
    • Without media"
  ↓
User: "Generate"
  ↓
🤖 Payload complete! Generating content...
  ↓
✓ Content created successfully!
  Platform: Instagram
  Type: Post
  Content: [Generated content here]
  Status: Saved as draft
```

### Create Lead Flow

```
User: "Add John Doe from website"
  ↓
🤖 Classifying intent... ✓ Intent: create_leads
  ↓
🤖 Constructing payload with examples...
  ↓
🤖 Found: lead_name="John Doe", lead_source="website"
  ↓
🤖 Missing: lead_email
  ↓
🤖 "What's their email address?"
  ↓
User: "john@example.com"
  ↓
🤖 "What's their phone number?"
  ↓
User: "+1234567890"
  ↓
🤖 Payload complete! Creating lead...
  ↓
✓ Lead created successfully!
  Name: John Doe
  Email: john@example.com
  Phone: +1234567890
  Source: website
  Status: New
```

### Edit Content Flow

```
User: "Edit my Instagram post to add emojis"
  ↓
🤖 Intent: edit_content
  ↓
🤖 Found: channel=Social Media, platform=Instagram
       edit_instruction="add emojis"
  ↓
🤖 Searching for Instagram posts...
  ↓
🤖 Found 3 posts. Which one?
    1. "AI trends in 2025" (Dec 24)
    2. "Marketing tips" (Dec 23)
    3. "Product launch" (Dec 22)
  ↓
User: "1"
  ↓
🤖 Applying edits...
  ↓
✓ Content updated!
  Added emojis: 🤖 ✨ 🚀 💡
```

### Schedule Content Flow

```
User: "Schedule my LinkedIn post for tomorrow at 2 PM"
  ↓
🤖 Intent: schedule_content
  ↓
🤖 Found: platform=LinkedIn, schedule_date="tomorrow"
       schedule_time="2 PM"
  ↓
🤖 Searching for LinkedIn drafts...
  ↓
🤖 Found 2 drafts. Select:
    1. "AI in Healthcare"
    2. "Remote Work Tips"
  ↓
User: "1"
  ↓
🤖 Scheduling...
  ↓
✓ Content scheduled!
  Post: "AI in Healthcare"
  Date: Dec 26, 2025
  Time: 2:00 PM
```

## 🔥 Most Common Queries

### Content Queries

```python
# Create
"Create an Instagram post about [topic]"
"Make a LinkedIn video about [subject]"
"Write a blog post on [topic]"

# Edit
"Edit my [platform] post to [instruction]"
"Change the [platform] content to be more [style]"

# Delete
"Delete all [platform] posts from [timeframe]"
"Remove my [platform] post from [date]"

# View
"Show me all [platform] content"
"List [platform] posts from [timeframe]"

# Publish
"Publish my [platform] draft"
"Post to [platform]"

# Schedule
"Schedule [platform] post for [date] at [time]"
"Post to [platform] on [date]"
```

### Lead Queries

```python
# Create
"Add lead [name], email [email], from [source]"
"Create new lead [name], phone [phone]"

# View
"Show me all [status] leads"
"List leads from [source]"
"Find lead [name]"

# Edit
"Update [name]'s status to [status]"
"Change [name]'s email to [email]"

# Delete
"Delete lead [name]"
"Remove all [status] leads"

# Follow up
"Follow up with [name] about [topic]"
"Send follow-up to [email]"
```

### Analytics Queries

```python
# Insights
"Show [platform] engagement for [timeframe]"
"Display [platform] metrics"

# Analytics
"Show [platform] analytics for [timeframe]"
"View all social media analytics"
```

## 📊 Payload Cheat Sheet

### Create Content
✅ **Required**: channel, platform, content_type, media, content_idea
📝 **Example**: Social Media → Instagram → Post → Generate → "AI trends..."

### Create Lead
✅ **Required**: lead_name + (lead_email OR lead_phone)
📝 **Example**: "John Doe" + "john@example.com" + "website"

### Edit Content
✅ **Required**: channel, platform, edit_instruction
📝 **Example**: Social Media → Instagram → "add more emojis"

### Schedule Content
✅ **Required**: channel, platform, schedule_date, schedule_time
📝 **Example**: Social Media → LinkedIn → "tomorrow" → "2 PM"

## 🎨 Clarification Response Tips

### When asked for Channel:
```
Just say: "Social Media" / "Blog" / "Email" / "Messages"
```

### When asked for Platform:
```
Just say: "Instagram" / "Facebook" / "LinkedIn" / etc.
```

### When asked for Media:
```
Say: "Generate" (AI creates image)
     "Upload" (you provide image)
     "Without media" (text only)
```

### When asked for Content Type:
```
Say: "Post" / "Short video" / "Long video" / "Email" / "Message"
```

### When asked for Date:
```
Say: "tomorrow" / "next Monday" / "2025-12-30" / "today"
```

### When asked for Time:
```
Say: "9 AM" / "14:00" / "2:30 PM" / "morning" / "evening"
```

## 🚀 Integration Code Snippets

### Basic Chat Loop

```python
from backend.agents.atsn import ATSNAgent

agent = ATSNAgent()

while True:
    user_input = input("You: ")
    if user_input.lower() in ['quit', 'exit']:
        break
    
    response = agent.process_query(user_input)
    
    if response['waiting_for_user']:
        print(f"Agent: {response['clarification_question']}")
    elif response['result']:
        print(f"Agent: {response['result']}")
        agent.reset()  # Start fresh for next task
    elif response['error']:
        print(f"Error: {response['error']}")
        agent.reset()
```

### REST API Endpoint

```python
from fastapi import FastAPI
from pydantic import BaseModel
from backend.agents.atsn import ATSNAgent

app = FastAPI()
agent_sessions = {}

class ChatRequest(BaseModel):
    session_id: str
    message: str

@app.post("/chat")
async def chat(request: ChatRequest):
    # Get or create agent for session
    if request.session_id not in agent_sessions:
        agent_sessions[request.session_id] = ATSNAgent()
    
    agent = agent_sessions[request.session_id]
    response = agent.process_query(request.message)
    
    # Clean up completed sessions
    if not response['waiting_for_user']:
        if request.session_id in agent_sessions:
            del agent_sessions[request.session_id]
    
    return response
```

### WebSocket Implementation

```python
from fastapi import WebSocket
from backend.agents.atsn import ATSNAgent

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    agent = ATSNAgent()
    
    try:
        while True:
            message = await websocket.receive_text()
            response = agent.process_query(message)
            await websocket.send_json(response)
            
            if not response['waiting_for_user']:
                agent.reset()
    except:
        pass
```

## 🔧 Troubleshooting

### "GEMINI_API_KEY not found"
```bash
export GEMINI_API_KEY="your-key"
# Or add to ~/.bashrc or ~/.zshrc
```

### "Import langgraph error"
```bash
pip install langgraph --upgrade
```

### "JSON decode error"
- The model output might not be clean JSON
- The code handles this with fallbacks
- If persists, check your API key and quota

### "Payload construction failed"
- Check if GEMINI_API_KEY is valid
- Verify internet connection
- Check Gemini API quota

## 📈 Performance Tips

1. **Reuse agent instance** - Don't create new agent for each query
2. **Reset after completion** - Call `agent.reset()` when task is done
3. **Batch similar queries** - Process similar tasks together
4. **Use conversation history** - Include context for better extraction

## 🎓 Learn By Example

Run the built-in examples:
```bash
python backend/agents/atsn.py
```

Watch how:
- Intent classification works
- Payload construction extracts information
- Clarification questions are asked
- Tasks are completed

## 📞 Need Help?

1. Check the full README: `ATSN_README.md`
2. Review the code comments in `atsn.py`
3. Run examples with `python backend/agents/atsn.py`
4. Check payload models in the code

---

**Happy building! 🚀**







