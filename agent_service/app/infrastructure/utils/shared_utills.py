from pathlib import Path
from typing import Dict, List, Any
from app.infrastructure.utils.file_utils import read_json_file
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def safe_strip(value: Any, default: str = "") -> str:
    """
    Safely strip whitespace from a value.
    
    Args:
        value: Any value to strip
        default: Default value if None or not a string
        
    Returns:
        Stripped string or default
    """
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip() if value else default


def _extract_target_language_from_scan(migration_dir: Path) -> str | None:
    """
    Extract target language from target_scanner_output.json if it exists.
    Returns the primary language detected in the target project.
    """
    try:
        target_scanner_file = migration_dir / "target_scanner_output.json"
        
        if not target_scanner_file.exists():
            logger.debug("No target_scanner_output.json found")
            return None
        
        target_data = read_json_file(str(target_scanner_file))
        
        # Add None safety checks
        if not target_data:
            logger.debug("target_scanner_output.json is empty")
            return None
            
        tech_data = target_data.get('tech_data', {})
        if not tech_data:
            logger.debug("No tech_data found in target_scanner_output.json")
            return None
        
        # Use safe_strip instead of direct .strip()
        target_language = safe_strip(tech_data.get('language', ''))
        
        if target_language and target_language.lower() not in ['unknown', 'none', '']:
            logger.info(f"✅ Target language auto-detected from target project: {target_language}")
            return target_language
        
        logger.debug("No valid language found in target_scanner_output.json")
        return None
        
    except Exception as e:
        logger.error(f"Failed to extract target language from scan: {e}")
        return None


def extract_target_tech_stack(migration_dir: Path) -> Dict[str, Any] | None:
    """
    Extract complete tech stack from target project scan.
    Returns framework, language, build_tool, architecture from target.
    """
    try:
        target_scanner_file = migration_dir / "target_scanner_output.json"
        
        if not target_scanner_file.exists():
            logger.debug("No target_scanner_output.json found")
            return None
        
        target_data = read_json_file(str(target_scanner_file))
        
        # Add None safety checks
        if not target_data:
            logger.debug("target_scanner_output.json is empty")
            return None
            
        tech_data = target_data.get('tech_data', {})
        if not tech_data:
            logger.debug("No tech_data found in target_scanner_output.json")
            return None
        
        # Use safe_strip for all string fields
        target_tech_stack = {
            "language": safe_strip(tech_data.get('language', '')),
            "framework": safe_strip(tech_data.get('framework', '')),
            "build_tool": safe_strip(tech_data.get('build_tool', ''), 'No build tool'),
            "architecture": safe_strip(tech_data.get('architecture', ''), 'Unknown'),
            "extensions": tech_data.get('extensions', []) or [],
            "libraries": tech_data.get('libraries', []) or [],
            "technologies": tech_data.get('Technologies', []) or []
        }
        
        # Validate we have meaningful data
        if target_tech_stack['language'] and target_tech_stack['language'].lower() not in ['unknown', 'none', '']:
            logger.info(f"✅ Target tech stack extracted: {target_tech_stack['language']} / {target_tech_stack['framework']}")
            return target_tech_stack
        
        logger.debug("No valid tech stack found in target_scanner_output.json")
        return None
        
    except Exception as e:
        logger.error(f"Failed to extract target tech stack: {e}", exc_info=True)
        return None