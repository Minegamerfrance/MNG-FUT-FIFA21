"""Versioned FUT catalogue restrictions and backed-up club migration."""
from __future__ import annotations

import copy
from contextlib import closing
import datetime
import json
import sqlite3
from pathlib import Path
from fut_i18n import t


def load_policy(root: Path) -> dict:
    path = root / "catalog-policy.json"
    if not path.exists():
        return {}
    policy = json.loads(path.read_text(encoding="utf-8"))
    allowed = policy.get("allowedRarities", [])
    if policy.get("enabled") and (not policy.get("version")
                                   or not {0, 1, 12}.issubset(allowed)
                                   or any(not isinstance(r, int) for r in allowed)
                                   or (set(allowed) != {0, 1, 12} and not policy.get("extraResourceIds"))):
        raise ValueError("Invalid summer 2020 catalogue policy")
    return policy


def constrain_packs(settings: dict, policy: dict) -> dict:
    if not policy.get("enabled"):
        return settings
    for pid, cfg in settings.get("packs", {}).items():
        allowed = set(cfg.get("allowed_rareflags", [0, 1, 12, 21])) & set(policy["allowedRarities"])
        if not allowed:
            cfg["enabled"] = False
        # Legacy 99/92+ promotional packs are no longer offered. Owned copies
        # can still be opened as ordinary gold packs, with no impossible pool.
        if str(pid) in {"5", "6"} or int(cfg.get("min_rating", 0)) > 94:
            cfg.update(enabled=False, name="Gold Pack", bio="Ordinary Gold players.",
                       min_rating=75, guaranteed_specials=0, special_chance=0.0,
                       allowed_rareflags=[0, 1], gold_weight=100,
                       silver_weight=0, bronze_weight=0)
        else:
            cfg["allowed_rareflags"] = sorted(allowed)
        cfg["special_weights"] = {"3": 100, "12": 100, "21": 100}
        if str(pid) in {"1", "2", "3"}:
            cfg.update(special_chance=0.0, guaranteed_specials=0,
                       allowed_rareflags=[0, 1])
        if str(pid) == "4":
            cfg.update(name="Gold 82+ x10 Pack", bio="10 ordinary Gold players rated 82 or higher.",
                       special_chance=0.0, guaranteed_specials=0,
                       allowed_rareflags=[0, 1])
        if str(pid) == "7":
            cfg.update(name="Base Icon Pack", min_rating=85,
                       bio="One Base Icon player.",
                       allowed_rareflags=[12])
        if 21 in policy["allowedRarities"] and str(pid) == "3":
            cfg.update(special_chance=0.05, allowed_rareflags=[0,1,12,21]+([3] if policy.get("totwNumbers")==[1] else []))
            cfg['special_weights']['12']=2
        if str(pid)=="3" and policy.get("rulebreakersActive") and 22 in policy["allowedRarities"]:
            cfg['allowed_rareflags']=sorted(set(cfg.get('allowed_rareflags',[]))|{22})
            cfg['special_weights']['22']=100
        cfg["name"] = t(cfg.get("name", "Gold Pack"))
        cfg["bio"] = t(cfg.get("bio", ""))
    if 21 in policy["allowedRarities"]:
        settings["packs"]["202010"] = {
            "enabled":True,"name":t("Summer 2020 OTW Pack"),"bio":t("One OTW from the summer 2020 transfers."),
            "price":50000,"size":1,"gold_weight":100,"silver_weight":0,"bronze_weight":0,
            "rare_slots":1,"guaranteed_specials":1,"special_chance":0.0,
            "manager_chance":0.0,"allowed_rareflags":[21],"special_weights":{"21":100},
            "allow_unweighted_specials":False,"store_group":"special"}
    if policy.get("totwNumbers") == [1]:
        settings["packs"]["202001"] = {
            "enabled":True,"name":t("TOTW 1 Pack"),"bio":t("One player from FIFA 21 Team of the Week 1."),
            "price":25000,"size":1,"gold_weight":100,"silver_weight":0,"bronze_weight":0,
            "rare_slots":1,"guaranteed_specials":1,"special_chance":0.0,"manager_chance":0.0,
            "allowed_rareflags":[3],"special_weights":{"3":100},"store_group":"special"}
    settings['packs']['202002']={
        'enabled':True,'name':'Pack joueurs MNG FUT','bio':'Joueurs du catalogue, hors DCE et objectifs.',
        'price':10000,'size':12,'gold_weight':84,'silver_weight':10,'bronze_weight':6,
        'rare_slots':3,'guaranteed_specials':0,'special_chance':0.10,'manager_chance':0.20,
        'allowed_rareflags':[0,1,3,12,21],'special_weights':{'3':100,'12':2,'21':100},'store_group':'special'}
    settings['packs']['202003']={
        'enabled':True,'name':'Pack écussons et maillots','bio':'12 objets de club FIFA 21.',
        'price':2500,'size':12,'club_items':True,'gold_weight':100,'silver_weight':0,'bronze_weight':0,
        'rare_slots':0,'special_chance':0,'manager_chance':0,'store_group':'special'}
    return settings


