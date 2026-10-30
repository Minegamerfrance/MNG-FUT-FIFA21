"""Request-scoped translations for the local FUT catalogue."""
from contextvars import ContextVar
import re
from urllib.parse import urlsplit, parse_qs

LANGUAGE = ContextVar("fut_ui_language", default="fr")
LANGUAGES = ("fr", "es", "de", "it", "pt")

# English keys retain the legacy catalogue and stable challenge identifiers.
WORDS = {
    "Foundations": ("Fondations", "Fundamentos", "Grundlagen", "Fondamentali", "Fundamentos"),
    "Hybrid": ("Hybrides", "Híbridos", "Hybride", "Ibridi", "Híbridos"),
    "Upgrades": ("Améliorations", "Mejoras", "Upgrades", "Aggiornamenti", "Melhorias"),
    "Players": ("Joueurs", "Jugadores", "Spieler", "Giocatori", "Jogadores"),
    "Let's Get Started": ("C'est parti", "Vamos a empezar", "Los geht's", "Cominciamo", "Vamos começar"),
    "League and Nation Basics": ("Bases championnats et pays", "Básicos de ligas y países", "Liga- und Nationengrundlagen", "Basi campionati e nazioni", "Básicos de ligas e nações"),
    "Let's Keep Going": ("Continuons", "Sigamos", "Weiter geht's", "Continuiamo", "Vamos continuar"),
    "Advanced": ("Avancé", "Avanzado", "Fortgeschritten", "Avanzato", "Avançado"),
    "Hybrid Nations": ("Hybrides pays", "Híbridos de países", "Nationen-Hybride", "Nazionalità ibride", "Híbridos de nações"),
    "Hybrid Leagues": ("Hybrides championnats", "Híbridos de ligas", "Liga-Hybride", "Campionati ibridi", "Híbridos de ligas"),
    "League and Nation Hybrid": ("Hybrides championnats et pays", "Híbridos de ligas y países", "Liga- und Nationen-Hybride", "Campionati e nazioni ibridi", "Híbridos de ligas e nações"),
    "First Exchange": ("Premier échange", "Primer intercambio", "Erster Tausch", "Primo scambio", "Primeira troca"),
    "The Second Step": ("Deuxième étape", "El segundo paso", "Der zweite Schritt", "Il secondo passo", "O segundo passo"),
    "The Third Step": ("Troisième étape", "El tercer paso", "Der dritte Schritt", "Il terzo passo", "O terceiro passo"),
    "One League Attack": ("Attaque d'un championnat", "Ataque de una liga", "Angriff aus einer Liga", "Attacco di un campionato", "Ataque de uma liga"),
    "One Nation Midfield": ("Milieu d'un pays", "Mediocampo de un país", "Mittelfeld einer Nation", "Centrocampo di una nazione", "Meio-campo de uma nação"),
    "Multi League & Nation": ("Plusieurs championnats et pays", "Varias ligas y países", "Mehrere Ligen und Nationen", "Più campionati e nazioni", "Várias ligas e nações"),
    "Brick Slots": ("Emplacements verrouillés", "Posiciones bloqueadas", "Gesperrte Positionen", "Slot bloccati", "Posições bloqueadas"),
    "The Correct Position": ("Au bon poste", "La posición correcta", "Die richtige Position", "La posizione giusta", "A posição correta"),
    "Perfect Links": ("Liens parfaits", "Enlaces perfectos", "Perfekte Verbindungen", "Intese perfette", "Ligações perfeitas"),
    "Loyal Lads": ("Joueurs fidèles", "Jugadores leales", "Treue Spieler", "Giocatori fedeli", "Jogadores leais"),
    "The Final Four": ("Les quatre derniers", "Los cuatro finalistas", "Die letzten Vier", "Gli ultimi quattro", "Os quatro finalistas"),
    "Six of the Best": ("Six des meilleurs", "Seis de los mejores", "Sechs der Besten", "Sei dei migliori", "Seis dos melhores"),
    "Elite Eight": ("Les huit d'élite", "Ocho de élite", "Die Elite-Acht", "Gli otto migliori", "Oito de elite"),
    "Around the World": ("Tour du monde", "La vuelta al mundo", "Rund um die Welt", "Giro del mondo", "Volta ao mundo"),
    "Give Me Five": ("Donnez-m'en cinq", "Dame cinco", "Gib mir fünf", "Dammi il cinque", "Dá-me cinco"),
    "Seven-League Boots": ("Bottes de sept ligues", "Siete ligas", "Sieben Ligen", "Sette campionati", "Sete ligas"),
    "The Whole Nine Yards": ("Le grand neuf", "Nueve ligas", "Neun Ligen", "Nove campionati", "Nove ligas"),
    "First XI": ("Onze de départ", "Once inicial", "Startelf", "Undici titolari", "Onze inicial"),
    "The Challenger": ("Le challenger", "El aspirante", "Der Herausforderer", "Lo sfidante", "O desafiante"),
    "Fiendish": ("Diabolique", "Diabólico", "Teuflisch", "Diabolico", "Diabólico"),
    "Puzzle Master": ("Maître des énigmes", "Maestro de puzles", "Rätselmeister", "Maestro degli enigmi", "Mestre dos enigmas"),
    "Gold Rush": ("Ruée vers l'or", "Fiebre del oro", "Goldrausch", "Corsa all'oro", "Corrida ao ouro"),
    "Rising Standard": ("Niveau supérieur", "Sube el nivel", "Steigender Standard", "Alza il livello", "Subir o nível"),
    "Marquee Squad": ("Équipe de prestige", "Plantilla destacada", "Top-Mannschaft", "Rosa di prestigio", "Elenco de destaque"),
    "Elite Standard": ("Niveau élite", "Nivel de élite", "Elite-Standard", "Livello élite", "Nível de elite"),
    "Bronze Pack": ("Pack Bronze", "Sobre Bronce", "Bronze-Pack", "Pacchetto Bronzo", "Pacote Bronze"),
    "Silver Pack": ("Pack Argent", "Sobre Plata", "Silber-Pack", "Pacchetto Argento", "Pacote Prata"),
    "Gold Pack": ("Pack Or", "Sobre Oro", "Gold-Pack", "Pacchetto Oro", "Pacote Ouro"),
    "Premium Gold Pack": ("Pack Or premium", "Sobre Oro premium", "Premium-Gold-Pack", "Pacchetto Oro premium", "Pacote Ouro premium"),
    "Gold Players Pack": ("Pack joueurs Or", "Sobre de jugadores Oro", "Goldspieler-Pack", "Pacchetto giocatori Oro", "Pacote de jogadores Ouro"),
    "Premium Gold Players Pack": ("Pack joueurs Or premium", "Sobre de jugadores Oro premium", "Premium-Goldspieler-Pack", "Pacchetto giocatori Oro premium", "Pacote de jogadores Ouro premium"),
    "Prime Gold Players Pack": ("Pack joueurs Or prime", "Sobre de jugadores Oro únicos", "Prime-Goldspieler-Pack", "Pacchetto giocatori Oro prime", "Pacote de jogadores Ouro prime"),
    "Mega Pack": ("Méga pack", "Megasobre", "Mega-Pack", "Mega pacchetto", "Megapacote"),
    "Rare Mega Pack": ("Méga pack rare", "Megasobre único", "Seltenes Mega-Pack", "Mega pacchetto raro", "Megapacote raro"),
    "Rare Players Pack": ("Pack joueurs rares", "Sobre de jugadores únicos", "Seltene-Spieler-Pack", "Pacchetto giocatori rari", "Pacote de jogadores raros"),
    "Rare Mixed Players Pack": ("Pack joueurs mélangés rares", "Sobre de jugadores mixtos únicos", "Seltene-gemischte-Spieler-Pack", "Pacchetto giocatori misti rari", "Pacote de jogadores mistos raros"),
    "Rare Gold Pack": ("Pack Or rare", "Sobre Oro único", "Seltenes Gold-Pack", "Pacchetto Oro raro", "Pacote Ouro raro"),
    "Prime Electrum Players Pack": ("Pack joueurs Électrum prime", "Sobre de jugadores Electro únicos", "Prime-Electrum-Spieler-Pack", "Pacchetto giocatori Electrum prime", "Pacote de jogadores Electrum prime"),
    "Submit an 11-player squad.": ("Échangez une équipe de 11 joueurs.", "Entrega una plantilla de 11 jugadores.", "Tausche ein Team aus 11 Spielern ein.", "Scambia una rosa di 11 giocatori.", "Troca um elenco de 11 jogadores."),
}

