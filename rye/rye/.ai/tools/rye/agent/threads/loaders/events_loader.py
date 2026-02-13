__version__ = "1.0.0"

from pathlib import Path
from typing import Any, Dict, Optional

from .config_loader import ConfigLoader


class EventsLoader(ConfigLoader):
    def __init__(self):
        super().__init__("events.yaml")

    def get_event_config(self, project_path: Path, event_type: str) -> Optional[Dict]:
        config = self.load(project_path)
        return config.get("event_types", {}).get(event_type)

    def get_criticality(self, project_path: Path, event_type: str) -> str:
        event_config = self.get_event_config(project_path, event_type)
        return (
            event_config.get("criticality", "important")
            if event_config
            else "important"
        )

    def should_emit_on_error(self, project_path: Path, event_type: str) -> bool:
        event_config = self.get_event_config(project_path, event_type)
        return event_config.get("emit_on_error", False) if event_config else False


_events_loader: Optional[EventsLoader] = None


def get_events_loader() -> EventsLoader:
    global _events_loader
    if _events_loader is None:
        _events_loader = EventsLoader()
    return _events_loader


def load(project_path: Path) -> Dict[str, Any]:
    return get_events_loader().load(project_path)
