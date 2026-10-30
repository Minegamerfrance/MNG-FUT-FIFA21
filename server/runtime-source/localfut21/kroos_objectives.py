"""Toni Kroos 75 -> Bayern 85 -> 90, with version-specific match receipts."""
import json
import mollet_objectives
from player_objectives import Campaign

GROUP = 7301
LEVERKUSEN, BAYERN, FINAL = 67291385, 84068601, 100845817
PACK = 521  # Two rare gold players, untradeable.
SBC = frozenset(f'MNG_KROOS_{i}' for i in range(1, 5))
ROWS = (
    ('Les débuts de Kroos', 1, PACK, 'Terminez les 4 équipes du SBC MNG FUT Kroos pour obtenir Toni Kroos MNG FUT 75.'),
    ("L’apprentissage", 48, PACK, 'Disputez 48 matchs avec Toni Kroos MNG FUT 75.'),
    ('Le sens du but', 10, PACK, 'Marquez 10 buts avec Toni Kroos MNG FUT 75.'),
    ("Le chef d’orchestre", 8, PACK, 'Réalisez 8 passes décisives avec Toni Kroos MNG FUT 75.'),
    ("L’ascension", 20, PACK, 'Remportez 20 matchs avec Toni Kroos MNG FUT 75 titulaire pour gagner sa version Bayern 85.'),
    ("L’ère bavaroise", 205, PACK, 'Disputez 205 matchs avec Toni Kroos Bayern 85.'),
    ('La précision du maestro', 24, PACK, 'Marquez 24 buts avec Toni Kroos Bayern 85.'),
    ("Le chef d’orchestre", 27, PACK, 'Réalisez 27 passes décisives avec Toni Kroos Bayern 85.'),
    ('La domination allemande', 144, PACK, 'Remportez 144 matchs avec Toni Kroos Bayern 85 titulaire.'),
)