TEMPLATES = {
    "Squad {n}": ("Équipe {n}", "Plantilla {n}", "Team {n}", "Rosa {n}", "Elenco {n}"),
    "{n}+ Player Pick": ("Choix joueur {n}+", "Elección de jugador {n}+", "{n}+-Spielerwahl", "Scelta giocatore {n}+", "Escolha de jogador {n}+"),
    "{n}+ Upgrade": ("Amélioration {n}+", "Mejora {n}+", "{n}+-Upgrade", "Aggiornamento {n}+", "Melhoria {n}+"),
    "Min Squad Rating: {n}": ("Note d'équipe : min. {n}", "Valoración de plantilla: mín. {n}", "Team-Gesamtwertung: mind. {n}", "Valutazione rosa: min. {n}", "Classificação do elenco: mín. {n}"),
    "Min Squad Chemistry: {n}": ("Collectif d'équipe : min. {n}", "Química de plantilla: mín. {n}", "Teamchemie: mind. {n}", "Intesa rosa: min. {n}", "Química do elenco: mín. {n}"),
    "Rare players: Min {n}": ("Joueurs rares : min. {n}", "Jugadores únicos: mín. {n}", "Seltene Spieler: mind. {n}", "Giocatori rari: min. {n}", "Jogadores raros: mín. {n}"),
    "Team of the Week players: Min {n}": ("Joueurs Équipe de la semaine : min. {n}", "Jugadores del equipo de la semana: mín. {n}", "Team-der-Woche-Spieler: mind. {n}", "Giocatori squadra della settimana: min. {n}", "Jogadores da equipa da semana: mín. {n}"),
    "Nationalities in Squad: Exactly {n}": ("Pays dans l'équipe : exactement {n}", "Países en la plantilla: exactamente {n}", "Nationen im Team: genau {n}", "Nazionalità in rosa: esattamente {n}", "Nações no elenco: exatamente {n}"),
    "Nationalities in Squad: Min {n}": ("Pays dans l'équipe : min. {n}", "Países en la plantilla: mín. {n}", "Nationen im Team: mind. {n}", "Nazionalità in rosa: min. {n}", "Nações no elenco: mín. {n}"),
    "Leagues in Squad: Exactly {n}": ("Championnats dans l'équipe : exactement {n}", "Ligas en la plantilla: exactamente {n}", "Ligen im Team: genau {n}", "Campionati in rosa: esattamente {n}", "Ligas no elenco: exatamente {n}"),
    "Leagues in Squad: Min {n}": ("Championnats dans l'équipe : min. {n}", "Ligas en la plantilla: mín. {n}", "Ligen im Team: mind. {n}", "Campionati in rosa: min. {n}", "Ligas no elenco: mín. {n}"),
    "Max players from same Nation: {n}": ("Joueurs du même pays : max. {n}", "Jugadores del mismo país: máx. {n}", "Spieler derselben Nation: max. {n}", "Giocatori della stessa nazione: max. {n}", "Jogadores da mesma nação: máx. {n}"),
    "Max players from same League: {n}": ("Joueurs du même championnat : max. {n}", "Jugadores de la misma liga: máx. {n}", "Spieler derselben Liga: max. {n}", "Giocatori dello stesso campionato: max. {n}", "Jogadores da mesma liga: máx. {n}"),
    "Max players from same Club: {n}": ("Joueurs du même club : max. {n}", "Jugadores del mismo club: máx. {n}", "Spieler desselben Vereins: max. {n}", "Giocatori dello stesso club: max. {n}", "Jogadores do mesmo clube: máx. {n}"),
    "Player Age: Max {n}": ("Âge des joueurs : max. {n}", "Edad de jugadores: máx. {n}", "Spieleralter: max. {n}", "Età giocatori: max. {n}", "Idade dos jogadores: máx. {n}"),
    "Number of players in the Squad: Exactly {n}": ("Nombre de joueurs : exactement {n}", "Número de jugadores: exactamente {n}", "Anzahl Spieler: genau {n}", "Numero di giocatori: esattamente {n}", "Número de jogadores: exatamente {n}"),
}
WORDS.update({
    "A bronze pack containing 12 items with 1 guaranteed rare and a chance of a Manager.": ("12 éléments bronze, dont 1 rare garanti, avec une chance d'obtenir un entraîneur.", "12 artículos Bronce, 1 único garantizado y posibilidad de entrenador.", "12 Bronze-Objekte, 1 seltenes garantiert und eine Trainerchance.", "12 oggetti Bronzo, 1 raro garantito e possibilità di un allenatore.", "12 itens Bronze, 1 raro garantido e possibilidade de treinador."),
    "A silver pack containing 12 items with 1 guaranteed rare and a chance of a Manager.": ("12 éléments argent, dont 1 rare garanti, avec une chance d'obtenir un entraîneur.", "12 artículos Plata, 1 único garantizado y posibilidad de entrenador.", "12 Silber-Objekte, 1 seltenes garantiert und eine Trainerchance.", "12 oggetti Argento, 1 raro garantito e possibilità di un allenatore.", "12 itens Prata, 1 raro garantido e possibilidade de treinador."),
    "A gold pack containing 12 items with 3 guaranteed rares and a chance of a Manager.": ("12 éléments or, dont 3 rares garantis, avec une chance d'obtenir un entraîneur.", "12 artículos Oro, 3 únicos garantizados y posibilidad de entrenador.", "12 Gold-Objekte, 3 seltene garantiert und eine Trainerchance.", "12 oggetti Oro, 3 rari garantiti e possibilità di un allenatore.", "12 itens Ouro, 3 raros garantidos e possibilidade de treinador."),
    "Electrum Players Pack": ("Pack joueurs Électrum", "Sobre de jugadores Electro", "Electrum-Spieler-Pack", "Pacchetto giocatori Electrum", "Pacote de jogadores Electrum"),
    "Prime Mixed Players Pack": ("Pack joueurs mélangés prime", "Sobre de jugadores mixtos prime", "Prime-gemischte-Spieler-Pack", "Pacchetto giocatori misti prime", "Pacote de jogadores mistos prime"),
    "Premium Silver Players Pack": ("Pack joueurs Argent premium", "Sobre de jugadores Plata premium", "Premium-Silberspieler-Pack", "Pacchetto giocatori Argento premium", "Pacote de jogadores Prata premium"),
    "Jumbo Rare Players Pack": ("Pack jumbo joueurs rares", "Sobre jumbo de jugadores únicos", "Jumbo-Seltene-Spieler-Pack", "Pacchetto maxi giocatori rari", "Pacote jumbo de jogadores raros"),
    "Ultimate Pack": ("Pack ultime", "Sobre definitivo", "Ultimatives Pack", "Pacchetto Ultimate", "Pacote Ultimate"),
    "Classic Icon 90+ Pack": ("Pack Icône classique 90+", "Sobre Icono clásico 90+", "Klassische-Icon-Pack 90+", "Pacchetto Icona classica 90+", "Pacote Ícone clássico 90+"),
    "Gold 82+ x10 Pack": ("Pack Or 82+ x10", "Sobre Oro 82+ x10", "Gold-Pack 82+ x10", "Pacchetto Oro 82+ x10", "Pacote Ouro 82+ x10"),
    "One classic Icon rated 90 or higher.": ("Une Icône classique notée 90 ou plus.", "Un Icono clásico de valoración 90 o superior.", "Ein klassischer Icon mit Wertung 90 oder höher.", "Un'Icona classica con valutazione 90 o superiore.", "Um Ícone clássico de classificação 90 ou superior."),
    "10 ordinary Gold players rated 82 or higher.": ("10 joueurs Or classiques notés 82 ou plus.", "10 jugadores Oro clásicos de valoración 82 o superior.", "10 normale Goldspieler mit Wertung 82 oder höher.", "10 giocatori Oro classici con valutazione 82 o superiore.", "10 jogadores Ouro clássicos de classificação 82 ou superior."),
    "Summer 2020 OTW Pack": ("Pack OTW été 2020", "Sobre OTW verano 2020", "OTW-Pack Sommer 2020", "Pacchetto OTW estate 2020", "Pacote OTW verão 2020"),
    "One OTW from the summer 2020 transfers.": ("Une carte OTW du mercato d'été 2020.", "Un OTW de los fichajes de verano de 2020.", "Ein OTW der Sommertransfers 2020.", "Un OTW dei trasferimenti estivi 2020.", "Um OTW das transferências do verão de 2020."),
    "Ordinary Gold players.": ("Joueurs Or classiques.", "Jugadores Oro clásicos.", "Normale Goldspieler.", "Giocatori Oro classici.", "Jogadores Ouro clássicos."),
    "Season Reward": ("Récompense de saison", "Recompensa de temporada", "Saisonbelohnung", "Premio stagionale", "Recompensa de temporada"),
    "Objective Player": ("Joueur d'objectif", "Jugador de objetivo", "Aufgabenspieler", "Giocatore obiettivo", "Jogador de objetivo"),
    "Premier League POTM": ("Joueur du mois Premier League", "Jugador del mes Premier League", "Premier-League-Spieler des Monats", "Giocatore del mese Premier League", "Jogador do mês Premier League"),
    "Bundesliga POTM": ("Joueur du mois Bundesliga", "Jugador del mes Bundesliga", "Bundesliga-Spieler des Monats", "Giocatore del mese Bundesliga", "Jogador do mês Bundesliga"),
    "Ligue 1 POTM": ("Joueur du mois Ligue 1", "Jugador del mes Ligue 1", "Ligue-1-Spieler des Monats", "Giocatore del mese Ligue 1", "Jogador do mês Ligue 1"),
    "La Liga POTM": ("Joueur du mois LaLiga", "Jugador del mes LaLiga", "LaLiga-Spieler des Monats", "Giocatore del mese LaLiga", "Jogador do mês LaLiga"),
    "Player Moments": ("Moments joueur", "Momentos de jugador", "Spielermomente", "Momenti giocatore", "Momentos do jogador"),
    "Team of the Week": ("Équipe de la semaine", "Equipo de la semana", "Team der Woche", "Squadra della settimana", "Equipa da semana"),
    "Record Breaker": ("Briseur de records", "Romperrécords", "Rekordbrecher", "Record Breaker", "Quebra-recordes"),
})
for quality, translations in {"Bronze":("bronze","bronce","Bronze","bronzo","bronze"), "Silver":("argent","plata","Silber","argento","prata"), "Gold":("or","oro","Gold","oro","ouro")}.items():
    WORDS[f"Player Quality: {quality} only"] = tuple(("Qualité : {q} uniquement", "Calidad: solo {q}", "Qualität: nur {q}", "Qualità: solo {q}", "Qualidade: apenas {q}")[i].format(q=q) for i,q in enumerate(translations))

