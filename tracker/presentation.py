"""User labels are mapped explicitly to decoded RAM fields."""
STAT_LABELS=(('ATQ','Ataque'),('DEF','Defensa'),('ATE','At. especial'),('DEE','Def. especial'),('VEL','Velocidad'))
def stat_text(pokemon):
    values=pokemon.get('stats') or {}
    return '\n'.join(f'{label}: {values.get(key,"—")}' for key,label in STAT_LABELS)
def move_text(pokemon,catalog):
    return '\n'.join(f'{i+1}. {catalog.name("moves",move)}' for i,move in enumerate(pokemon['moves']))
