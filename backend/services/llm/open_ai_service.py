"""Service for handling OpenAI API interactions"""
import os
from typing import List, Dict, Any, Tuple
from openai import OpenAI

class OpenAIService:
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key not found")
        self.client = OpenAI(api_key=self.api_key)
        self.model_name = "gpt-3.5-turbo"

    def check_health(self) -> Tuple[bool, str]:
        """Check if the service is healthy and responding"""
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "Test connection"}],
                max_tokens=5
            )
            return True, "OpenAI service is healthy"
        except Exception as e:
            return False, f"OpenAI service health check failed: {str(e)}"

    def process_batch(self, prompts: List[str]) -> List[Dict[str, Any]]:
        """Process a batch of prompts using OpenAI"""
        results = []
        for prompt in prompts:
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that returns responses in JSON format."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=1000,
                    temperature=0.7
                )
                results.append({"response": response.choices[0].message.content})
            except Exception as e:
                results.append({"error": str(e)})
        return results