"""Constantes de l'intégration Domum."""

from datetime import timedelta

DOMAIN = "domum"
SCAN_INTERVAL = timedelta(seconds=60)
SERVICE_GENERATE_ALIAS = "generate_alias"
ATTR_CONFIG_ENTRY = "config_entry_id"
ATTR_DESTINATION = "destination"
ATTR_DOMAIN = "domain"
ATTR_CHILD = "child"
ATTR_MINUTES = "minutes"
ATTR_MODE = "mode"
ATTR_EVENT = "event"
SERVICE_ADD_TIME = "add_time"
SERVICE_PUNISH = "punish"
SERVICE_LIFT_PUNISHMENT = "lift_punishment"
SERVICE_FAMILY_EVENT = "family_event"

# Options : punition appliquée par l'interrupteur « Punition ».
CONF_PUNISH_MINUTES = "punish_minutes"
CONF_PUNISH_MODE = "punish_mode"
DEFAULT_PUNISH_MINUTES = 60
PUNISH_MODES = ["profile", "cut"]
DEFAULT_PUNISH_MODE = "profile"

# États d'un enfant renvoyés par Domum (module Famille).
FAMILY_STATES = ["open", "closed", "paused", "punished", "exhausted"]

# États d'une sauvegarde renvoyés par Domum (capteur à valeurs énumérées).
BACKUP_STATES = [
    "success",
    "partial",
    "failed",
    "running",
    "late",
    "never",
    "cancelled",
    "interrupted",
    "pending",
]
