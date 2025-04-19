import json
import logging
from typing import Dict, List, Optional
from fuzzywuzzy import fuzz
from dataclasses import dataclass
from datetime import datetime
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class AttributeWithConfidence:
    label: str
    confidence: float

@dataclass
class ShoeAttributes:
    height: str
    colors: List[str]
    design: str
    gender: str = "unisex"
    season: Optional[str] = None
    category: Optional[AttributeWithConfidence] = None
    sub_category: Optional[AttributeWithConfidence] = None

class StyleMatcher:
    def __init__(self, config_path: str = '../config/style_config.json'):
        self.config = self._load_config(config_path)

    def _load_config(self, path: str) -> Dict:
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.abspath(os.path.join(script_dir, '..', '..', 'config', 'style_configure.json'))
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"Configuration file not found: {config_path}")
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            required_sections = ["shoe_rules", "color_rules", "fallback"]
            for section in required_sections:
                if section not in config:
                    logger.warning(f"Missing section in config: {section}. Using default values.")
                    config[section] = []
            return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise

    def _get_current_season(self) -> str:
        month = datetime.now().month
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        return "fall"

    def _match_color_rules(self, attributes: ShoeAttributes) -> Optional[Dict]:
        best_match = None
        highest_score = 0
        for rule in self.config.get("color_rules", []):
            primary_score = fuzz.ratio(rule["primary"].lower(), attributes.colors[0].lower() if attributes.colors else "")
            if primary_score < 70:
                continue
            secondary_score = 0
            if "secondary" in rule and len(attributes.colors) > 1:
                secondary_score = max(
                    fuzz.ratio(s.lower(), attributes.colors[1].lower()) for s in rule["secondary"]
                )
            total_score = (primary_score * 0.7 + secondary_score * 0.3) + rule.get("priority", 0)
            if total_score > highest_score:
                highest_score = total_score
                best_match = rule
        return best_match

    def _match_shoe_rules(self, attributes: ShoeAttributes) -> Optional[Dict]:
        best_match = None

        for rule in self.config.get("shoe_rules", []):
            if attributes.category and attributes.sub_category:
                # Direct match for category
                if rule.get("category", "").lower() == attributes.category.label.lower():

                    # Match sub_category: support list of subcategories in rule
                    rule_subcategories = rule.get("subcategories", [])
                    if isinstance(rule_subcategories, list):
                        subcategory_match = any(
                            sub.lower() == attributes.sub_category.label.lower()
                            for sub in rule_subcategories
                        )
                    else:
                        subcategory_match = rule_subcategories.lower() == attributes.sub_category.label.lower()

                    if subcategory_match:
                        # Gender handling (list or string in rules)
                        rule_gender = rule.get("gender", "unisex")
                        attribute_gender = attributes.gender.lower()

                        if isinstance(rule_gender, list):
                            rule_gender_list = [g.lower() for g in rule_gender]
                            selected_gender = attribute_gender if attribute_gender in rule_gender_list else "unisex"
                        else:
                            rule_gender_value = rule_gender.lower()
                            selected_gender = attribute_gender if attribute_gender == rule_gender_value else "unisex"

                        best_match = dict(rule)  # Make a copy to avoid modifying the original rule
                        best_match["selected_gender"] = selected_gender
                        break  # Found a match, exit

        return best_match

    def _match_design_rules(self, attributes: ShoeAttributes) -> Optional[Dict]:
        for rule in self.config.get("design_rules", []):
            if fuzz.ratio(rule["design"].lower(), attributes.design.lower()) > 80:
                return rule
        return None

    def _check_special_combos(self, attributes: ShoeAttributes) -> Optional[Dict]:
        for combo in self.config.get("special_combinations", []):
            if (self._color_match(combo["colors"][0], attributes.colors[0]) and
                (len(combo["colors"]) == 1 or self._color_match(combo["colors"][1], attributes.colors[1] if len(attributes.colors) > 1 else ""))):
                return combo["recommendations"]
        return None

    def _color_match(self, expected: str, actual: str) -> bool:
        return fuzz.ratio(expected.lower(), actual.lower()) > 70

    def _calculate_confidence(self, *matches: Optional[Dict]) -> float:
        weights = { 'shoe_match': 0.4, 'color_match': 0.4, 'design_match': 0.2 }
        score = 0.0
        total_weight = 0.0
        if matches[0]:
            score += weights['shoe_match'] * min(1.0, matches[0].get('priority', 1) / 5)
            total_weight += weights['shoe_match']
        if matches[1]:
            score += weights['color_match'] * min(1.0, matches[1].get('priority', 1) / 5)
            total_weight += weights['color_match']
        if matches[2]:
            score += weights['design_match'] * min(1.0, matches[2].get('priority', 1) / 5)
            total_weight += weights['design_match']
        return round(score / total_weight, 2) if total_weight > 0 else 0.0

    def _apply_fallbacks(self, recommendations: Dict) -> Dict:
        fallback = self.config["fallback"]
        return {
            "sock_types": recommendations.get("sock_types") or fallback.get("sock_types", []),
            "sock_colors": recommendations.get("sock_colors") or fallback.get("colors", []),
            "patterns": recommendations.get("patterns") or fallback.get("patterns", []),
            "materials": recommendations.get("materials") or [fallback.get("material", "default_material")],
            "match_type": recommendations.get("match_type", "fallback"),
            "confidence": recommendations.get("confidence", 0.0) * 0.8
                if any(not recommendations.get(k) for k in ["sock_types", "sock_colors", "patterns", "materials"])
                else recommendations.get("confidence", 0.0),
            "style_tip":recommendations.get("style_tip") or fallback.get("style_tip", [])

        }

    def _generate_style_tip(self, attributes: ShoeAttributes, shoe_match, color_match, design_match) -> str:
        style_parts = []
        if shoe_match:
            style_parts.append(f"chosen to complement your '{attributes.sub_category.label}' shoes")
        if color_match:
            primary_color = attributes.colors[0] if attributes.colors else "unknown color"
            style_parts.append(f"coordinated with the color '{primary_color}'")
        if design_match:
            style_parts.append(f"styled to match the '{attributes.design}' design theme")
        return (f"Suggested socks are {', '.join(style_parts)} — ideal for the {attributes.season} season."
                if style_parts else "No direct style rules matched — fallback suggestions provided for versatility.")

    def match(self, attributes: ShoeAttributes) -> Dict:
        try:
            if not attributes.season:
                attributes.season = self._get_current_season()
            match_details = {"shoe_rule_matched": False, "color_rule_matched": False, "design_rule_matched": False, "special_combo_matched": False, "rules_applied": []}
            special_match = self._check_special_combos(attributes)
            if special_match:
                match_details.update({"special_combo_matched": True, "rules_applied": ["special_combination"]})
                return {**special_match, "match_type": "special_combo", "confidence": 0.85, "match_details": match_details}
            shoe_match = self._match_shoe_rules(attributes)
            color_match = self._match_color_rules(attributes)
            design_match = self._match_design_rules(attributes)
            if shoe_match:
                match_details.update({"shoe_rule_matched": True, "rules_applied": match_details["rules_applied"] + ["shoe_rule"]})
            if color_match:
                match_details.update({"color_rule_matched": True, "rules_applied": match_details["rules_applied"] + ["color_rule"]})
            if design_match:
                match_details.update({"design_rule_matched": True, "rules_applied": match_details["rules_applied"] + ["design_rule"]})
            confidence = self._calculate_confidence(shoe_match, color_match, design_match)
            recommendations = {
                "sock_types": shoe_match.get("recommended_socks", []) if shoe_match else [],
                "sock_colors": color_match.get("recommended_colors", []) if color_match else [],
                "patterns": design_match.get("recommended_patterns", []) if design_match else [],
                "materials": list(set((shoe_match.get("material", []) if shoe_match else []) + (design_match.get("material", []) if design_match else []))),
                "primary_color": attributes.colors[0] if attributes.colors else "",
                "secondary_color": attributes.colors[1] if len(attributes.colors) > 1 else "",
                "style_tip": self._generate_style_tip(attributes, shoe_match, color_match, design_match),
                "match_type": "standard_rules",
                "confidence": confidence,
                "match_details": match_details
            }
            return self._apply_fallbacks(recommendations)
        except Exception as e:
            logger.error(f"Matching failed: {e}")
            fallback = self.config.get("fallback", {})
            return {"sock_types": fallback.get("sock_types", []), "sock_colors": fallback.get("colors", []), "patterns": fallback.get("patterns", []), "materials": [fallback.get("material", "default_material")], "match_type": "fallback", "confidence": 0.0, "error": str(e), "match_details": {"fallback_used": True, "reason": str(e)}}
