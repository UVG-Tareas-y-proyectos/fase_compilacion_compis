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
        if owner.kind == 'función' and owner.parent and owner.parent.kind == 'clase' and 'receptor' not in frame:
            frame['receptor'] = {'nombre': '@this', 'desplazamiento': frame['tamano'], 'tamano': WORD}
            frame['tamano'] += WORD
        env.frame = frame
        for symbol in env.symbols.values():
            symbol.address = f"v{i}_{symbol.name}"
            symbol.storage = "global" if owner.parent is None else "local"
            symbol.size = WORD
            if env.kind == 'clase':
                symbol.storage = 'método' if symbol.kind == 'método' else 'atributo'
                symbol.offset = 0
                if symbol.kind == 'método':
                    symbol.label = f'F{i}_{symbol.name}'
                continue
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


def layout_classes(table):
    classes = {s.name: s for e in table.environments() for s in e.symbols.values()
               if s.kind == 'clase'}
    done = set()

    def visit(symbol, path):
        if symbol.name in done:
            return
        if symbol.name in path:
            raise ValueError('ciclo en la jerarquía de clases')
        parent = classes.get(symbol.metadata.get('parent'))
        offset = WORD  # cabecera: descriptor de clase
        if parent:
            visit(parent, path | {symbol.name})
            offset = parent.size
        for member in symbol.environment.symbols.values():
            if member.kind not in {'función', 'método'}:
                member.storage = 'atributo'
                member.offset = offset
                offset += WORD
        symbol.size = offset
        done.add(symbol.name)

    for symbol in classes.values():
        visit(symbol, set())
