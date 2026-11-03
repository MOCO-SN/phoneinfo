"""
LeakOSINT API Client & Service
Documentation Reference: https://leakosintapi.com/
"""

import os
import re
import math
import requests
from typing import Optional, Dict, Any, List, Union, Tuple

DEFAULT_API_URL = "https://leakosintapi.com/"

def calculate_query_complexity(query: Union[str, List[str]]) -> Tuple[int, int, List[str]]:
    """
    Calculates search query complexity based on the documentation formula:
    - 1 word: Complexity = 1
    - 2 words: Complexity = 5
    - 3 words: Complexity = 16
    - More than 3 words: Complexity = 40
    
    Elements NOT considered words:
    - Dates (e.g. YYYY-MM-DD, DD.MM.YYYY)
    - Strings shorter than 4 characters
    - Numbers shorter than 6 characters
    Phrases in double quotes are treated as one word.
    """
    if isinstance(query, list):
        query_str = " ".join(str(item) for item in query)
    else:
        query_str = str(query)

    # Extract quoted phrases as single words
    quoted = re.findall(r'"([^"]+)"', query_str)
    unquoted = re.sub(r'"[^"]+"', ' ', query_str)

    words = []
    for q in quoted:
        if q.strip():
            words.append(q.strip())

    for w in unquoted.split():
        w_clean = w.strip('.,!?:;()[]{}<>"\'')
        if not w_clean:
            continue
        # Check if date format
        if re.match(r'^\d{1,4}[-./]\d{1,2}[-./]\d{1,4}$', w_clean):
            continue
        # Numbers shorter than 6 characters
        if w_clean.isdigit() and len(w_clean) < 6:
            continue
        # Lines / words shorter than 4 characters
        if len(w_clean) < 4:
            continue
        words.append(w_clean)

    count = len(words)
    if count <= 1:
        complexity = 1
    elif count == 2:
        complexity = 5
    elif count == 3:
        complexity = 16
    else:
        complexity = 40

    return complexity, count, words


def calculate_estimated_price(limit: int, complexity: int) -> float:
    """
    Formula from documentation:
    Price ($) = 0.0002 * (5 + sqrt(Limit * Complexity))
    """
    try:
        lim = max(100, min(int(limit), 10000))
    except (ValueError, TypeError):
        lim = 100
    return 0.0002 * (5 + math.sqrt(lim * complexity))


class LeakOSINTClient:
    def __init__(self, token: Optional[str] = None, api_url: str = DEFAULT_API_URL):
        self.token = token or os.environ.get("LEAKOSINT_API_TOKEN", "").strip()
        self.api_url = api_url

    def search(
        self,
        query: Union[str, List[str]],
        token: Optional[str] = None,
        limit: int = 100,
        lang: str = "en",
        report_type: str = "json",
        bot_name: Optional[str] = None,
        timeout: int = 20,
    ) -> Dict[str, Any]:
        """
        Executes search against LeakOSINT API.
        
        Parameters:
        - query: String or list of strings to search (phone, email, name, etc.)
        - token: API token override
        - limit: Number of results / search depth (100 - 10000, default 100)
        - lang: Language code for results ('en', 'ru', etc.)
        - report_type: 'json', 'short', or 'html' (default 'json')
        - bot_name: Optional bot name in '@name' format
        - timeout: HTTP request timeout in seconds
        """
        active_token = (token or self.token or "").strip()
        
        # Calculate complexity and price estimate
        complexity, word_count, words = calculate_query_complexity(query)
        estimated_price = calculate_estimated_price(limit, complexity)

        if not active_token:
            return {
                "success": False,
                "needs_token": True,
                "error": "No API token provided. Please enter your LeakOSINT token or set LEAKOSINT_API_TOKEN.",
                "complexity": complexity,
                "word_count": word_count,
                "words": words,
                "estimated_price": f"${estimated_price:.5f}",
                "databases": [],
                "total_databases": 0,
                "total_records": 0,
                "has_results": False,
            }

        # Clamp limit between 100 and 10000
        try:
            limit_val = max(100, min(int(limit), 10000))
        except (ValueError, TypeError):
            limit_val = 100

        payload: Dict[str, Any] = {
            "token": active_token,
            "request": query,
            "limit": limit_val,
            "lang": lang or "en",
            "type": report_type or "json",
        }
        if bot_name:
            payload["bot_name"] = bot_name

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "PhoneInfo-LeakOSINT-Agent/1.0"
        }

        try:
            # Query must be sent as JSON in POST body according to documentation
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=timeout)
            
            # Handle HTTP errors
            if response.status_code == 501:
                return {
                    "success": False,
                    "error": "Server error 501: Ensure request body is formatted as valid JSON.",
                    "complexity": complexity,
                    "estimated_price": f"${estimated_price:.5f}",
                    "databases": [],
                    "has_results": False,
                }
            
            try:
                res_json = response.json()
            except Exception:
                return {
                    "success": False,
                    "error": f"Invalid JSON response from server (Status {response.status_code}): {response.text[:200]}",
                    "complexity": complexity,
                    "estimated_price": f"${estimated_price:.5f}",
                    "databases": [],
                    "has_results": False,
                }

            # Check for API error response
            if isinstance(res_json, dict) and "Error code" in res_json:
                error_msg = res_json["Error code"]
                return {
                    "success": False,
                    "error": f"LeakOSINT API Error: {error_msg}",
                    "error_code": error_msg,
                    "complexity": complexity,
                    "estimated_price": f"${estimated_price:.5f}",
                    "databases": [],
                    "has_results": False,
                }

            # Parse results list
            databases_list = []
            total_records = 0
            has_results = False

            if isinstance(res_json, dict) and "List" in res_json:
                db_dict = res_json["List"]
                if isinstance(db_dict, dict):
                    for db_name, db_content in db_dict.items():
                        if db_name == "No results found":
                            continue
                        
                        info_leak = ""
                        records = []
                        if isinstance(db_content, dict):
                            info_leak = db_content.get("InfoLeak", "")
                            raw_data = db_content.get("Data", [])
                            if isinstance(raw_data, list):
                                records = raw_data
                        
                        rec_count = len(records)
                        total_records += rec_count
                        if rec_count > 0:
                            has_results = True

                        databases_list.append({
                            "name": db_name,
                            "info_leak": info_leak,
                            "records": records,
                            "count": rec_count,
                        })

            return {
                "success": True,
                "has_results": has_results,
                "query": query,
                "limit": limit_val,
                "lang": lang,
                "complexity": complexity,
                "word_count": word_count,
                "words": words,
                "estimated_price": f"${estimated_price:.5f}",
                "total_databases": len(databases_list),
                "total_records": total_records,
                "databases": databases_list,
                "raw_response": res_json,
            }

        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Request timed out while connecting to LeakOSINT API. Please try again.",
                "complexity": complexity,
                "estimated_price": f"${estimated_price:.5f}",
                "databases": [],
                "has_results": False,
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Network error connecting to LeakOSINT API: {str(e)}",
                "complexity": complexity,
                "estimated_price": f"${estimated_price:.5f}",
                "databases": [],
                "has_results": False,
            }
