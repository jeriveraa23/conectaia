# Paleta de colores del IEC (Índice de Efectividad de Conectividad).
# Debe mantenerse sincronizada con la leyenda que se muestra en mapa.py.
COLOR_SIN_DATO = "#a0a0a0"  # gris neutro — nunca negro, para no confundir con bordes/resaltado


def color_por_iec(iec):
    if iec is None:
        return COLOR_SIN_DATO
    if iec >= 75:
        return "#1a9641"   # verde
    elif iec >= 60:
        return "#a6d96a"   # verde claro
    elif iec >= 45:
        return "#fdae61"   # naranja
    else:
        return "#d7191c"   # rojo


def color_por_nivel(nivel):
    colores = {
        "Alto":  "#1a9641",
        "Medio": "#a6d96a",
        "Bajo":  "#d7191c",
    }
    return colores.get(nivel, COLOR_SIN_DATO)