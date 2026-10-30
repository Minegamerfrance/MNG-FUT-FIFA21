# Hébergement de test FIFA 21

## Clubs personnels avec le compte MNG

Le lanceur 1.3.27 réutilise l'inscription et la connexion MNG existantes.
Le connecteur vérifie l'empreinte TLS du VPS avant d'envoyer le jeton de session.
La passerelle `account_gateway.py` valide ce jeton auprès de l'API MNG fixe
et refuse toute identité différente de celle retournée par l'API.
Aucun mot de passe MNG ni jeton n'est stocké dans les données du VPS.

Chaque compte ouvre son propre processus FUT, ses réglages et sa base SQLite
dans le volume `personal-clubs`. Les anciens clubs locaux et le club commun
du test Tailscale ne sont pas migrés automatiquement.
L'inscription, les joueurs et la progression sont indépendants entre comptes.
Le catalogue de joueurs reste commun et est distribué avec le moteur.

Déploiement : `docker compose -p mng21-accounts -f accounts.compose.yaml up -d --build`.
Seule la passerelle TLS écoute sur le port public TCP 51443 ; les ports des
clubs sont limités aux adresses de boucle locale du conteneur. Tailscale n'est
pas nécessaire à cette connexion. Le service `mng-fut21-accounts.service`
assure le démarrage après Docker. Les clés TLS restent dans le volume privé.

Capacité initiale : 4 clubs actifs simultanément, avec remplacement du club
inactif le plus ancien lorsque nécessaire. Les bases sont conservées.
Cette configuration n'est pas une validation pour 50 joueurs simultanés.
Le marché de transferts est partagé entre les comptes : seules les cartes
effectivement proposées par les joueurs apparaissent. Il n'y a pas de stock
automatique. Achats immédiats, enchères, remboursements des joueurs surenchéris,
expiration, remise en vente et listes de suivi sont persistants. La taxe de vente
est de 5 %. Les cartes non échangeables, en prêt ou utilisées dans une équipe
ne peuvent pas être mises en vente.

La passerelle définit `LOCALFUT_SHARED_MARKET_ROOT` pour chaque moteur. Le fichier
`/state/accounts/transfermarket.sqlite3` contient les annonces, cartes en dépôt,
enchères réservées et reçus. Il doit être sauvegardé avec `accounts.sqlite3` et
les bases des clubs, jamais publié. Les transactions entre clubs utilisent le
mode de journal SQLite DELETE et la synchronisation FULL pour que cartes et
crédits soient validés ensemble. Les annonces expirées sont réglées toutes les
deux secondes, même lorsque les joueurs sont hors ligne.

Tests : `python hosting/test_shared_market.py` et
`python hosting/test_account_gateway.py`. Les rencontres 1 contre 1 restent à développer.

Tests : `python hosting/test_account_gateway.py` vérifie deux vrais moteurs
isolés avec des identités de test, le refus des mauvaises sessions, l'empreinte
TLS, les canaux HTTP/UDP et la persistance après redémarrage. Le connecteur a
aussi été testé depuis Windows vers le VPS avec un compte MNG réel.
La version du lanceur doit encore être validée dans FIFA.

## Essai gratuit sur le PC de l'hôte

Tailscale doit être installé et connecté. `server/Start-TestHost.cmd` démarre
un moteur séparé sur l'adresse privée Tailscale du PC. Le club d'essai se trouve
dans `%LOCALAPPDATA%/MNG21/HostingTest21`, hors du club habituel. Le bouton
`server/Stop-TestHost.cmd` arrête uniquement ce moteur d'essai et conserve son club.

Sur le PC joueur : fermer le serveur FUT local, connecter Tailscale au réseau
autorisé, puis ouvrir `server/Launch-RemoteFUT.cmd` et saisir l'adresse privée du
PC serveur. Le lanceur habituel conserve ses correctifs Windows, son accès EA App
et son redirecteur local ; le relais transmet FUT/Blaze/SSF en TCP et QoS en UDP.
Le moteur FUT ne tourne que sur l'hôte. L'arrêt habituel du lanceur ferme le
connecteur, sans arrêter le serveur d'essai.

Cette première version possède UN club d'essai : ne pas y connecter deux joueurs
simultanément. La séparation des comptes et le marché partagé restent à faire.
Aucun réglage de box, pare-feu public ou publication Tailscale Funnel n'est ajouté.
Le PC hôte doit rester allumé. Un test effectué depuis ce même PC vérifie le
routage, mais ne prouve pas le passage par Internet depuis un autre réseau.

Tests de transport : `python hosting/test_remote_relay.py`.

## Hôte Linux

Déploiement Docker validé sur Ubuntu 26.04 : démarrage des services,
connexion depuis un PC Windows par Tailscale et persistance SQLite après
redémarrage du conteneur. L'entrée dans FUT sur cet hôte reste à valider en jeu.

## Premier essai privé

Depuis ce dossier : `docker compose up -d --build`.
Vérifier ensuite `docker compose ps` et `docker compose logs --tail=50`.
Arrêter avec `docker compose down`, sans l'option `-v`, pour conserver le club.

Le moteur utilise un club de test neuf dans le volume `club-test`. Les données,
réglages et images mises en cache restent dans ce volume après redémarrage.
La sauvegarde personnelle Windows n'est pas copiée. Les images du catalogue
sont récupérées à la demande depuis le dépôt existant, avec contrôle d'empreinte.

Les ports du moteur sont publiés uniquement sur la boucle locale de l'hôte.
Pour un VPS privé connecté à Tailscale, créer un fichier `.env` à côté de
`compose.yaml` avec `MNG21_BIND_ADDRESS=` suivi de son adresse IPv4 Tailscale.
Ne jamais utiliser son IP publique ni `0.0.0.0`. Le fichier `.env` est propre
à la machine et ne doit pas être ajouté au dépôt.
Le service `mng-fut21.service` attend cette adresse avant de démarrer Compose.
Ses chemins supposent une installation dans `/home/ubuntu/mng21-server`.
Installer le service dans `/etc/systemd/system`, puis l'activer avec systemctl.
Partager le VPS dans Tailscale avec chaque testeur autorisé : un partage du PC
de développement ne donne pas automatiquement accès au VPS.
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
sur un hébergeur distant, ni dans FIFA par Internet. La construction Docker est
validée sur le VPS ; la connexion en jeu doit encore être validée.
