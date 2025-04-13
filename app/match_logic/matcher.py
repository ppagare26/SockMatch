import os
import json
import logging
from typing import Dict
from openai import OpenAI

from .image_preprocessing import detect_and_process_shoe, extract_shoe_attributes
from .match_socks_rule import StyleMatcher, ShoeAttributes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



class SockRecommender:
    def __init__(self):
        self.matcher = StyleMatcher()
        api_key =""
        self.client = None

    def gpt_refine(self, context: Dict) -> Dict:
        prompt = f"""
        You are a fashion expert helping match socks to shoes.

        Shoe:
        - Type: {context['shoe_analysis']['type']}
        - Height: {context['shoe_analysis']['height']}
        - Primary color: {context['shoe_analysis']['primary_color']}
        - Accent color: {context['shoe_analysis'].get('accent_color')}
        - Secondary color: {context['shoe_analysis'].get('secondary_color')}
        - Design: {context['shoe_analysis']['design']}
        - Season: {context['metadata']['season']}
        - Gender: {context.get('gender', 'unisex')}

        Initial sock recommendation:
        - Types: {context['recommendations']['types']}
        - Colors: {context['recommendations']['colors']}
        - Patterns: {context['recommendations']['patterns']}
        - Materials: {context['recommendations']['materials']}

        Please:
        1. Refine the sock recommendation (keep it realistic)
        2. Add a fashion-forward style tip
        3. Keep it concise and return a JSON like:
        {{
            "refined_types": [...],
            "refined_colors": [...],
            "refined_patterns": [...],
            "refined_materials": [...],
            "style_tip": "..."
        }}
        """

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return eval(content)

    def match_socks(self, image_path: str, gender: str = "unisex") -> Dict:
        try:
            shoe_image = detect_and_process_shoe(image_path)
            attributes = extract_shoe_attributes(shoe_image)

            if attributes.get("error"):
                raise ValueError(attributes["error"])

            colors = [c.lower() for c in attributes.get("colors", [])]
            shoe_attrs = ShoeAttributes(
                shoe_type=attributes.get("type", "generic").lower(),
                height=attributes.get("height", "low").lower(),
                colors=colors,
                design=attributes.get("design", "solid").lower(),
                gender=gender.lower()
            )

            recommendations = self.matcher.match(shoe_attrs)

            primary_color = colors[0] if colors else "neutral"
            accent_color = colors[1] if len(colors) > 1 else None
            secondary_color = colors[2] if len(colors) > 2 else None

            base_response = {
                "shoe_analysis": {
                    "type": shoe_attrs.shoe_type,
                    "height": shoe_attrs.height,
                    "primary_color": primary_color,
                    "accent_color": accent_color,
                    "secondary_color": secondary_color,
                    "design": shoe_attrs.design,
                    "season": shoe_attrs.season
                },
                "recommendations": {
                    "types": recommendations["sock_types"],
                    "colors": recommendations["sock_colors"],
                    "patterns": recommendations["patterns"],
                    "materials": recommendations["materials"]
                },
                "metadata": {
                    "match_type": recommendations["match_type"],
                    "confidence": round(recommendations.get("confidence", 0), 2),
                    "season": shoe_attrs.season,
                    "match_details": recommendations.get("match_details", {}),
                    "special_combo_match": recommendations.get("special_combo_match"),
                    "fallback_used": recommendations.get("fallback_used", False)
                },
                "error": None,
                "style_tip": None,
                "gender": gender
            }

            # gpt_refinement = self.gpt_refine(base_response)
            #
            # base_response["recommendations"] = {
            #     "types": gpt_refinement["refined_types"],
            #     "colors": gpt_refinement["refined_colors"],
            #     "patterns": gpt_refinement["refined_patterns"],
            #     "materials": gpt_refinement["refined_materials"]
            # }
            # base_response["style_tip"] = gpt_refinement["style_tip"]

            return base_response

        except Exception as e:
            logger.error(f"Recommendation failed: {e}")
            return {
                "shoe_analysis": None,
                "recommendations": self.matcher.config["fallback"],
                "metadata": {
                    "match_type": "error",
                    "confidence": 0,
                    "fallback_used": True
                },
                "style_tip": None,
                "error": str(e)
            }