# Taskflow API

Portail interne pour centraliser les appels d'offres publics récupérés depuis e-marchespublics. Le projet expose une API REST (Django + DRF) ainsi qu'un tableau de bord HTML prêt à l'emploi.

## Prérequis

- Python 3.11+
- `pip` et `venv`
- Accès réseau aux pages e-marchespublics (ou bien un dump HTML local)

## Installation rapide

```bash
git clone <repo>
cd taskflow-api
python -m venv venv
venv\Scripts\activate  # PowerShell: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Créez un fichier `.env` si vous devez surcharger des paramètres Django (facultatif).

## Mise en base de données

```bash
cd taskflow-api
python manage.py migrate
```

## Récupération des appels d'offres

```bash
python manage.py fetch_tenders
```

- La commande télécharge la page e-marchespublics principale, parse les cartes et alimente la table `tenders_tender`.
- Utilisez `--from-file tmp_emarches.html` pour rejouer un dump HTML local pendant le développement.

## Lancer le serveur local

```bash
python manage.py runserver
```

Ensuite ouvrez `http://127.0.0.1:8000/` pour afficher le tableau de bord. Les filtres consomment l'API `/api/tenders/` et le bouton « Exporter JSON » renvoie les mêmes données brutes.

## API principale

| Endpoint | Description |
| --- | --- |
| `GET /api/tenders/` | Liste paginée des appels d'offres (filtres: `search`, `category`, `procedure`, `region`, `department`, `deadline_at__lte`). |
| `GET /api/tenders/filters/` | Métadonnées pour alimenter les listes déroulantes du front (catégories, procédures, zones, bornes de dates). |

## Tests

```bash
pytest
```

Les tests couvrent les anciennes API « tasks ». Ajoutez de nouveaux cas autour de `tenders` lorsque nécessaire.

## Déploiement rapide

1. Exécuter les migrations sur l'environnement cible.
2. Lancer `python manage.py fetch_tenders` via cron/Job pour garder les données à jour.
3. Exposer l'URL `/` (dashboard) et `/api/tenders/` via votre serveur HTTP habituel.