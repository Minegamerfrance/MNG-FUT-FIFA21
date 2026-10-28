"""Build a thin friend-test client from an explicit allowlist, without a club DB."""
import argparse
import hashlib
import ipaddress
import json
from pathlib import Path
import zipfile

REPO = Path(__file__).resolve().parents[1]
FILES = (
    "Launch-LocalFUT.ps1", "Stop-LocalFUT.ps1", "User-Settings.ps1",
    "Launch-RemoteFUT.ps1", "Prepare-RemoteClient.ps1", "Check-RemoteClient.ps1",
    "FIFA21-LocalAuthBridge.cs", "MNG21-LocalAuthBridge.exe",
    "FIFA21-RarityNames.cs", "MNG21-RarityNames.exe",
    "runtime-source/remote_relay.py", "runtime-source/redirector_tls.py",
    "runtime-source/PATCH_RUNNING_FIFA21_TRUST.py",
    "runtime-source/generate_local_cert.py", "runtime-source/gos2015-original-modulus.bin",
)
COMMANDS = {"Preparer.cmd": "Prepare-RemoteClient.ps1",
            "Verifier-connexion.cmd": "Check-RemoteClient.ps1",
            "Connexion-serveur.cmd": "Launch-RemoteFUT.ps1",
            "Arreter-connexion.cmd": "Stop-LocalFUT.ps1"}


def content(host):
    address = ipaddress.ip_address(host)
    if address not in ipaddress.ip_network("100.64.0.0/10"):
        raise ValueError("Private Tailscale address required")
    files = {name: (REPO / "server" / name).read_bytes() for name in FILES}
    for name, script in COMMANDS.items():
        files[name] = ('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0' + script + '"\r\npause\r\n').encode("ascii")
    files["remote-test.json"] = json.dumps({"gameId": "21", "host": host}, indent=2).encode()
    contract = {"gameId": "21"}
    for key, name in (("server", "server.py"), ("onboarding", "onboarding.py")):
        contract[key] = hashlib.sha256((REPO / "server/runtime-source/localfut21" / name).read_bytes()).hexdigest()
    files["remote-runtime.json"] = json.dumps(contract, indent=2).encode()
    files["LIRE-MOI.txt"] = ("""MNG FUT FIFA 21 - CONNEXION DE TEST PRIVEE

1. Extrais tout le ZIP dans un nouveau dossier. Ne lance rien depuis le ZIP.
2. FIFA 21 et Python doivent deja etre installes. Ouvre Preparer.cmd une fois.
3. Installe et connecte Tailscale avec TON compte. L'hote doit autoriser ton acces
   a son PC de test. Ne demande pas ses identifiants et ne partage pas les tiens.
4. Ouvre Verifier-connexion.cmd. Le PC de l'hote doit rester allume.
5. Si le test repond OK, ouvre EA App puis Connexion-serveur.cmd. Si demande,
   selectionne FIFA21.exe. La validation Windows sert aux correctifs locaux
   habituels du lanceur. Lance ensuite FIFA avec ta methode habituelle.
6. Ouvre FUT. Tu dois retrouver le club d'essai MNG Test (nouveau club).
7. Pour finir, ouvre Arreter-connexion.cmd. Le club reste chez l'hote.

Ne lance pas un autre serveur FUT local en meme temps que ce connecteur.
Cette premiere version partage UN seul club de test : un seul testeur a la fois.
Le 1 contre 1 n'est pas encore integre. La connexion depuis un autre reseau
reste a valider en jeu. En cas d'erreur, envoie le texte de Verifier-connexion
et les journaux du dossier runtime, jamais des identifiants.

Ce dossier ne contient ni jeu FIFA, ni moteur FUT, ni base de joueurs,
ni sauvegarde personnelle, ni cle privee de l'hote. Les cles necessaires
au connecteur sont generees sur ton propre PC.
""").encode("utf-8")
    files["fichiers.sha256.json"] = json.dumps({name: hashlib.sha256(data).hexdigest() for name, data in files.items()}, indent=2).encode()
    return files


def build(host, output):
    files = content(host)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr("MNG-FUT-21-Connexion-test/" + name, data)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert not any(name.endswith((".pem", ".key", ".sqlite3", ".log")) or "/localfut21/" in name for name in archive.namelist())
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = build(args.host, args.output)
    print(result)
    print("Verified: no FUT engine, player database, saved club or host private key")
