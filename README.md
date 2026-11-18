# Domum pour Home Assistant

Intégration personnalisée qui relie Home Assistant à [Domum](https://git.roques.bzh/tools/domum),
l'outillage du homelab : état des sauvegardes, bastion SSH, alias mail, puis supervision,
mises à jour, planning (Domum 2.8.0) et contrôle parental, module Famille (Domum 2.26.0), snippets (Domum 2.28.0) et listes de blocage (Domum 2.30.0).

## Installation (HACS, dépôt personnalisé)

1. HACS → menu ⋮ → **Dépôts personnalisés** : adresse HTTPS de ce dépôt,
   `https://git.roques.bzh/ha/domum-integration`, catégorie **Intégration**.
2. Installer « Domum », puis redémarrer Home Assistant.
3. Dans Domum : **Paramètres → Home Assistant → Jetons d'intégration**, créer un jeton en
   choisissant ses portées (lecture ou écriture par domaine) et les éléments exposés
   (sauvegardes, alias, serveurs, snippets). Sa valeur n'est affichée qu'une fois.
4. Home Assistant → **Paramètres → Appareils et services → Ajouter une intégration → Domum** :
   adresse de Domum et jeton.

Le jeton n'ouvre que l'API d'intégration de Domum (`/api/integration`), jamais le reste de
l'outil ; chaque action est tracée dans l'audit de Domum. Un jeton révoqué déclenche une
demande de nouveau jeton dans Home Assistant.

## Entités

Les entités suivent les portées du jeton : sans écriture, pas de bouton ni d'interrupteur.

| Domaine | Entités |
|---|---|
| Sauvegarde | par sauvegarde : état (réussie, en échec, en retard, en cours…), dernière réussite, problème (binaire), bouton « lancer » |
| Bastion | sessions actives, bastion en marche (binaire), bouton « couper les sessions » |
| Mail Alias | par alias : interrupteur (écriture) ou état actif (lecture) |
| Supervision | par serveur : anomalie (binaire, avec la liste des systèmes de fichiers saturés sans alerte), charge, mémoire, disque le plus plein ; par système de fichiers : utilisation en % (seuil critique, alerte, saturation en attributs, Domum 2.8.1 ou plus) ; par contrôle HTTP : anomalie |
| Mises à jour | par serveur : faille critique corrigeable, faille haute corrigeable, redémarrage requis (binaires), paquets à mettre à jour ; boutons « mettre à jour » et « redémarrer » si Domum le permet depuis Home Assistant pour ce serveur |
| Multimédia | derniers ajouts de Jellyfin (nombre ; liste en attribut `items`, épisodes à purger en `purgeable`), bouton « purger » (écriture) — Domum 2.9.0 |
| Famille | par enfant, un appareil « Famille - <prénom> » : temps restant (inconnu sans budget) et temps utilisé en minutes, état (ouvert, fermé, en pause, puni, temps épuisé), connecté (binaire) ; interrupteurs (écriture) « Internet » (éteint = pause), « Punition » (durée et mode des options) et « Mode vacances » ; boutons « Ajouter 15 minutes », « Ajouter 30 minutes », « Ajouter 1 heure » — jeton avec la portée `family`, Domum 2.26.0 |
| Snippets | par snippet exposé : bouton « lancer » (écriture), qui exécute ses étapes sur ses cibles ; un snippet créé dans Domum apparaît à l'actualisation suivante, un snippet supprimé devient indisponible puis disparaît au rechargement de l'intégration — jeton avec la portée `snippets` et les snippets choisis dans « éléments exposés » ; seuls les snippets qui autorisent leur lancement depuis Home Assistant (case du snippet dans Domum) sont visibles, Domum 2.28.0 |
| Listes de blocage | capteur « adresses retenues » (réseaux, date de la dernière fusion et nombre d'erreurs en attributs, lecture) ; bouton « relever » (écriture, toutes les sources, hors refus 429 en cours) ; un interrupteur par application (Bastion, routeur UniFi, Reverse Proxy) — seules celles cochées « Home Assistant » dans Domum (Paramètres → Listes de blocage) apparaissent : deux accords, la portée `blocklists` en écriture du jeton et la case de l'application, Domum 2.30.0 |
| Reverse Proxy | un interrupteur par redirection et par flux (actif ou coupé) — seuls ceux cochés « Autoriser l'activation depuis Home Assistant » dans Domum apparaissent : deux accords, la portée `reverse_proxy` en écriture du jeton et la case de l'objet, Domum 2.30.0 |
| Planning | calendrier « Planning » : sauvegardes, mises à jour planifiées, tâches de l'ordonnanceur, plages de maintenance (chevauchements signalés) |

Chaque nom d'entité commence par son module (« Sauvegarde - Critique : lancer », « Supervision -
VPS : charge »…). Les identifiants (`entity_id`) des entités déjà créées ne changent pas ; seules
les nouvelles entités reçoivent un identifiant préfixé.

Les éléments ajoutés dans Domum (et exposés au jeton) apparaissent sans recharger
l'intégration ; un élément retiré devient indisponible.

Exemple : couper l'accès Internet d'un serveur exposé tant qu'une faille critique corrigeable
n'est pas corrigée (déclencheur sur `binary_sensor.domum_mises_a_jour_vps_faille_critique_corrigeable`), ou
lancer la mise à jour du serveur de développement quand l'alarme passe en « Arm Night ».

## Famille

Le jeton doit avoir la portée `family` (lecture : capteurs seuls ; écriture : interrupteurs,
boutons et services). Les entités ont pour identifiants `sensor.famille_<prénom>_remaining_time`,
`switch.famille_<prénom>_internet`, `switch.famille_<prénom>_punishment`, etc.

**Options** (Paramètres → Appareils et services → Domum → Configurer) : durée de la punition en
minutes (60 par défaut) et mode `profile` (profil de punition) ou `cut` (coupure d'Internet),
appliqués quand on allume l'interrupteur « Punition ». L'éteindre lève la punition.

Services (l'enfant se désigne par son prénom ou son identifiant) :

| Service | Champs |
|---|---|
| `domum.add_time` | `child`, `minutes` : temps en plus pour aujourd'hui |
| `domum.punish` | `child`, `minutes` et `mode` facultatifs (options par défaut) |
| `domum.lift_punishment` | `child` |
| `domum.family_event` | `event` : déclenche l'action associée à cet évènement dans Domum ; renvoie `persons` |

Automatisation : mode vacances piloté par un capteur binaire de vacances scolaires (ou un calendrier) :

```yaml
automation:
  - alias: "Vacances scolaires : mode vacances des enfants"
    triggers:
      - trigger: state
        entity_id: binary_sensor.vacances_scolaires   # ou calendar.vacances_scolaires
    actions:
      - action: "{{ 'switch.turn_on' if trigger.to_state.state == 'on' else 'switch.turn_off' }}"
        target:
          entity_id: switch.famille_<prénom>_vacation_mode
```

Automatisation : alarme en « Arm Night » -> Internet en pause pour les enfants (et reprise au
désarmement) :

```yaml
automation:
  - alias: "Alarme nuit : pause d'Internet des enfants"
    triggers:
      - trigger: state
        entity_id: alarm_control_panel.maison
        to: armed_night
    actions:
      - action: switch.turn_off      # « Internet » éteint = pause
        target:
          entity_id: switch.famille_<prénom>_internet
  - alias: "Alarme désarmée : reprise d'Internet"
    triggers:
      - trigger: state
        entity_id: alarm_control_panel.maison
        to: disarmed
    actions:
      - action: switch.turn_on
        target:
          entity_id: switch.famille_<prénom>_internet
```

Pour laisser Domum décider (déclencheurs réglés dans le module Famille), appeler plutôt
`domum.family_event` avec le nom de l'évènement.

## Service `domum.generate_alias`

Crée un alias aléatoire **actif** (commentaire « Généré via Home Assistant le <date heure> ») et
renvoie son adresse, utilisable dans une automatisation :

```yaml
action: domum.generate_alias
data:
  destination: moi@exemple.fr   # facultatif si Domum n'a qu'une destination
  domain: roques.bzh            # facultatif si Domum n'a qu'un domaine
response_variable: alias
# puis : "{{ alias.address }}"
```

## Développement

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements_test.txt
.venv/bin/ruff check custom_components tests && .venv/bin/ruff format --check custom_components tests
.venv/bin/pytest --cov          # couverture exigée : 100 %
```
