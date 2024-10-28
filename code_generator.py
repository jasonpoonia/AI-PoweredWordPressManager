import logging

logger = logging.getLogger(__name__)

class CodeGenerator:
    def __init__(self, claude_client):
        self.claude = claude_client
        
    def generate_function(self, task_description: str) -> str:
        """Generate Python code for a given task"""
        try:
            logger.debug(f"Generating code for task: {task_description}")
            
            prompt = f"""You are a Python code generator for WordPress management.
            Your task is to create a Python function for the WordPressAPI class that does the following:
            {task_description}
            
            Rules:
            1. Include proper error handling and logging
            2. Use self.wp_url, self.wp_username, and self.wp_password from the class
            3. Return only the function code without any markdown formatting
            4. Include docstrings and type hints
            5. Handle all potential errors appropriately
            
            Generate the function code now:"""
            
            logger.debug("Sending request to Claude...")
            response = self.claude.messages.create(
                model="claude-3-opus-20240229",
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            if not response.content:
                logger.error("No content in Claude's response")
                return None
                
            code = response.content[0].text
            logger.debug(f"Received response from Claude: {code[:100]}...")
            
            # Clean up the code
            if "```python" in code:
                code = code.split("```python")[1].split("```")[0].strip()
                logger.debug("Extracted code from markdown blocks")
            elif "```" in code:
                code = code.split("```")[1].split("```")[0].strip()
                logger.debug("Extracted code from markdown blocks")
                
            logger.debug(f"Final generated code:\n{code}")
            return code
            
        except Exception as e:
            logger.error(f"Error generating code: {str(e)}", exc_info=True)
            raise