MESSAGES = {
    "official_otw_sbc_description": ("DCE OTW officiel FIFA 21 sorti le {date}.", "DCP OTW oficial de FIFA 21 publicado el {date}.", "Offizielle FIFA-21-OTW-SBC vom {date}.", "SCR OTW ufficiale FIFA 21 del {date}.", "DME OTW oficial de FIFA 21 de {date}."),
    "league_requirement": ("Joueurs de {name} : min. {n}", "Jugadores de {name}: mín. {n}", "Spieler aus {name}: mind. {n}", "Giocatori di {name}: min. {n}", "Jogadores de {name}: mín. {n}"),
    "nation_requirement": ("Joueurs de {name} : min. {n}", "Jugadores de {name}: mín. {n}", "Spieler aus {name}: mind. {n}", "Giocatori di {name}: min. {n}", "Jogadores de {name}: mín. {n}"),
    "set_description": ("Terminez {name} ({n} défis).", "Completa {name} ({n} desafíos).", "Schließe {name} ab ({n} Aufgaben).", "Completa {name} ({n} sfide).", "Conclui {name} ({n} desafios)."),
    "player_sbc_description": ("Récompense DCE sortie le {date}. Défi MNG adapté : note, collectif et rareté.", "Recompensa DCP del {date}. Desafío MNG adaptado: valoración, química y rareza.", "SBC-Belohnung vom {date}. Angepasste MNG-Aufgabe: Wertung, Chemie und Seltenheit.", "Premio SCR del {date}. Sfida MNG adattata: valutazione, intesa e rarità.", "Recompensa DME de {date}. Desafio MNG adaptado: classificação, química e raridade."),
    "objective_sbc_description": ("Carte d'objectif sortie le {date}. Défi MNG pour l'obtenir sur le serveur local.", "Carta de objetivo del {date}. Desafío MNG para conseguirla en el servidor local.", "Aufgabenkarte vom {date}. MNG-SBC zum Freischalten auf dem lokalen Server.", "Carta obiettivo del {date}. Sfida MNG per ottenerla sul server locale.", "Carta de objetivo de {date}. Desafio MNG para obtê-la no servidor local."),
}
EN_MESSAGES = {"set_description":"Complete {name} ({n} challenges).", "player_sbc_description":"SBC reward released {date}. Adapted MNG challenge: rating, chemistry and rarity.", "objective_sbc_description":"Objective card released {date}. MNG challenge to obtain it on the local server."}
EN_MESSAGES.update(official_otw_sbc_description="Official FIFA 21 OTW SBC released {date}.", league_requirement="Players from {name}: min. {n}", nation_requirement="Players from {name}: min. {n}")
WORDS.update({"TOTW 1 Pack":("Pack TOTW 1","Sobre TOTW 1","TOTW-1-Pack","Pacchetto TOTW 1","Pacote TOTW 1"), "One player from FIFA 21 Team of the Week 1.":("Un joueur de la première Équipe de la semaine de FIFA 21.","Un jugador del primer equipo de la semana de FIFA 21.","Ein Spieler aus FIFA 21 Team der Woche 1.","Un giocatore della prima squadra della settimana di FIFA 21.","Um jogador da primeira equipa da semana de FIFA 21.")})
MATCHERS = [(re.compile(re.escape(key).replace(r"\{n\}", r"(?P<n>\d+)")), values) for key,values in TEMPLATES.items()]


