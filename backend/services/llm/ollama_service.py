"""Service for handling Ollama interactions"""
import os
import json
from typing import List, Dict, Any, Tuple
import requests
import logging

logger = logging.getLogger(__name__)

class OllamaService:
    def __init__(self):
        self.base_url = os.getenv('OLLAMA_API_URL', 'http://localhost:11434')
        self.model_name = os.getenv('OLLAMA_MODEL', 'mistral')
        
        try:
            # Test connection
            health_check = requests.get(f"{self.base_url}")
            health_check.raise_for_status()
            logger.info(f"✅ Connected to Ollama at {self.base_url}")
        except Exception as e:
            error_msg = f"Failed to initialize Ollama service: {str(e)}"
            logger.error(f"❌ {error_msg}")
            raise RuntimeError(error_msg)

    def check_health(self) -> Tuple[bool, str]:
        """Check if the service is healthy"""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model_name,
                    "prompt": "Test connection",
                    "stream": False
                }
            )
            response.raise_for_status()
            return True, "Ollama service is healthy"
        except requests.exceptions.ConnectionError:
            return False, "Ollama service is not reachable"
        except requests.exceptions.HTTPError as e:
            return False, f"Ollama service returned HTTP error: {str(e)}"
        except Exception as e:
            return False, f"Ollama service health check failed: {str(e)}"

    def process_batch(self, prompts: List[str]) -> List[Dict[str, Any]]:
        """Process a batch of prompts"""
        results = []
        for prompt in prompts:
            try:
                # Add JSON instruction
                prompt = f"{prompt}\nReturn a single JSON object only. No other text."
                
                # Call API
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False
                    }
                )
                response.raise_for_status()
                
                # Get response text
                text = response.json().get("response", "").strip()
                results.append({"response": text})
            except requests.exceptions.ConnectionError:
                results.append({
                    "error": "Ollama service is not reachable",
                    "error_type": "critical"
                })
                break
            except requests.exceptions.HTTPError as e:
                results.append({
                    "error": f"Ollama service error: {str(e)}",
                    "error_type": "critical"
                })
                break
            except Exception as e:
                results.append({
                    "error": f"Unexpected error: {str(e)}",
                    "error_type": "critical"
                })
                break
                
        return results