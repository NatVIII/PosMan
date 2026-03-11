"""
Configuration loader for Poster Management System.

This module handles loading and validating configuration from YAML files.
All configuration is stored in /config directory and loaded at runtime.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import portalocker

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration cannot be loaded or validated."""


class ConfigLoader:
    """Loads and manages configuration from YAML files."""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.environ.get('CONFIG_PATH', '/config')
        self.config_path = Path(config_path)
        self._system_config = None
        self._template_config = None
        self._price_tiers_config = None
        
    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """Load a YAML file with file locking."""
        if not file_path.exists():
            raise ConfigError(f"Config file not found: {file_path}")
            
        try:
            with portalocker.Lock(file_path, 'r', timeout=5) as f:
                return yaml.safe_load(f)
        except portalocker.LockException:
            raise ConfigError(f"Could not acquire lock on config file: {file_path}")
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {file_path}: {e}")
            
    def load_system_config(self) -> Dict[str, Any]:
        """Load system configuration from system.yaml."""
        if self._system_config is None:
            config_file = self.config_path / "system.yaml"
            self._system_config = self._load_yaml_file(config_file)
            
            # Set defaults if not present
            defaults = {
                "system": {
                    "name": "Poster Management System",
                    "data_path": "/data",
                    "ftp_export_path": "/data/ftp_export",
                    "backup_path": "/backups",
                    "backup_retention": 4,
                    "upload_limit_mb": 200,
                },
                "users": []
            }
            
            # Merge defaults
            if self._system_config is None:
                self._system_config = defaults
            else:
                for key, value in defaults.items():
                    if key not in self._system_config:
                        self._system_config[key] = value
                        
        return self._system_config
    
    def load_template_config(self) -> Dict[str, Any]:
        """Load template configuration from template.yaml."""
        if self._template_config is None:
            config_file = self.config_path / "template.yaml"
            self._template_config = self._load_yaml_file(config_file)
            
            # Set defaults if not present
            defaults = {
                "template": {
                    "global": {
                        "price": 12.00,
                        "seller": "Party For Socialism and Liberation",
                        "slogans": ["@pslvirginia", "Dare to struggle, dare to win"],
                        "logo": {
                            "path": "/config/assets/logo.png",
                            "width_ratio": 0.8,
                            "scaling": "fit"
                        },
                        "bug": {
                            "width_in": 2.0,
                            "top_frac": 0.1,
                            "page_margin_in": 0.5,
                            "dpi": 300,
                            "horizontal_orientation": "landscape"
                        }
                    },
                    "price_tiers": {
                        "standard": {
                            "name": "Standard",
                            "price": 12.00,
                            "default": True
                        },
                        "premium": {
                            "name": "Premium",
                            "price": 15.00
                        },
                        "sale": {
                            "name": "Sale",
                            "price": 8.00
                        }
                    }
                }
            }
            
            if self._template_config is None:
                self._template_config = defaults
            else:
                # Deep merge defaults
                import copy
                merged = copy.deepcopy(defaults)
                self._merge_dicts(merged, self._template_config)
                self._template_config = merged
                
        return self._template_config
    
    def load_price_tiers_config(self) -> Dict[str, Any]:
        """Load price tiers configuration from price_tiers.yaml."""
        if self._price_tiers_config is None:
            config_file = self.config_path / "price_tiers.yaml"
            if config_file.exists():
                self._price_tiers_config = self._load_yaml_file(config_file)
            else:
                # Use template config price tiers as fallback
                template_config = self.load_template_config()
                self._price_tiers_config = template_config.get("template", {}).get("price_tiers", {})
                
        return self._price_tiers_config
    
    def _merge_dicts(self, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """Recursively merge source dict into target dict."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_dicts(target[key], value)
            else:
                target[key] = value
    
    def _save_yaml_file(self, file_path: Path, data: Dict[str, Any]) -> None:
        """Save a YAML file with file locking."""
        try:
            with portalocker.Lock(file_path, 'w', timeout=5) as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, indent=2)
        except portalocker.LockException:
            raise ConfigError(f"Could not acquire lock on config file: {file_path}")
        except (OSError, yaml.YAMLError) as e:
            raise ConfigError(f"Failed to save config file {file_path}: {e}")
    
    def save_system_config(self, system_config: Dict[str, Any]) -> None:
        """Save system configuration to system.yaml."""
        config_file = self.config_path / "system.yaml"
        self._save_yaml_file(config_file, system_config)
        # Invalidate cached config
        self._system_config = system_config
    
    def update_user(self, username: str, updates: Dict[str, Any]) -> bool:
        """Update user attributes and save configuration."""
        system_config = self.load_system_config()
        users = system_config.get("users", [])
        
        for i, user in enumerate(users):
            if user.get("username") == username:
                # Update user dict
                users[i].update(updates)
                # Save back
                self.save_system_config(system_config)
                return True
        
        return False
    
    def update_user_password(self, username: str, password_hash: str) -> bool:
        """Update user password hash."""
        return self.update_user(username, {"password_hash": password_hash})
    
    def add_user(self, user_data: Dict[str, Any]) -> bool:
        """Add a new user to configuration."""
        system_config = self.load_system_config()
        users = system_config.get("users", [])
        
        # Check if username already exists
        username = user_data.get("username")
        if any(u.get("username") == username for u in users):
            return False
        
        # Add created_at if not present
        if "created_at" not in user_data:
            from datetime import datetime
            user_data["created_at"] = datetime.utcnow().isoformat() + "Z"
        
        users.append(user_data)
        self.save_system_config(system_config)
        return True
    
    def delete_user(self, username: str) -> bool:
        """Delete a user from configuration."""
        system_config = self.load_system_config()
        users = system_config.get("users", [])
        
        new_users = [u for u in users if u.get("username") != username]
        if len(new_users) == len(users):
            return False
        
        system_config["users"] = new_users
        self.save_system_config(system_config)
        return True
    
    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user configuration by username."""
        system_config = self.load_system_config()
        users = system_config.get("users", [])
        
        for user in users:
            if user.get("username") == username:
                return user
        return None
    
    def validate_user_password(self, username: str, password_hash: str) -> bool:
        """Validate user password hash."""
        user = self.get_user(username)
        if not user:
            return False
            
        return user.get("password_hash") == password_hash
    
    def reload_all(self) -> None:
        """Reload all configuration files."""
        self._system_config = None
        self._template_config = None
        self._price_tiers_config = None


# Global configuration loader instance
config_loader = ConfigLoader()