def language_for_request(path, headers, default="fr"):
    query = parse_qs(urlsplit(path).query)
    lower = {str(k).lower():str(v) for k,v in headers.items()}
    value = next((query[k][0] for k in ("locale","language","lang") if query.get(k)), "")
    value = value or lower.get("x-ut-uilanguage", "") or lower.get("accept-language", "")
    if not value:
        match = re.search(r"storepackdescriptions\.(fr|es|de|it|pt)[_-]", path, re.I)
        value = match.group(1) if match else default
    value = value.lower().split(",",1)[0].split(";",1)[0].replace("_","-").split("-",1)[0]
    return value if value in (*LANGUAGES,"en") else "en"


def t(text, **values):
    text = str(text or "")
    lang = LANGUAGE.get()
    # Authored French strings and canonical English catalogue strings share
    # the same request-scoped translations, including the English locale.
    from ui_localization import translate
    translated = translate(text, lang)
    if translated is not None:
        return translated.format(**values) if values else translated
    if lang == "en":
        return EN_MESSAGES.get(text,text).format(**values) if values else EN_MESSAGES.get(text,text)
    index = LANGUAGES.index(lang) if lang in LANGUAGES else 0
    if text in MESSAGES:
        return MESSAGES[text][index].format(**values)
    if text in WORDS:
        return WORDS[text][index]
    if " — " in text:
        name,edition = text.rsplit(" — ",1)
        return name + " — " + t(edition)
    for pattern,translations in MATCHERS:
        match = pattern.fullmatch(text)
        if match:
            return translations[index].format(**match.groupdict())
    return text
