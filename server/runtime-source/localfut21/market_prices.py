"""Shared display and listing limits for MNG FUT player cards."""
def price_limits(meta):
    if str(meta.get('itemType', 'player')) != 'player':
        return 150, 15000000
    rating = int(meta.get('rating', 0) or 0)
    rarity = int(meta.get('rareflag', 0) or 0)
    if rarity == 12:
        if rating >= 92: return 1500000, 15000000
        if rating >= 90: return 750000, 8000000
        if rating >= 88: return 350000, 2500000
        if rating >= 85: return 150000, 900000
    elif rarity > 1 or meta.get('special'):
        if rating >= 91: return 500000, 5000000
        if rating >= 88: return 200000, 1500000
        if rating >= 85: return 70000, 500000
        if rating >= 80: return 30000, 200000
    elif rating >= 75:
        if rarity == 0: return 350, 10000
        if rating >= 92: return 500000, 4000000
        if rating >= 90: return 250000, 2000000
        if rating >= 89: return 100000, 900000
        if rating >= 87: return 35000, 350000
        if rating >= 85: return 12000, 150000
        if rating >= 83: return 4000, 60000
        if rating >= 80: return 1500, 30000
        return 700, 15000
    return 150, 15000000
