from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import anthropic
import requests
import uvicorn
from pydantic import BaseModel
from typing import List, Dict, Optional
import os  # Added missing import
from dotenv import load_dotenv
from code_manager import DynamicCodeManager  # This import should now work
from code_generator import CodeGenerator
from wordpress_api import WordPressAPI
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()
claude = anthropic.Client(api_key=os.getenv("ANTHROPIC_API_KEY"))
wp_api = WordPressAPI()
code_manager = DynamicCodeManager()
code_generator = CodeGenerator(claude)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]

@app.get("/", response_class=HTMLResponse)
def get_index():
    with open("static/index.html") as f:
        return f.read()

@app.post("/api/chat")
async def chat(request: ChatRequest):
    logger.debug(f"Received chat request: {request}")
    
    try:
        user_request = request.messages[-1].content
        
        # First, check if we have a suitable existing function
        func_name, func_details = await code_manager.find_matching_function(user_request)
        
        if func_name:
            logger.info(f"Found matching function: {func_name}")
            try:
                # Execute the existing function
                func = getattr(wp_api, func_name)
                result = func()
                
                # Format the result
                if isinstance(result, list) and len(result) > 0 and 'title' in result[0]:
                    # It's probably a list of pages/posts
                    formatted_result = "\n".join([f"- {item['title']['rendered']}" for item in result])
                else:
                    formatted_result = str(result)
                
                return {
                    "role": "assistant",
                    "content": f"I found an existing function ({func_name}) that can help. Here's the result:\n\n{formatted_result}"
                }
            except Exception as e:
                logger.error(f"Error executing function {func_name}: {str(e)}")
                return {
                    "role": "assistant",
                    "content": f"I found a matching function but encountered an error: {str(e)}"
                }
        
        # If no matching function, generate new code
        logger.info("No matching function found, generating new code...")
        code = code_generator.generate_function(user_request)
        
        if code is None:
            return {
                "role": "assistant",
                "content": "I apologize, but I wasn't able to generate code for your request. Could you please rephrase it?"
            }
            
        # Add the new function
        if code_manager.add_function(code):
            # Try to execute the new function
            try:
                func_name = ast.parse(code).body[0].name
                func = getattr(wp_api, func_name)
                result = func()
                
                # Format the result
                if isinstance(result, list) and len(result) > 0 and 'title' in result[0]:
                    formatted_result = "\n".join([f"- {item['title']['rendered']}" for item in result])
                else:
                    formatted_result = str(result)
                
                return {
                    "role": "assistant",
                    "content": f"I've created and executed a new function to handle your request. Here's the result:\n\n{formatted_result}\n\nI added this function for future use:\n```python\n{code}\n```"
                }
            except Exception as e:
                return {
                    "role": "assistant",
                    "content": f"I created a new function but encountered an error when executing it: {str(e)}\n\nHere's the function I added:\n```python\n{code}\n```"
                }
        else:
            return {
                "role": "assistant",
                "content": "I wasn't able to add the new function to handle your request. This might be due to a code error or naming conflict."
            }
            
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
if __name__ == "__main__":
    logger.info("Starting application...")
    try:
        # Create 'static' directory if it doesn't exist
        if not os.path.exists('static'):
            os.makedirs('static')
            logger.info("Created 'static' directory")
        
        # Create default index.html if it doesn't exist
        if not os.path.exists('static/index.html'):
            with open('static/index.html', 'w') as f:
                f.write("""<!DOCTYPE html>
<html>
<head>
    <title>WordPress Manager</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        #chat { height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; margin-bottom: 10px; }
        #input { width: 100%; padding: 10px; margin-bottom: 10px; }
        .message { margin-bottom: 10px; }
        .user { color: blue; }
        .assistant { color: green; }
        pre { background: #f5f5f5; padding: 10px; border-radius: 5px; overflow-x: auto; }
    </style>
</head>
<body>
    <h1>WordPress Manager</h1>
    <div id="chat"></div>
    <input type="text" id="input" placeholder="Type your request...">
    <button onclick="sendMessage()">Send</button>
    <script>
        let messages = [];
        
        async function sendMessage() {
            const input = document.getElementById('input');
            const chat = document.getElementById('chat');
            const text = input.value.trim();
            
            if (!text) return;
            
            // Add user message
            messages.push({ role: 'user', content: text });
            updateChat();
            
            // Clear input
            input.value = '';
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ messages })
                });
                
                const data = await response.json();
                messages.push(data);
                updateChat();
                
            } catch (error) {
                console.error('Error:', error);
                messages.push({
                    role: 'assistant',
                    content: 'Sorry, there was an error processing your request.'
                });
                updateChat();
            }
        }
        
        function updateChat() {
            const chat = document.getElementById('chat');
            chat.innerHTML = messages.map(m => `
                <div class="message ${m.role}">
                    <strong>${m.role}:</strong>
                    <div>${formatMessage(m.content)}</div>
                </div>
            `).join('');
            chat.scrollTop = chat.scrollHeight;
        }
        
        function formatMessage(content) {
            return content.replace(/```(.*?)\n([\s\S]*?)```/g, (match, lang, code) => `
                <pre><code class="language-${lang || ''}">${code.trim()}</code></pre>
            `);
        }
        
        // Handle enter key
        document.getElementById('input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    </script>
</body>
</html>""")
            logger.info("Created default index.html")
            
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}", exc_info=True)
        raise