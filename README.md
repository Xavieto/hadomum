# Domum pour Home Assistant

Intégration personnalisée qui relie Home Assistant à [Domum](https://git.roques.bzh/tools/domum),
l'outillage du homelab : état des sauvegardes, bastion SSH, alias mail, puis supervision,
mises à jour et planning (Domum 2.8.0).

## Installation (HACS, dépôt personnalisé)

1. HACS → menu ⋮ → **Dépôts personnalisés** : adresse HTTPS de ce dépôt,
   `https://git.roques.bzh/ha/domum-integration`, catégorie **Intégration**.
2. Installer « Domum », puis redémarrer Home Assistant.
3. Dans Domum : **Paramètres → Home Assistant → Jetons d'intégration**, créer un jeton en
   choisissant ses portées (lecture ou écriture par domaine) et les éléments exposés
   (sauvegardes, alias, serveurs). Sa valeur n'est affichée qu'une fois.
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

Les éléments ajoutés dans Domum (et exposés au jeton) apparaissent sans recharger
l'intégration ; un élément retiré devient indisponible.

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