def constrain_sbcs(catalogue: dict, policy: dict) -> dict:
    if not policy.get("enabled"):
        return catalogue
    result = copy.deepcopy(catalogue)
    kept = []
    for ordinal, group in enumerate(result.get("sets", [])):
        if policy.get("sbcTabs"):
            if int(group.get("tabId", -1)) not in policy["sbcTabs"]:
                continue
            if group.get("releaseDate", "0000") > policy.get("releaseCutoff", "9999"):
                continue
            group.setdefault("_catalogOrdinal", ordinal)
            kept.append(group)
            continue
        # These authored player rewards can invent ratings/editions which do
        # not exist in the historical catalogue. Keep ordinary pack SBCs only.
        def incompatible(value):
            if isinstance(value, dict):
                if str(value.get("type", "")).upper() in {"PLAYER", "TOTW"}:
                    return True
                return any(incompatible(v) for v in value.values())
            if isinstance(value, list):
                return any(incompatible(v) for v in value)
            return False
        if int(group.get("tabId", 0)) in {6, 8} or incompatible(group):
            continue
        group["_catalogOrdinal"] = ordinal
        kept.append(group)
    result["sets"] = kept
    if policy.get("sbcTabs"):
        result["tabs"] = [tab for tab in result.get("tabs", []) if tab["id"] in policy["sbcTabs"]]
    return result


def migrate_club(state, catalogue: dict, policy: dict) -> dict:
    if not policy.get("enabled"):
        return {}
    marker = "catalog_policy_migration"
    previous = state.conn.execute("SELECT value FROM kv WHERE key=?", (marker,)).fetchone()
    if previous and json.loads(previous[0]).get("version") == policy["version"]:
        return json.loads(previous[0])
    rows = state.conn.execute("SELECT id, resource_id, pile, data FROM items").fetchall()
    result = {"version": policy["version"], "removed": 0, "refreshed": 0,
              "remapped": 0, "existingClub": bool(rows), "backup": None}
    # sqlite backup() includes committed WAL pages; never copy a live .sqlite3
    # file with ordinary filesystem copy. Failure aborts before touching items.
    state.conn.commit()
    if rows:
        folder = Path(state.path).parent / "backups"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = folder / f"before-summer2020-{stamp}.sqlite3"
        with closing(sqlite3.connect(backup_path)) as backup:
            state.conn.backup(backup)
        result["backup"] = str(backup_path)
    removed_ids = set()
    static_fields = ("resourceId", "assetId", "rating", "rareflag", "leagueId",
                     "teamid", "nation", "preferredPosition", "preferredFoot",
                     "weakFoot", "skillMoves", "workRateAttack", "workRateDefense",
                     "attributeList", "cardsubtypeid", "resourceGameYear",
                     "firstName", "lastName", "commonname", "discardValue")
    with state.conn:
        for row in rows:
            data = json.loads(row["data"])
            if data.get("itemType") != "player":
                continue
            rid = int(row["resource_id"])
            # Never turn a special edition into a base card just because it
            # shares an asset ID. Only known ordinary transfer versions remap.
            target = int(policy.get("remapBaseResources", {}).get(str(rid), rid))
            if target not in catalogue or int(data.get("rareflag", 0)) not in policy["allowedRarities"]:
                removed_ids.add(int(row["id"]))
                state.conn.execute("DELETE FROM items WHERE id=?", (row["id"],))
                result["removed"] += 1
                continue
            fresh = state.build_player_item(target, int(row["id"]), row["pile"],
                                            int(data.get("loans", 0) or 0))
            for key in static_fields:
                data[key] = data["appliedPosition"] if key == "preferredPosition" and data.get("appliedPosition") else fresh[key]
            # Gameplay progress, contracts, ownership and tradability survive.
            state.conn.execute("UPDATE items SET resource_id=?, data=? WHERE id=?",
                               (target, json.dumps(data), row["id"]))
            result["refreshed"] += 1
            result["remapped"] += int(target != rid)
        def clear_refs(value):
            if isinstance(value, list):
                return [clear_refs(v) for v in value]
            if isinstance(value, dict):
                return {k: (0 if k in {"id", "itemId", "captain"} and
                            isinstance(v, int) and v in removed_ids else clear_refs(v))
                        for k, v in value.items()}
            return value
        for row in state.conn.execute("SELECT id,data FROM squads").fetchall():
            squad = clear_refs(json.loads(row["data"]))
            state.conn.execute("UPDATE squads SET data=? WHERE id=?",
                               (json.dumps(squad), row["id"]))
        # Catalogue expansion alone must not reset ongoing matches or drafts.
        if removed_ids or result["remapped"]:
            state.conn.execute("DELETE FROM draft_runs")
            state.conn.execute("DELETE FROM squad_battles")
        state.conn.execute("INSERT OR REPLACE INTO kv(key,value) VALUES(?,?)",
                           (marker, json.dumps(result)))
    return result
