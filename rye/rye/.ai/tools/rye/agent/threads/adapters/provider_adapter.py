__version__ = "1.0.0"

from typing import Any, Dict, List


class ProviderAdapter:
    """Abstract interface for LLM providers.

    Each provider implementation translates to/from the provider's native API.
    The runner calls only these methods.
    """

    def __init__(self, model: str, provider_config: Dict):
        self.model = model
        self.config = provider_config

    async def create_completion(self, messages: List[Dict], tools: List[Dict]) -> Dict:
        """Send messages to LLM and return structured response.

        Args:
            messages: List of {"role": str, "content": str} message dicts
            tools: List of tool schemas the LLM can call

        Returns:
            {
                "text": str,
                "tool_calls": [
                    {
                        "id": str,
                        "name": str,
                        "input": Dict,
                    }
                ],
                "input_tokens": int,
                "output_tokens": int,
                "spend": float,
                "finish_reason": str,
            }
        """
        raise NotImplementedError(
            f"No provider implementation for model '{self.model}'. "
            "Subclass ProviderAdapter and implement create_completion()."
        )

    async def create_streaming_completion(
        self, messages: List[Dict], tools: List[Dict]
    ):
        """Streaming variant — yields chunks."""
        raise NotImplementedError(
            f"No streaming provider implementation for model '{self.model}'. "
            "Subclass ProviderAdapter and implement create_streaming_completion()."
        )
