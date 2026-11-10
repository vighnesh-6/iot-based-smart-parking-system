"""Backend settings; never place runtime SQLite files inside a synced checkout."""

from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
DEVICES = {f"esp32_{i:02d}": tuple(f"P{n}" for n in range(4*i-3, 4*i+1)) for i in range(1, 4)}
TOPICS = {f"smartparking/{device}/telemetry": device for device in DEVICES}


def safe_database_path(value):
    path = Path(value).expanduser().resolve()
    forbidden = [ROOT]
    forbidden += [Path(v).resolve() for k, v in os.environ.items() if k.lower().startswith("onedrive") and v]
    if not Path(value).is_absolute() or any(path == root or root in path.parents for root in forbidden):
        raise ValueError("DATABASE_PATH must be absolute and outside the project and OneDrive")
    if any("onedrive" in part.lower() for part in path.parts):
        raise ValueError("DATABASE_PATH must be outside OneDrive")
    return path


@dataclass(frozen=True)
class Settings:
    database_path: Path
    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_client_id: str = "smartparking-backend"
    mqtt_username: str = ""
    mqtt_password: str = field(default="", repr=False)
    mqtt_enabled: bool = True
    stale_seconds: int = 30
    queue_size: int = 256
    database_timeout: float = 2.0

    def __post_init__(self):
        object.__setattr__(self, "database_path", safe_database_path(self.database_path))
        if not self.mqtt_host or not self.mqtt_client_id or self.mqtt_client_id.startswith("smartparking-esp32_"):
            raise ValueError("Backend requires its own nonempty MQTT identity and host")
        if not 1 <= self.mqtt_port <= 65535 or self.stale_seconds < 1 or self.queue_size < 1 or self.database_timeout <= 0:
            raise ValueError("Invalid backend timing, queue or port setting")

    @classmethod
    def from_env(cls):
        # Environment wins. Reading .env does not mutate process-wide variables.
        env = {**dotenv_values(ROOT / ".env"), **os.environ}
        local = env.get("LOCALAPPDATA")
        default = str(Path(local) / "SmartParking" / "parking.db") if local else ""
        enabled = str(env.get("MQTT_ENABLED", "true")).lower()
        if enabled not in {"true", "false"}:
            raise ValueError("MQTT_ENABLED must be true or false")
        return cls(database_path=Path(env.get("DATABASE_PATH") or default),
                   mqtt_host=env.get("MQTT_HOST") or "127.0.0.1",
                   mqtt_port=int(env.get("MQTT_PORT", 1883)),
                   mqtt_client_id=env.get("MQTT_CLIENT_ID") or "smartparking-backend",
                   mqtt_username=env.get("MQTT_USERNAME") or "",
                   mqtt_password=env.get("MQTT_PASSWORD") or "",
                   mqtt_enabled=enabled == "true", stale_seconds=int(env.get("STALE_SECONDS", 30)),
                   queue_size=int(env.get("INGEST_QUEUE_SIZE", 256)))
