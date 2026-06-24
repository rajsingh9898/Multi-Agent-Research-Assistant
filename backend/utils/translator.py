"""Multi-language translation and localization utilities for research reports.

This module maps target languages to LLM instruction prompts, UI label maps,
and language metadata for UI selections (English, Hindi, Spanish).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES: Dict[str, Dict[str, str]] = {
    "english": {
        "name": "English",
        "code": "en",
        "native": "English",
        "flag": "🇬🇧",
    },
    "hindi": {
        "name": "Hindi",
        "code": "hi",
        "native": "हिन्दी",
        "flag": "🇮🇳",
    },
    "spanish": {
        "name": "Spanish",
        "code": "es",
        "native": "Español",
        "flag": "🇪🇸",
    },
}


def validate_language(language: str) -> str:
    """Validate if the language is supported, fallback to 'english' and log warning if not."""
    if not language:
        return "english"

    lang_lower = language.strip().lower()
    if lang_lower in SUPPORTED_LANGUAGES:
        return lang_lower

    logger.warning(f"Unsupported language requested: '{language}'. Falling back to 'english'.")
    return "english"


def get_language_prompt(language: str) -> str:
    """Return specific prompt instructions for the LLM agent to write in target language."""
    valid_lang = validate_language(language)

    if valid_lang == "english":
        return "Write the report in clear, professional English."
    elif valid_lang == "hindi":
        return (
            "Write the entire report in Hindi (हिन्दी). Use Devanagari script. "
            "Keep technical terms in English where Hindi equivalent is unclear."
        )
    elif valid_lang == "spanish":
        return (
            "Write the entire report in Spanish (Español). Use formal Spanish "
            "suitable for academic writing."
        )

    return "Write the report in clear, professional English."


def get_report_labels(language: str) -> Dict[str, str]:
    """Return localized section headers and status labels for final report structures."""
    valid_lang = validate_language(language)

    if valid_lang == "hindi":
        return {
            "executive_summary": "कार्यकारी सारांश",
            "key_findings": "मुख्य निष्कर्ष",
            "detailed_analysis": "विस्तृत विश्लेषण",
            "limitations": "सीमाएं",
            "conclusion": "निष्कर्ष",
            "sources": "स्रोत",
            "confidence": "विश्वास स्कोर",
            "verified": "सत्यापित",
            "uncertain": "अनिश्चित",
        }
    elif valid_lang == "spanish":
        return {
            "executive_summary": "Resumen Ejecutivo",
            "key_findings": "Hallazgos Clave",
            "detailed_analysis": "Análisis Detallado",
            "limitations": "Limitaciones",
            "conclusion": "Conclusión",
            "sources": "Fuentes",
            "confidence": "Puntuación de Confianza",
            "verified": "Verificado",
            "uncertain": "Incierto",
        }

    # Default to English
    return {
        "executive_summary": "Executive Summary",
        "key_findings": "Key Findings",
        "detailed_analysis": "Detailed Analysis",
        "limitations": "Limitations",
        "conclusion": "Conclusion",
        "sources": "Sources",
        "confidence": "Confidence Score",
        "verified": "Verified",
        "uncertain": "Uncertain",
    }


def get_all_languages() -> List[Dict[str, str]]:
    """Return list of supported languages containing metadata configurations."""
    result = []
    for key, val in SUPPORTED_LANGUAGES.items():
        result.append(
            {
                "key": key,
                "name": val["name"],
                "native": val["native"],
                "flag": val["flag"],
            }
        )
    return result
