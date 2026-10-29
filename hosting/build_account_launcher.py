"""Package the MNG launcher with a thin account client; never include personal data."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from build_test_client import FILES

REPO = Path(__file__).resolve().parents[1]


def build(executable, assets, output):
    files = {'MNG FUT.exe': Path(executable).read_bytes(),
             'FIFA21-Update.py': (REPO / 'launcher/FIFA21-Update.py').read_bytes()}
    with zipfile.ZipFile(assets) as old:
        for name in old.namelist():
            if name.startswith('assets/') and not name.endswith('/') and Path(name).suffix.lower() in ('.png', '.jpg', '.jpeg', '.ico'):
                if '..' in Path(name).parts:
                    raise ValueError('Unsafe asset path')
                files[name] = old.read(name)
    for name in (*FILES, 'account-server.json', 'runtime-source/account_client.py', 'runtime-source/account_transport.py'):
        files['fifa21-server/' + name] = (REPO / 'server' / name).read_bytes()
    contract = {'gameId': '21'}
    for key, name in [('server', 'server.py'), ('onboarding', 'onboarding.py')]:
        contract[key] = hashlib.sha256((REPO / 'server/runtime-source/localfut21' / name).read_bytes()).hexdigest()
    files['fifa21-server/remote-runtime.json'] = json.dumps(contract, indent=2).encode()
    files['LIRE-MOI.txt'] = ('MNG FUT 1.3.27 - Clubs FIFA 21 personnels sur le VPS\r\n'
        '1. Extraire le ZIP dans un dossier. Fermer les anciens connecteurs et FIFA avant le premier essai.\r\n'
        '2. Ouvrir MNG FUT.exe. Se connecter au compte MNG ou en creer un avec le bouton Compte.\r\n'
        '3. Choisir FIFA 21, son executable, puis Se connecter a FUT. Lancer FIFA normalement quand le lanceur est pret.\r\n'
        'Tailscale est inutile pour cette connexion. Python 3 est requis et le connecteur prepare son environnement au premier lancement.\r\n'
        'Chaque compte possede son club, ses credits, ses joueurs et sa progression sur le VPS.\r\n'
        'Le club commun du premier test et les anciens clubs locaux ne sont pas importes automatiquement.\r\n'
        'Les outils des autres FIFA restent disponibles dans le lanceur. Le 1 contre 1 reste a developper.\r\n'
        'Cette version doit encore etre validee dans FIFA. Ne jamais envoyer de mot de passe ou de fichier de session.\r\n').encode('utf-8')
    files['fichiers.sha256.json'] = json.dumps({name: hashlib.sha256(data).hexdigest() for name, data in files.items()}, indent=2).encode()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        assert not any('/localfut21/' in name or name.endswith(('.sqlite3', '.pem', '.key', '.log')) for name in archive.namelist())
    print('Account launcher ready; no club DB, session, password or private key included:', output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--executable', required=True)
    parser.add_argument('--assets', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    build(args.executable, args.assets, args.output)
