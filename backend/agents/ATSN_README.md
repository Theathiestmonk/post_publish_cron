# ATSN Agent - Content & Lead Management

A lightweight, intelligent agent built with **LangGraph** and **Gemini 2.5** for managing content creation and lead workflows.

## 🎯 Features

### **13 Task Types Supported**

#### Content Management
1. **Create Content** - Generate posts, videos, emails, messages for various platforms
2. **Edit Content** - Modify existing content with specific instructions
3. **Delete Content** - Remove content with filters
4. **View Content** - List and filter content
5. **Publish Content** - Publish content to connected platforms
6. **Schedule Content** - Schedule content for future publishing

#### Lead Management
7. **Create Leads** - Add new leads to the system
8. **View Leads** - List and filter leads
9. **Edit Leads** - Update lead information
10. **Delete Leads** - Remove leads
11. **Follow Up Leads** - Generate and send follow-up messages

#### Analytics
12. **View Insights** - See metrics and insights
13. **View Analytics** - View detailed analytics

## 🏗️ Architecture

```
User Query
    ↓
Intent Classifier (Gemini 2.5)
    ↓
Task-Specific Payload Constructor (with examples)
    ↓
Payload Completer (asks clarifications)
    ↓
Action Executor (performs the task)
    ↓
Result
```

### Key Components

- **Intent Classifier**: Uses Gemini 2.5 to classify user intent into 13 categories
- **Payload Constructors**: 13 specialized constructors, each with task-specific examples
- **Payload Completers**: Smart clarification system with clear options
- **Action Executors**: Task-specific handlers for execution

## 🚀 Installation

### 1. Install Dependencies

```bash
pip install -r backend/agents/atsn_requirements.txt
```

Required packages:
- `langgraph>=0.2.0` - Graph-based workflow orchestration
- `pydantic>=2.0.0` - Data validation and models
- `google-generativeai>=0.3.0` - Gemini 2.5 API

### 2. Set Up API Key

```bash
export GEMINI_API_KEY="your-gemini-api-key-here"
```

Or create a `.env` file:
```
GEMINI_API_KEY=your-gemini-api-key-here
```

## 💻 Usage

### Basic Usage

```python
from backend.agents.atsn import ATSNAgent

# Initialize agent
agent = ATSNAgent()

# Process a query
response = agent.process_query(
    "Create an Instagram post about AI trends in 2025"
)

# Handle clarifications
while response['waiting_for_user']:
    print(response['clarification_question'])
    user_input = input("You: ")
    response = agent.process_query(user_input)

# Get result
if response['result']:
    print(response['result'])
```

### Response Structure

```python
{
    "intent": "create_content",
    "payload": {
        "channel": "Social Media",
        "platform": "Instagram",
        "content_type": "Post",
        ...
    },
    "payload_complete": True,
    "waiting_for_user": False,
    "clarification_question": None,
    "result": "✓ Content created successfully!...",
    "error": None,
    "current_step": "end"
}
```

## 📝 Example Queries

### Content Creation

```
"Create an Instagram post about sustainable fashion"
"Write a LinkedIn article about AI in healthcare"
"Generate a Facebook post with an image about productivity"
"Create a short video for Youtube about cooking tips"
```

### Content Management

```
"Edit my Instagram post to add more emojis"
"Delete all Facebook posts from last week"
"Show me all LinkedIn content from this month"
"Publish my draft Instagram post"
"Schedule my LinkedIn post for tomorrow at 9 AM"
```

### Lead Management

```
"Add a new lead John Doe from website, email john@example.com"
"Show me all qualified leads"
"Update Sarah Johnson's status to Contacted"
"Delete leads with status Lost"
"Follow up with Mike Chen about the proposal"
```

### Analytics

```
"Show me Instagram engagement metrics for this week"
"Display Facebook analytics from last month"
"View insights for all social media platforms"
```

## 🔧 Customization

### Adding Custom Handlers

Each task has its own handler function. To customize behavior, modify the handler in the code:

```python
def handle_create_content(state: AgentState) -> AgentState:
    """Your custom implementation"""
    # Add your logic here
    # Connect to your database
    # Call your APIs
    return state
```

### Integrating with Supabase

The handlers are ready for database integration. Example:

