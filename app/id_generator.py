"""
ID Generator for Poster Management System.

Generates poster IDs using configurable templates with variable substitution.
"""
import re
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

from .config import config_loader

logger = logging.getLogger(__name__)


class IDGenerationError(Exception):
    """Raised when ID generation fails."""


class IDGenerator:
    """Generates poster IDs from template patterns."""
    
    # Regex to match template variables: {{var}} or {{var:format}}
    VAR_PATTERN = re.compile(r'\{\{(\w+)(?::([^}]+))?\}\}')
    
    def __init__(self, config_loader_instance=None):
        self.config_loader = config_loader_instance or config_loader
    
    def get_default_template(self) -> Optional[Dict[str, Any]]:
        """Get the default ID template from configuration."""
        config = self.config_loader.load_id_templates_config()
        templates = config.get('templates', [])
        for template in templates:
            if template.get('default'):
                return template
        return None
    
    def parse_template(self, template_pattern: str) -> Tuple[str, list]:
        """
        Parse template pattern and extract variables.
        
        Returns:
            Tuple of (format_string, variable_names)
            where format_string has {{var}} replaced with {} placeholders
            and variable_names is list of (var_name, format_spec) tuples.
        """
        variables = []
        format_parts = []
        last_pos = 0
        
        for match in self.VAR_PATTERN.finditer(template_pattern):
            # Text before match
            format_parts.append(re.escape(template_pattern[last_pos:match.start()]))
            var_name = match.group(1)
            format_spec = match.group(2) or ''
            variables.append((var_name, format_spec))
            # Replace with placeholder
            format_parts.append('{}')
            last_pos = match.end()
        
        # Remaining text
        format_parts.append(re.escape(template_pattern[last_pos:]))
        format_string = ''.join(format_parts)
        
        # Unescape the format string (we only needed to escape for regex replacement)
        # Actually we should not escape; we need to keep original literal parts.
        # Let's rebuild without escaping.
        format_parts = []
        last_pos = 0
        
        for match in self.VAR_PATTERN.finditer(template_pattern):
            format_parts.append(template_pattern[last_pos:match.start()])
            format_parts.append('{}')
            last_pos = match.end()
        format_parts.append(template_pattern[last_pos:])
        format_string = ''.join(format_parts)
        
        return format_string, variables
    
    def generate_id(self, context: Dict[str, Any]) -> str:
        """
        Generate an ID using the default template.
        
        Args:
            context: Dictionary with variable values (category_code, source_code, etc.)
        
        Returns:
            Generated ID string
        """
        template = self.get_default_template()
        if not template:
            raise IDGenerationError("No default ID template configured")
        
        pattern = template['pattern']
        return self.generate_id_from_pattern(pattern, context)
    
    def generate_id_from_pattern(self, pattern: str, context: Dict[str, Any]) -> str:
        """
        Generate an ID from a specific pattern.
        
        Args:
            pattern: Template pattern string
            context: Dictionary with variable values
        
        Returns:
            Generated ID string
        """
        format_string, variables = self.parse_template(pattern)
        
        # Prepare values for substitution
        values = []
        for var_name, format_spec in variables:
            if var_name == 'seq':
                # Get next sequence number for this pattern
                seq = self._get_next_sequence(pattern, context)
                if format_spec:
                    # Apply formatting (e.g., '04d' -> zero-pad to 4 digits)
                    try:
                        # Python format spec: need to convert to int first
                        seq = int(seq)
                        values.append(f"{seq:{format_spec}}")
                    except (ValueError, TypeError):
                        # Fallback to string representation
                        values.append(str(seq))
                else:
                    values.append(str(seq))
            else:
                # Get value from context
                value = context.get(var_name, '')
                if format_spec:
                    # Apply formatting if specified
                    try:
                        # For non-seq variables, format spec might be something else
                        values.append(f"{value:{format_spec}}")
                    except (ValueError, TypeError):
                        values.append(str(value))
                else:
                    values.append(str(value))
        
        # Substitute values into format string
        result = format_string.format(*values)
        return result
    
    def _get_next_sequence(self, pattern: str, context: Dict[str, Any]) -> int:
        """
        Get next sequence number for a pattern, incrementing the counter.
        
        The counter is stored in the ID templates configuration.
        Uses pattern as key in counters dict.
        """
        config = self.config_loader.load_id_templates_config()
        counters = config.get('counters', {})
        
        # Use pattern as counter key
        current = counters.get(pattern, 1)
        
        # Increment counter and save
        counters[pattern] = current + 1
        config['counters'] = counters
        self.config_loader.save_id_templates_config(config)
        
        return current
    
    def preview_id(self, context: Dict[str, Any]) -> str:
        """
        Preview an ID without incrementing the sequence counter.
        
        Useful for showing users what ID will be generated.
        """
        template = self.get_default_template()
        if not template:
            return "No template configured"
        
        pattern = template['pattern']
        format_string, variables = self.parse_template(pattern)
        
        values = []
        for var_name, format_spec in variables:
            if var_name == 'seq':
                # Get current sequence without incrementing
                config = self.config_loader.load_id_templates_config()
                counters = config.get('counters', {})
                seq = counters.get(pattern, 1)
                if format_spec:
                    try:
                        seq = int(seq)
                        values.append(f"{seq:{format_spec}}")
                    except (ValueError, TypeError):
                        values.append(str(seq))
                else:
                    values.append(str(seq))
            else:
                value = context.get(var_name, '')
                if format_spec:
                    try:
                        values.append(f"{value:{format_spec}}")
                    except (ValueError, TypeError):
                        values.append(str(value))
                else:
                    values.append(str(value))
        
        return format_string.format(*values)


# Global ID generator instance
id_generator = IDGenerator()