# Synchronisation du catalogue MNG FUT

Le site lit `web/version.json`, puis `web/catalog.json` quand sa version change. Les portraits et fonds de carte utilisent des noms issus de leur contenu pour éviter les anciennes images en cache.

`Sync-Web-Catalog.py --source <dossier localfut21> --watch` publie les changements toutes les 30 secondes. Le lanceur local MNG FUT démarre ce processus en arrière-plan. Un verrou empêche les doublons. Sans `--watch`, une seule synchronisation est exécutée.

Le script requiert Python, Pillow et Git. Il utilise la connexion GitHub déjà enregistrée dans le gestionnaire Git de Windows. Aucun secret ne figure dans le site ou les fichiers publiés. Le script ne lit jamais les sauvegardes SQLite, les crédits ou les informations de club. Seuls les champs publics de la définition des joueurs sont exportés. Les raretés désactivées sont exclues.

Les images locales sont converties de DDS en PNG pour le navigateur. Le script conserve les portraits et fonds déjà hébergés grâce au manifeste d’images. Le dossier facultatif `web-card-art/rarity22.png` contient le fond Rulebreakers personnalisé.

Le statut est enregistré dans `%LOCALAPPDATA%/MNG21/web-catalog/status.json`. En cas d’échec, la dernière version en ligne reste disponible et le processus réessaie. Quand le PC est éteint, le site continue d’afficher la dernière version publiée.
