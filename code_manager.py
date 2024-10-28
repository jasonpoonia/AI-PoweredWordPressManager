import ast
import os
import inspect
from typing import Optional, Tuple, Dict, List
import logging
import anthropic

logger = logging.getLogger(__name__)

class DynamicCodeManager:
    def __init__(self, filename="wordpress_api.py", claude_client=None):
        self.filename = filename
        self.claude = claude_client
        self.current_code = self._read_current_code()
        self.function_registry = self._analyze_existing_functions()
        
    def _read_current_code(self) -> str:
        """Read the current code from file or create base structure if doesn't exist"""
        try:
            with open(self.filename, 'r') as f:
                return f.read()
        except FileNotFoundError:
            base_code = """import requests
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class WordPressAPIError(Exception):
    pass

class WordPressAPI:
    def __init__(self):
        self.wp_url = os.getenv("WP_URL")
        self.wp_username = os.getenv("WP_USERNAME")
        self.wp_password = os.getenv("WP_APP_PASSWORD")
        
        if not all([self.wp_url, self.wp_username, self.wp_password]):
            missing = []
            if not self.wp_url: missing.append("WP_URL")
            if not self.wp_username: missing.append("WP_USERNAME")
            if not self.wp_password: missing.append("WP_APP_PASSWORD")
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
"""
            with open(self.filename, 'w') as f:
                f.write(base_code)
            return base_code

    def _analyze_existing_functions(self) -> Dict[str, Dict]:
        """Analyze existing functions and their purposes"""
        try:
            tree = ast.parse(self.current_code)
            functions = {}
            
            # Find the WordPressAPI class
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "WordPressAPI":
                    # Analyze each function in the class
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            doc = ast.get_docstring(item)
                            params = [a.arg for a in item.args.args if a.arg != 'self']
                            returns = None
                            
                            # Get return type hint if exists
                            if item.returns:
                                returns = ast.unparse(item.returns)
                            
                            functions[item.name] = {
                                'name': item.name,
                                'docstring': doc,
                                'parameters': params,
                                'returns': returns,
                                'code': ast.unparse(item)
                            }
                            
            logger.debug(f"Found {len(functions)} existing functions")
            return functions
            
        except Exception as e:
            logger.error(f"Error analyzing functions: {str(e)}")
            return {}

    async def find_matching_function(self, user_request: str) -> Tuple[Optional[str], Optional[Dict]]:
        """Use Claude to determine if an existing function matches the user's request"""
        try:
            # Prepare function registry for Claude
            function_descriptions = []
            for name, details in self.function_registry.items():
                desc = f"""Function: {name}
                Description: {details['docstring']}
                Parameters: {', '.join(details['parameters'])}
                Returns: {details['returns']}
                """
                function_descriptions.append(desc)
                
            prompt = f"""Given this user request: "{user_request}"
            
            Here are the existing functions:
            {chr(10).join(function_descriptions)}
            
            Can any of these functions fulfill the user's request? If yes, which one?
            Respond in this format:
            MATCH: [function_name or "none"]
            REASON: [brief explanation]
            """
            
            response = await self.claude.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            
            analysis = response.content[0].text
            logger.debug(f"Claude function analysis: {analysis}")
            
            # Parse Claude's response
            if "MATCH: none" in analysis.lower():
                return None, None
                
            # Extract function name
            for line in analysis.split('\n'):
                if line.startswith('MATCH:'):
                    func_name = line.split(':')[1].strip()
                    if func_name in self.function_registry:
                        return func_name, self.function_registry[func_name]
                        
            return None, None
            
        except Exception as e:
            logger.error(f"Error finding matching function: {str(e)}")
            return None, None

    def add_function(self, function_code: str) -> bool:
        """Add a new function to the codebase"""
        try:
            # Parse the function code
            tree = ast.parse(function_code)
            function_def = next(node for node in tree.body if isinstance(node, ast.FunctionDef))
            function_name = function_def.name
            
            logger.debug(f"Adding function: {function_name}")
            
            # Parse current file
            current_tree = ast.parse(self.current_code)
            
            # Find the WordPressAPI class
            class_node = None
            for node in ast.walk(current_tree):
                if isinstance(node, ast.ClassDef) and node.name == "WordPressAPI":
                    class_node = node
                    break
                    
            if not class_node:
                logger.error("WordPressAPI class not found")
                return False
                
            # Add new function to class
            class_node.body.append(function_def)
            
            # Generate new code
            new_code = ast.unparse(current_tree)
            
            # Write updated code back to file
            with open(self.filename, 'w') as f:
                f.write(new_code)
                
            # Update function registry
            self._analyze_existing_functions()
            
            logger.info(f"Successfully added function: {function_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding function: {str(e)}")
            return False