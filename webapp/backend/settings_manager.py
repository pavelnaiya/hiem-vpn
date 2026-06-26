import json
import os
from pydantic import BaseModel, Field
from backend.logger import log

HIEM_DIR = os.path.expanduser("~/.hiem")
SETTINGS_FILE = os.path.join(HIEM_DIR, "settings.json")

class Profile(BaseModel):
    name: str = "Default"
    routing_mode: str = "all"
    routing_domains: str = ""
    exit_node: str = "Any"

class Settings(BaseModel):
    version: int = 1
    frequency_seconds: int = 0
    rotation_jitter: bool = False
    kill_switch: bool = False
    start_on_launch: bool = False
    auto_connect: bool = False
    auto_wifi: bool = False
    active_profile: Profile = Field(default_factory=Profile)

class SettingsManager:
    def __init__(self):
        self.settings = self.load()

    def load(self) -> Settings:
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r") as f:
                    data = json.load(f)
                    
                    # Migration logic if version changes later
                    if data.get("version", 1) == 1:
                        pass 
                        
                    return Settings(**data)
            except Exception as e:
                log.error(f"Failed to load settings: {e}. Using defaults.")
        return Settings()

    def save(self):
        try:
            with open(SETTINGS_FILE, "w") as f:
                f.write(self.settings.model_dump_json(indent=4))
        except Exception as e:
            log.error(f"Failed to save settings: {e}")

    def update(self, new_settings: Settings):
        self.settings = new_settings
        self.save()

settings_manager = SettingsManager()
