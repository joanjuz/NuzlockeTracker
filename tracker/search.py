import unicodedata

def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD',str(value)).casefold() if not unicodedata.combining(c))

def matches(pokemon, query, catalog):
    words=normalized(query).split()
    text=normalized(' '.join([pokemon['nickname'],catalog.name('species',pokemon['species_id']),
         catalog.name('abilities',pokemon['ability_id']),catalog.name('items',pokemon['item_id']),
         str(pokemon['species_id']),*map(lambda n:catalog.name('moves',n),pokemon['moves'])]))
    return all(word in text for word in words)
