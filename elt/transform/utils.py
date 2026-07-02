import unicodedata


def estandarizar_texto(texto):
    if texto is None:
        return None
    sin_tildes = unicodedata.normalize("NFD", str(texto))
    sin_tildes = "".join(c for c in sin_tildes if unicodedata.category(c) != "Mn")
    return sin_tildes.upper().strip()