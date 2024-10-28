import requests
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
        self.wp_url = os.getenv('WP_URL')
        self.wp_username = os.getenv('WP_USERNAME')
        self.wp_password = os.getenv('WP_APP_PASSWORD')
        if not all([self.wp_url, self.wp_username, self.wp_password]):
            missing = []
            if not self.wp_url:
                missing.append('WP_URL')
            if not self.wp_username:
                missing.append('WP_USERNAME')
            if not self.wp_password:
                missing.append('WP_APP_PASSWORD')
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        logging.debug(f'Initialized WordPress API with URL: {self.wp_url}')

    def test_connection(self) -> bool:
        """Test WordPress connection"""
        try:
            response = requests.get(f'{self.wp_url}/posts', auth=(self.wp_username, self.wp_password), timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            raise ConnectionError(f'Failed to connect to WordPress: {str(e)}')

    def get_pages(self) -> List[Dict[str, Any]]:
        """Get all pages"""
        try:
            response = requests.get(f'{self.wp_url}/pages', auth=(self.wp_username, self.wp_password), timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f'Error getting pages: {str(e)}')
            raise WordPressAPIError(f'Failed to get pages: {str(e)}')

    def get_post(self, post_id: int) -> Dict[str, Any]:
        """
    Retrieves a specific post from WordPress by its ID.

    Args:
        post_id (int): The ID of the post to retrieve.

    Returns:
        Dict[str, Any]: The retrieved post data as a dictionary.

    Raises:
        requests.exceptions.RequestException: If an error occurs during the API request.
        ValueError: If the API response is not valid JSON.
        KeyError: If the 'id' key is missing from the API response.
    """
        try:
            url = f'{self.wp_url}/wp-json/wp/v2/posts/{post_id}'
            response = requests.get(url, auth=(self.wp_username, self.wp_password))
            response.raise_for_status()
            post_data = response.json()
            if 'id' not in post_data:
                raise KeyError("'id' key missing from API response")
            return post_data
        except requests.exceptions.RequestException as e:
            logging.error(f'Error occurred while retrieving post: {e}')
            raise
        except (ValueError, KeyError) as e:
            logging.error(f'Invalid API response: {e}')
            raise

    def get_pages(self) -> List[Dict[str, Any]]:
        """
    Retrieves all pages from the WordPress website.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries representing the pages.

    Raises:
        requests.exceptions.RequestException: If an error occurs during the API request.
        WordPressAPIError: If the API response contains an error message.
    """
        try:
            response = requests.get(f'{self.wp_url}/wp-json/wp/v2/pages', auth=(self.wp_username, self.wp_password))
            if response.status_code == 200:
                pages = response.json()
                logging.info(f'Successfully retrieved {len(pages)} pages from {self.wp_url}')
                return pages
            else:
                error_message = f'Failed to retrieve pages. Status code: {response.status_code}'
                logging.error(error_message)
                raise WordPressAPIError(error_message)
        except requests.exceptions.RequestException as e:
            error_message = f'An error occurred while making the API request: {str(e)}'
            logging.exception(error_message)
            raise
        except json.JSONDecodeError as e:
            error_message = f'Failed to parse the API response as JSON: {str(e)}'
            logging.exception(error_message)
            raise WordPressAPIError(error_message)
        except Exception as e:
            error_message = f'An unexpected error occurred: {str(e)}'
            logging.exception(error_message)
            raise