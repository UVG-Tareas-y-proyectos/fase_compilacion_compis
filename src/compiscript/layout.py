"""Modelo de memoria abstracta de 64 bits y registros de activación."""

WORD = 8
HEADER = {"enlace_control": 0, "enlace_acceso": 8,
          "direccion_retorno": 16, "valor_retorno": 24}


def extend_symbols(table):
    """Las direcciones son simbólicas. No son direcciones de RAM de Python."""
    frames = {}
    for i, env in enumerate(table.environments()):
        env.code_id = f"E{i}"
        owner = env
        while owner.parent is not None and owner.kind != "función":
            owner = owner.parent
        key = id(owner)
        frame = frames.setdefault(key, {
            "entorno": owner.name, "cabecera": dict(HEADER),
            "parametros": [], "locales": [], "temporales": [], "tamano": 32,
        })
        env.frame = frame
        for symbol in env.symbols.values():
            symbol.address = f"v{i}_{symbol.name}"
            symbol.storage = "global" if owner.parent is None else "local"
            symbol.size = WORD
            symbol.offset = frame["tamano"]
            frame["tamano"] += WORD
            section = "parametros" if symbol.kind == "parámetro" else "locales"
            frame[section].append({"nombre": symbol.name, "direccion": symbol.address,
                                   "desplazamiento": symbol.offset, "tamano": WORD})
            if symbol.kind in {"función", "método"}:
                symbol.label = f"F{i}_{symbol.name}"
            elif symbol.kind == "clase":
                symbol.label = f"C{i}_{symbol.name}"
    return frames
