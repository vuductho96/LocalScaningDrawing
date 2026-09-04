"""
Vision AI Grounding Module.
Connects to Multimodal Vision LLMs (e.g. Gemini 2.5 Flash / Pro) to determine computer use actions.
"""

import os
import re
import json
import logging
from typing import Optional, List, Dict, Any, Union, Tuple
from PIL import Image

from computer_use.config import default_config, ComputerUseConfig
from computer_use.types import ComputerAction, ActionType
from computer_use.ai.prompts import COMPUTER_USE_SYSTEM_PROMPT

logger = logging.getLogger("computer_use.grounding")


class VisionGrounding:
    """
    Multimodal Vision Grounding Client for Computer Use.
    """

    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None, config: Optional[ComputerUseConfig] = None):
        self.config = config or default_config
        self.api_key = api_key or self.config.api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.model_name = model_name or self.config.gemini_model_name
        self.client = None
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            logger.warning("No GEMINI_API_KEY or GOOGLE_API_KEY found. Vision grounding will require manual key passing.")
            return

        try:
            # Try new google.genai SDK first
            from google import genai
            self.client = genai.Client(api_key=self.api_key)
            self.client_type = "genai"
            logger.info("Initialized Google GenAI client.")
        except Exception:
            try:
                # Fallback to google.generativeai
                import google.generativeai as genai_legacy
                genai_legacy.configure(api_key=self.api_key)
                self.client = genai_legacy.GenerativeModel(self.model_name)
                self.client_type = "generativeai_legacy"
                logger.info("Initialized legacy google.generativeai client.")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.client = None

    def _clean_json_response(self, text: str) -> Dict[str, Any]:
        """Extracts and parses JSON object from model response text."""
        text = text.strip()
        
        # Match ```json ... ``` blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try finding the first '{' and last '}'
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                json_str = text[start:end + 1]
            else:
                json_str = text

        return json.loads(json_str)

    def predict_next_action(
        self,
        image: Image.Image,
        goal: str,
        history: Optional[List[Dict[str, Any]]] = None,
        screen_size: Optional[Tuple[int, int]] = None
    ) -> ComputerAction:
        """
        Sends current screenshot and goal to Gemini Vision model and returns the parsed ComputerAction.
        """
        if not self.client:
            self._init_client()
            if not self.client:
                raise ValueError("Vision client is not initialized. Please configure GEMINI_API_KEY.")

        screen_w, screen_h = screen_size or image.size

        # Format prompt
        history_text = ""
        if history:
            history_text = "PREVIOUS ACTIONS PERFORMED:\n"
            for i, h in enumerate(history[-5:], 1):
                history_text += f"{i}. Action: {h.get('action')}, Details: {h.get('details')}, Message: {h.get('message')}\n"
        else:
            history_text = "No previous actions yet."

        user_prompt = f"""Current screen resolution: {screen_w}x{screen_h}

OBJECTIVE / GOAL:
{goal}

{history_text}

Analyze the current screen and decide the next single action to achieve the objective.
Remember to return ONLY the raw JSON object adhering to the schema.
"""

        try:
            if getattr(self, "client_type", None) == "genai":
                from google.genai import types
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[
                        COMPUTER_USE_SYSTEM_PROMPT,
                        user_prompt,
                        image
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json"
                    )
                )
                response_text = response.text
            else:
                # Legacy SDK
                response = self.client.generate_content(
                    [COMPUTER_USE_SYSTEM_PROMPT, user_prompt, image],
                    generation_config={"temperature": 0.1}
                )
                response_text = response.text

            logger.info(f"Model raw output: {response_text}")
            parsed = self._clean_json_response(response_text)
            
            # Map action string to ActionType
            action_type_str = parsed.get("action", "done").lower()
            try:
                act_type = ActionType(action_type_str)
            except ValueError:
                # Fallback mapping
                act_type = ActionType.DONE if "done" in action_type_str else ActionType.LEFT_CLICK

            return ComputerAction(
                action=act_type,
                x=parsed.get("x"),
                y=parsed.get("y"),
                text=parsed.get("text"),
                key=parsed.get("key"),
                keys=parsed.get("keys"),
                clicks=parsed.get("clicks", 1),
                direction=parsed.get("direction", "vertical"),
                duration=parsed.get("duration"),
                reasoning=parsed.get("reasoning", "")
            )

        except Exception as e:
            logger.error(f"Error predicting action with Vision AI: {e}", exc_info=True)
            return ComputerAction(
                action=ActionType.FAIL,
                reasoning=f"Vision model prediction failed: {str(e)}"
            )
