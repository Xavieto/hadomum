"""Constantes de l'intégration Domum."""

from datetime import timedelta

DOMAIN = "domum"
SCAN_INTERVAL = timedelta(seconds=60)
SERVICE_GENERATE_ALIAS = "generate_alias"
ATTR_CONFIG_ENTRY = "config_entry_id"
ATTR_DESTINATION = "destination"
ATTR_DOMAIN = "domain"

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