```python
from supabase import create_client

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def handle_create_content(state: AgentState) -> AgentState:
    payload = state.payload
    
    # Generate content
    content = generate_content(payload)
    
    # Save to Supabase
    result = supabase.table('content').insert({
        'platform': payload['platform'],
        'content': content,
        'status': 'draft',
        'created_at': 'now()'
    }).execute()
    
    state.result = f"✓ Content saved with ID: {result.data[0]['id']}"
    return state
```

### Customizing Clarification Questions

Edit the `FIELD_CLARIFICATIONS` dictionary:

```python
FIELD_CLARIFICATIONS = {
    "create_content": {
        "channel": "Your custom clarification question here...",
        ...
    },
    ...
}
```

## 📊 Payload Models

Each task has a specific Pydantic model defining its structure:

### CreateContentPayload
- `channel`: Social Media | Blog | Email | messages
- `platform`: Instagram | Facebook | LinkedIn | Youtube | Gmail | Whatsapp
- `content_type`: Post | short video | long video | Email | message
- `media`: Generate | Upload | without media
- `content_idea`: Main content idea (min 10 words)

### CreateLeadPayload
- `lead_name`: Lead's full name
- `lead_email`: Email address
- `lead_phone`: Phone number
- `lead_source`: Where the lead came from
- `lead_status`: New | Contacted | Qualified | Lost | Won
- `remarks`: Additional notes

[See code for all payload models]

## 🧪 Testing

Run the example script:

```bash
python backend/agents/atsn.py
```

This will run through 4 example scenarios demonstrating:
1. Content creation with clarifications
2. Lead creation
3. Content scheduling
4. Viewing filtered leads

## 🔍 How It Works

### 1. Intent Classification

```python
User: "Create an Instagram post about AI"
       ↓
Gemini 2.5 analyzes and classifies
       ↓
Intent: "create_content"
```

### 2. Payload Construction

Each intent has a specialized constructor with examples:

```python
Query: "Create Instagram post about AI"
       ↓
Extract using task-specific prompt with examples
       ↓
Payload: {
    "channel": "Social Media",
    "platform": "Instagram",
    "content_idea": "artificial intelligence trends..."
}
```

### 3. Payload Completion

```python
Missing: content_type, media
       ↓
Ask: "What type of content?
      • Post
      • Short video
      • Long video"
       ↓
User: "Post"
       ↓
Ask: "Include media?
      • Generate
      • Upload
      • Without media"
```

### 4. Action Execution

```python
Complete payload
       ↓
Route to handler: handle_create_content()
       ↓
Generate content using Gemini
       ↓
Save to database
       ↓
Return result
```

## 🎨 Advantages

### Task-Specific Constructors
- Each task has tailored extraction logic
- Better context understanding
- More accurate field extraction

### Example-Based Prompts
- Gemini learns from examples
- Consistent extraction patterns
- Handles edge cases better

### Clear Clarification Flow
- Users get clear options
- Reduces ambiguity
- Faster completion

### Lightweight & Fast
- Only uses Gemini 2.5 (no multiple LLMs)
- Minimal dependencies
- Fast response times

## 📈 Future Enhancements

- [ ] Add actual Supabase integration
- [ ] Implement social media API connections
- [ ] Add content templates
- [ ] Implement lead scoring
- [ ] Add batch operations
- [ ] Create web UI
- [ ] Add authentication
- [ ] Implement webhooks for scheduled content

## 🤝 Integration Guide

### With FastAPI

```python
from fastapi import FastAPI
from backend.agents.atsn import ATSNAgent

app = FastAPI()
agent = ATSNAgent()

@app.post("/chat")
async def chat(message: str):
    response = agent.process_query(message)
    return response
```

### With Streamlit

```python
import streamlit as st
from backend.agents.atsn import ATSNAgent

if 'agent' not in st.session_state:
    st.session_state.agent = ATSNAgent()

user_input = st.text_input("Your message:")
if user_input:
    response = st.session_state.agent.process_query(user_input)
    
    if response['waiting_for_user']:
        st.info(response['clarification_question'])
    else:
        st.success(response['result'])
```

## 📄 License

[Your License Here]

## 👨‍💻 Author

Built with ❤️ using LangGraph and Gemini 2.5

---

**Need help?** Check the examples in `main()` function or open an issue.








