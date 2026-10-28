# Hébergement de test FIFA 21

Préparation pour une machine Linux disposant de Docker Compose. Ce dossier
ne constitue pas un déploiement déjà effectué. Aucun hébergeur n'est créé et
aucun port Internet n'est ouvert automatiquement.

## Premier essai privé

Depuis ce dossier : `docker compose up -d --build`.
Vérifier ensuite `docker compose ps` et `docker compose logs --tail=50`.
Arrêter avec `docker compose down`, sans l'option `-v`, pour conserver le club.

Le moteur utilise un club de test neuf dans le volume `club-test`. Les données,
réglages et images mises en cache restent dans ce volume après redémarrage.
La sauvegarde personnelle Windows n'est pas copiée. Les images du catalogue
sont récupérées à la demande depuis le dépôt existant, avec contrôle d'empreinte.

Les ports du moteur sont publiés uniquement sur la boucle locale de l'hôte.
L'accès distant doit passer par une connexion privée authentifiée. Ne pas
remplacer ces adresses par `0.0.0.0` dans Compose : le moteur actuel n'est pas
un service public multi-compte. Un seul testeur doit utiliser ce premier club.
Les interfaces locales Windows et les correctifs du lanceur restent sur le PC
du joueur ; les exécutables Windows ne sont pas lancés dans le conteneur Linux.

Le routage du lanceur à travers cette connexion privée reste à intégrer et à
vérifier en jeu. Le transport doit tenir compte du QoS UDP ainsi que de FUT,
Blaze et SSF en TCP. Les matchs 1 contre 1 ne font pas partie de ce premier essai.

## Vérifications

`python hosting/smoke_test.py` depuis la racine du dépôt vérifie le vrai moteur
avec un club temporaire, puis son redémarrage et sa persistance. Le moteur local
du joueur n'est pas arrêté. Le test utilise une autre adresse de boucle locale.

Cette vérification ne prouve pas à elle seule le fonctionnement sous Linux,
sur un hébergeur distant, ni dans FIFA par Internet. La construction Docker et
la connexion en jeu devront être validées sur la machine choisie.