class Kroos(Campaign):
    def __init__(self):
        super().__init__(GROUP, dict(player=FINAL, key='mng_kroos_career_v1',
            title="L'ascension du maestro Toni Kroos", leagueName='MNG FUT', priority=1,
            subTitle="Jeune prodige du Bayern Munich, révélé à Leverkusen, puis de retour en Bavière avant de devenir une légende du Real Madrid. Revivez l'ascension de Toni Kroos.",
            displayOrder=list(range(len(ROWS)))), ROWS, xp=0, group_xp=0)

    def progress(self, s):
        p = super().progress(s)
        # Existing SBC completion is recognized without requiring a second SBC.
        if SBC.issubset(set(s.STATE.get('sbc_completed', []) or [])):
            p['counts'][0] = 1
        return p

    def awards(self, s, index=None):
        if index is None or index == 4:
            return [s._scmp_award('player', FINAL if index is None else BAYERN)]
        reward = s._pack_award(PACK)
        reward['halId'] = reward['assetId']
        return [reward]

    def claim(self, s, index=None):
        if index is not None and index not in range(len(ROWS)):
            return 404, dict(reason='UNKNOWN_OBJECTIVE')
        with s.STATE.lock:
            p = self.progress(s)
            if p.get('claimed') if index is None else index in p.get('claimedObjectives', []):
                return 200, dict(alreadyClaimed=True, awards=[], awardsList=[], itemList=[], grantedItems=[])
            needed = range(len(ROWS)) if index is None else [index]
            if any(p['counts'][i] < ROWS[i][1] for i in needed):
                return 403, dict(reason='OBJECTIVES_INCOMPLETE', awards=[], itemList=[])
            player = FINAL if index is None else BAYERN if index == 4 else None
            items = []
            if player:
                identifier = max(int(s.STATE.get('next_item_id', 900000000000)) + 1,
                    int(s.STATE.conn.execute('SELECT COALESCE(MAX(id),0)+1 FROM items').fetchone()[0]))
                item = s.STATE.build_player_item(player, identifier, 'unassigned')
                item.update(untradeable=True, untradeableCount=1, objectiveReward=True)
                items.append(item)
            if index is None:
                p['claimed'] = True
            else:
                p['claimedObjectives'] = sorted(set(p.get('claimedObjectives', [])) | {index})
            # The reward and its receipt commit together, so retries cannot pay twice.
            with s.STATE.conn:
                if player:
                    s.STATE.conn.execute('INSERT INTO items(id,resource_id,pile,data) VALUES(?,?,?,?)',
                        (identifier, player, 'unassigned', json.dumps(item)))
                    mollet_objectives._put(s, 'next_item_id', identifier)
                else:
                    s.STATE.conn.execute('INSERT INTO unopened_packs(pack_id,data) VALUES(?,?)',
                        (PACK, json.dumps(dict(source='kroos_objective', objectiveId=GROUP*100+index+1,
                                               created=s.now_s(), untradeable=True))))
                mollet_objectives._put(s, self.key, p)
            native = [s._native_pack_item(item) for item in items]
            s.PENDING_USERSESSION_REFRESH.set()
            return 200, dict(alreadyClaimed=False, awards=self.awards(s, index), awardsList=self.awards(s, index),
                             itemList=native, grantedItems=native, xpAward=0)

    def start(self, s, payload, response):
        with s.STATE.lock:
            if self.progress(s).get('pending'):
                return
            super().start(s, payload, response)
            p = self.progress(s)
            context = p.get('pending')
            if not context:
                return
            # A concept, another version or an unowned card cannot count.
            owned = []
            seen = set()
            for card in context['players']:
                if card['id'] not in seen and s.STATE.conn.execute(
                        'SELECT 1 FROM items WHERE id=? AND resource_id=?',
                        (card['id'], card['resourceId'])).fetchone():
                    owned.append(card)
                    seen.add(card['id'])
            context['players'] = owned
            context['sbcUnlocked'] = p['counts'][0] >= 1
            context['bayernUnlocked'] = 4 in p.get('claimedObjectives', [])
            s.STATE.set(self.key, p)

    def finish(self, s, payload):
        with s.STATE.lock:
            p = self.progress(s)
            context = p.pop('pending', None)
            if not context:
                return
            reason = str(payload.get('endReason', '')).upper()
            if reason not in ('WIN', 'DRAW', 'LOSS'):
                s.STATE.set(self.key, p)
                return
            stats = {row['id']: row for row in payload.get('items', []) if
                     isinstance(row, dict) and type(row.get('id')) is int} if isinstance(payload.get('items'), list) else {}
            events = []
            for event in payload.get('events', []) if isinstance(payload.get('events'), list) else []:
                if not isinstance(event, dict) or not isinstance(event.get('attributes'), list):
                    continue
                fields = {a.get('key'): a.get('value') for a in event['attributes'] if isinstance(a, dict)}
                events.append(fields)
            changes = [0] * len(ROWS)
            for resource, offset, unlocked in ((LEVERKUSEN, 1, context.get('sbcUnlocked')),
                                               (BAYERN, 5, context.get('bayernUnlocked'))):
                if not unlocked:
                    continue
                cards = [c for c in context['players'] if c['resourceId'] == resource]
                played = started = goals = assists = 0
                for card in cards:
                    row = stats.get(card['id'])
                    # Asset-only events are ambiguous if multiple versions share the XI.
                    unique_asset = sum(c['assetId'] == card['assetId'] for c in context['players']) == 1
                    own_events = [e for e in events if str(e.get('player_id')) == str(resource) or
                                  unique_asset and str(e.get('player_id')) == str(card['assetId'])]
                    g = mollet_objectives._positive(row.get('goals')) if row is not None else sum(e.get('name') == 'goal' for e in own_events)
                    a = mollet_objectives._positive(row.get('assists')) if row is not None else sum(e.get('name') == 'assist' for e in own_events)
                    starter = card['index'] < 11
                    participated = starter or g > 0 or a > 0 or row and any(
                        mollet_objectives._positive(row.get(k)) > 0 for k in ('minutesPlayed', 'gamesPlayed', 'matchesPlayed'))
                    played |= bool(participated)
                    started |= starter
                    goals += g
                    assists += a
                changes[offset:offset+4] = [int(played), goals, assists, int(reason == 'WIN' and started)]
            p['counts'] = [min(row[1], p['counts'][i] + changes[i]) for i, row in enumerate(ROWS)]
            with s.STATE.conn:
                mollet_objectives._put(s, self.key+'_match_'+context['id'],
                    dict(id=context['id'], increments=changes, at=s.now_s()))
                mollet_objectives._put(s, self.key, p)
