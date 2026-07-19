def color_por_iec(iec):
    if iec is None:
        return "#cccccc"
    if iec >= 75:
        return "#1a9641"
    elif iec >= 60:
        return "#a6d96a"
    elif iec >= 45:
        return "#fdae61"
    else:
        return "#d7191c"


def color_por_nivel(nivel):
    colores = {
        "Alto":  "#1a9641",
        "Medio": "#fdae61",
        "Bajo":  "#d7191c",
    }
    return colores.get(nivel, "#cccccc")