"""Instalador del mod de traducción al español para Rubinite.

Qué hace:
  1. resources.assets
     - Rellena la columna «es-ES» del I2Languages con traduccion_es.json y la activa.
     - Añade la etiqueta «Español» al selector de idioma de los ajustes (se clona la de pt-BR).
     - Añade la fuente dinámica SILVER SDF como respaldo global de TextMeshPro, para que
       ñ, ¿, ¡ y las mayúsculas acentuadas se vean con la fuente pixelada del juego.
  2. Assembly-CSharp.dll
     - El juego solo aplica la velocidad de escritura/sonido «alfabética» a en/pt/ru/uk; el
       resto usa la de chino/japonés/coreano (3 veces más lenta). Se invierte la comprobación
       (lento solo para zh-TW/zh-CN/ko, ja igual que antes) sin cambiar el tamaño del código.

Uso:  RubiniteES.exe  (menú)       RubiniteES.exe [--instalar | --desinstalar] [ruta_del_juego]
      python instalar.py ...        (mismos argumentos, desde el código fuente)
"""
import contextlib, copy, json, os, re, shutil, struct, sys

CONGELADO = getattr(sys, 'frozen', False)                    # ejecutable de PyInstaller
AQUI = os.path.dirname(sys.executable if CONGELADO else os.path.abspath(__file__))
RECURSOS = getattr(sys, '_MEIPASS', AQUI)                     # archivos empaquetados dentro del .exe
sys.path.insert(0, RECURSOS)
from i2asset import parse, build

ES_INDEX = 10              # columna «Español - España (es-ES)» del I2Languages
ES_NOMBRE = 'Español'
ETIQUETA_BASE = 'pt-BR'    # etiqueta del menú que se clona
FUENTE_RESPALDO = 'SILVER SDF'
SUFIJO_BAK = '.orig_es'


def bibliotecas_steam():
    """Carpetas de bibliotecas de Steam según el registro y libraryfolders.vdf."""
    raices = []
    try:
        import winreg
        for hive, clave in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam'),
                            (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam')):
            try:
                with winreg.OpenKey(hive, clave) as k:
                    for valor in ('SteamPath', 'InstallPath'):
                        try:
                            raices.append(os.path.normpath(winreg.QueryValueEx(k, valor)[0]))
                        except OSError:
                            pass
            except OSError:
                pass
    except ImportError:
        pass
    for raiz in list(raices):
        vdf = os.path.join(raiz, 'steamapps', 'libraryfolders.vdf')
        if os.path.isfile(vdf):
            texto = open(vdf, encoding='utf-8', errors='replace').read()
            raices += [p.replace('\\\\', '\\') for p in re.findall(r'"path"\s+"([^"]+)"', texto)]
    for unidad in 'CDEFGHIJ':
        raices += [unidad + r':\Program Files (x86)\Steam', unidad + r':\SteamLibrary', unidad + r':\Steam']
    return raices


def buscar_juego(arg):
    if arg:                                # si se indica una ruta, solo se usa esa
        candidatos = [arg, os.path.dirname(arg)]
    else:
        candidatos = [os.path.join(b, 'steamapps', 'common', 'Rubinite') for b in bibliotecas_steam()]
    for c in candidatos:
        if c and os.path.isfile(os.path.join(c, 'Rubinite_Data', 'resources.assets')):
            return c
    salir('No encontré el juego. Arrastra la carpeta de Rubinite sobre el programa, '
          'o pásala como argumento: RubiniteES.exe "D:\\...\\Rubinite"')


def salir(mensaje=None, codigo=1):
    if mensaje:
        print(mensaje)
    if CONGELADO:                          # que la ventana no se cierre sin dejar leer
        input('\nPresiona Enter para cerrar...')
    sys.exit(codigo if mensaje else 0)


@contextlib.contextmanager
def silencio():
    """Oculta los avisos que la librería nativa de typetrees escribe directamente en la consola."""
    sys.stdout.flush(); sys.stderr.flush()
    guardados = [os.dup(1), os.dup(2)]
    nulo = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(nulo, 1); os.dup2(nulo, 2)
        yield
    finally:
        sys.stdout.flush(); sys.stderr.flush()
        os.dup2(guardados[0], 1); os.dup2(guardados[1], 2)
        for fd in guardados + [nulo]:
            os.close(fd)


def respaldar(ruta, esta_parcheado):
    """Devuelve la ruta del original limpio, creando la copia de seguridad si hace falta."""
    bak = ruta + SUFIJO_BAK
    if not esta_parcheado:
        shutil.copy2(ruta, bak)          # original actual (también tras una actualización del juego)
    elif not os.path.isfile(bak):
        salir(f'{ruta} ya está modificado y no hay copia {bak}. Verifica los archivos en Steam y reintenta.')
    return bak


# ---------------------------------------------------------------- resources.assets
def parchear_assets(juego):
    import UnityPy
    from UnityPy.helpers.TypeTreeGenerator import TypeTreeGenerator

    datos = os.path.join(juego, 'Rubinite_Data')
    ruta = os.path.join(datos, 'resources.assets')
    externa = os.path.join(AQUI, 'traduccion_es.json')        # permite corregir textos sin recompilar
    traduccion = json.load(open(externa if os.path.isfile(externa) else os.path.join(RECURSOS, 'traduccion_es.json'),
                                encoding='utf-8'))
    avisos = []

    def cargar(p):
        # En memoria (para poder reemplazar el archivo luego) pero con el nombre real, para que
        # UnityPy resuelva las referencias externas (globalgamemanagers.assets) desde `datos`.
        env = UnityPy.Environment(path=datos)
        with open(p, 'rb') as f:
            env.load_file(f.read(), name='resources.assets')
        sf = env.files['resources.assets']
        gen = TypeTreeGenerator(sf.unity_version)
        gen.load_local_game(juego)
        env.typetree_generator = gen
        return env, sf

    # tabla pathID -> clase, a partir de los MonoScript de globalgamemanagers.assets
    ggm = UnityPy.load(os.path.join(datos, 'globalgamemanagers.assets'))
    scripts = {o.path_id: o.read().m_ClassName
               for o in next(iter(ggm.files.values())).objects.values() if o.type.name == 'MonoScript'}

    def de_clase(sf, nombre):
        """MonoBehaviours cuyo script es `nombre` (se lee el PPtr m_Script sin typetree)."""
        idx_ggm = 1 + [e.path for e in sf.externals].index('globalgamemanagers.assets')
        res = []
        for o in sf.objects.values():
            if o.type.name == 'MonoBehaviour':
                fid, pid = struct.unpack_from('<iq', o.get_raw_data(), 16)
                if fid == idx_ggm and scripts.get(pid) == nombre:
                    res.append(o)
        return res

    # ¿ya está parcheado? Entonces se parte del original guardado.
    env, sf = cargar(ruta)
    i2 = de_clase(sf, 'LanguageSourceAsset')[0]
    parcheado = parse(i2.get_raw_data())['languages'][ES_INDEX]['Name'] == ES_NOMBRE
    origen = respaldar(ruta, parcheado)
    if parcheado:
        env, sf = cargar(origen)
        i2 = de_clase(sf, 'LanguageSourceAsset')[0]
    objs = sf.objects

    # 1) textos
    d = parse(i2.get_raw_data())
    lang = d['languages'][ES_INDEX]
    assert lang['Code'].strip() == 'es-ES', lang
    lang['Name'], lang['Flags'] = ES_NOMBRE, 0
    usados = 0
    for t in d['terms']:
        texto = traduccion.get(t['Term'])
        if texto is not None and len(t['Languages']) > ES_INDEX:
            t['Languages'][ES_INDEX] = texto
            usados += 1
    i2.set_raw_data(build(d))
    faltan = len(d['terms']) - usados
    avisos.append(f'  Textos traducidos: {usados}/{len(d["terms"])}' + (f' ({faltan} sin traducir, quedarán en inglés)' if faltan else ''))

    # 2) etiqueta «Español» en cada selector de idioma
    siguiente_id = [max(objs) + 1]
    def nuevo_objeto(plantilla, arbol):
        o = copy.copy(plantilla)
        o.path_id = siguiente_id[0]; siguiente_id[0] += 1
        objs[o.path_id] = o
        o.save_typetree(arbol)
        return o.path_id

    pptr = lambda pid: {'m_FileID': 0, 'm_PathID': pid}
    selectores = de_clase(sf, 'GameSettingPaper')
    for gsp in selectores:
        arbol_gsp = gsp.read_typetree()
        etiquetas = [objs[p['m_PathID']] for p in arbol_gsp['languageNames']]
        if any(e.read_typetree()['m_Name'] == 'es-ES' for e in etiquetas):
            continue
        base = next(e for e in etiquetas if e.read_typetree()['m_Name'] == ETIQUETA_BASE)
        go = base.read_typetree()
        comps = [objs[c['component']['m_PathID']] for c in go['m_Component']]
        nuevo_go = siguiente_id[0] + len(comps)          # los componentes se crean antes que el GameObject
        ids_comp = []
        for c in comps:
            t = c.read_typetree()
            t['m_GameObject'] = pptr(nuevo_go)
            if c.type.name == 'RectTransform':
                t['m_Children'] = []
                padre = objs[t['m_Father']['m_PathID']]
            if c.type.name == 'MonoBehaviour':
                t['m_text'] = ES_NOMBRE
            ids_comp.append(nuevo_objeto(c, t))
        go['m_Name'] = 'es-ES'
        go['m_Component'] = [{'component': pptr(i)} for i in ids_comp]
        assert nuevo_objeto(base, go) == nuevo_go
        rect_nuevo = next(i for i, c in zip(ids_comp, comps) if c.type.name == 'RectTransform')
        tp = padre.read_typetree(); tp['m_Children'].append(pptr(rect_nuevo)); padre.save_typetree(tp)
        arbol_gsp['languageNames'].append(pptr(nuevo_go)); gsp.save_typetree(arbol_gsp)
    avisos.append(f'  Selector de idioma: opción «{ES_NOMBRE}» añadida en {len(selectores)} menús')

    # 3) fuente de respaldo global
    ajustes = de_clase(sf, 'TMP_Settings')[0]
    fuente = next(o for o in de_clase(sf, 'TMP_FontAsset') if o.read_typetree()['m_Name'] == FUENTE_RESPALDO)
    t = ajustes.read_typetree()
    if all(f['m_PathID'] != fuente.path_id for f in t['m_fallbackFontAssets']):
        t['m_fallbackFontAssets'].append(pptr(fuente.path_id))
        ajustes.save_typetree(t)
    avisos.append(f'  Fuente de respaldo: {FUENTE_RESPALDO} (ñ ¿ ¡ Á É Í Ó Ú)')

    # Unity alinea los datos de cada objeto a 16 bytes; UnityPy usa 8. Se fuerza 16 al guardar.
    from UnityPy.streams.EndianBinaryWriter import EndianBinaryWriter
    alinear = EndianBinaryWriter.align_stream
    EndianBinaryWriter.align_stream = lambda self, alignment=4: alinear(self, 16 if alignment == 8 else alignment)
    try:
        datos_nuevos = sf.save()
    finally:
        EndianBinaryWriter.align_stream = alinear
    tmp = ruta + '.tmp_es'
    with open(tmp, 'wb') as f:
        f.write(datos_nuevos)
    os.replace(tmp, ruta)
    return avisos


# ---------------------------------------------------------------- Assembly-CSharp.dll
def tokens_us(dll):
    """Mapa cadena -> token ldstr (0x70......) del heap #US."""
    import dnfile
    pe = dnfile.dnPE(data=dll)
    heap = pe.net.user_strings.__data__
    res, i = {}, 1
    while i < len(heap):
        inicio, b = i, heap[i]
        if b & 0x80 == 0: n, i = b, i + 1
        elif b & 0xC0 == 0x80: n, i = ((b & 0x3F) << 8) | heap[i + 1], i + 2
        else: n, i = ((b & 0x1F) << 24) | (heap[i + 1] << 16) | (heap[i + 2] << 8) | heap[i + 3], i + 4
        if n:
            s = heap[i:i + n - 1].decode('utf-16le', 'replace')
            res.setdefault(s, 0x70000000 | inicio)
        i += n
    return res


def patrones_idioma(dll):
    """(patrón original, patrón ya parcheado, T) de las 4 comprobaciones de idioma alfabético."""
    tok = tokens_us(bytes(dll))
    T = lambda s: struct.pack('<I', tok[s])
    LD = rb'(?:[\x06-\x09]|\x11.)'                      # ldloc.0-3 | ldloc.s N
    CMP = lambda s: rb'(' + LD + rb')\x72' + re.escape(T(s)) + rb'\x28(....)'
    patron = re.compile(CMP('en-US') + rb'\x2d(.)' + CMP('pt-BR') + rb'\x2d.' + CMP('ru') + rb'\x2d.' +
                        CMP('uk') + rb'([\x2c\x2d])(.)(?:' + CMP('ja') + rb'\x2d(.)\x2b(.))?', re.S)
    ya_hecho = re.compile(CMP('zh-TW') + rb'\x2d.' + CMP('zh-CN') + rb'\x2d.' + CMP('ko') + rb'\x2d.', re.S)
    return patron, ya_hecho, T


def parchear_dll(juego):
    # Se modifica en su sitio (sin partir de la copia de seguridad) para no borrar
    # parches de otros mods que también toquen esta DLL.
    ruta = os.path.join(juego, 'Rubinite_Data', 'Managed', 'Assembly-CSharp.dll')
    dll = bytearray(open(ruta, 'rb').read())
    patron, ya_hecho, T = patrones_idioma(dll)
    hallados = list(patron.finditer(dll))
    if not hallados and ya_hecho.search(dll):
        print('  Velocidad de escritura y sonido del diálogo: ya estaban ajustados')
        return
    if len(hallados) == 4:
        respaldar(ruta, False)
    if len(hallados) != 4:
        print(f'  AVISO: se esperaban 4 comprobaciones de idioma y hay {len(hallados)}; no se toca la DLL.')
        return

    s8 = lambda x: struct.unpack('b', x)[0]
    for m in hallados:
        ld, eq = m.group(1), m.group(2)
        tam = len(ld) + 12                                 # ldloc + ldstr(5) + call(5) + br.s(2)
        ini = m.start()
        destino = lambda k, rel: ini + tam * (k + 1) + s8(rel)   # absoluto desde el salto k
        latino = destino(0, m.group(3))
        cinco = m.group(12) is not None
        if not cinco:                                      # 4 comprobaciones; la última (brfalse) salta a «no latino»
            assert m.group(10) == b'\x2c'
            no_latino = destino(3, m.group(11))
            orden = [('zh-TW', no_latino), ('zh-CN', no_latino), ('ko', no_latino), ('ja', no_latino)]
        else:                                              # 5 comprobaciones (la 5.ª es ja) + br.s al final
            ja = destino(4, m.group(14))
            fin = ini + tam * 5 + 2 + s8(m.group(15))
            orden = [('zh-TW', fin), ('zh-CN', fin), ('ko', fin), ('ja', ja)]
        nuevo = bytearray()
        for k, (codigo, dst) in enumerate(orden):
            rel = dst - (ini + tam * (k + 1))
            nuevo += ld + b'\x72' + T(codigo) + b'\x28' + eq + b'\x2d' + struct.pack('b', rel)
        if cinco:                                          # nop de relleno para conservar el tamaño, y salto a «latino»
            nuevo += b'\x00' * tam + b'\x2b' + struct.pack('b', latino - (ini + tam * 5 + 2))
        assert len(nuevo) == m.end() - ini, (len(nuevo), m.end() - ini)
        dll[ini:m.end()] = nuevo
    tmp = ruta + '.tmp_es'
    open(tmp, 'wb').write(dll)
    os.replace(tmp, ruta)
    print('  Velocidad de escritura y sonido del diálogo: ajustados para el español')


def restaurar_dll(ruta):
    """Deshace solo el cambio de este mod reconstruyendo las instrucciones originales.

    No se copia la copia de seguridad encima: así no se pierden otros mods, y funciona aunque otra
    herramienta haya reescrito la DLL (las posiciones y los tokens pueden haber cambiado)."""
    dll = bytearray(open(ruta, 'rb').read())
    tok = tokens_us(bytes(dll))
    T = lambda s: struct.pack('<I', tok[s])
    LD = rb'(?:[\x06-\x09]|\x11.)'
    CMP = lambda s: rb'(' + LD + rb')\x72' + re.escape(T(s)) + rb'\x28(....)'
    parcheado = re.compile(CMP('zh-TW') + rb'\x2d(.)' + CMP('zh-CN') + rb'\x2d.' + CMP('ko') + rb'\x2d.' +
                           CMP('ja') + rb'\x2d(.)(?:(\x00+)\x2b(.))?', re.S)
    s8 = lambda x: struct.unpack('b', x)[0]
    revertidos = 0
    for m in list(parcheado.finditer(dll)):
        ld, eq = m.group(1), m.group(2)
        tam = len(ld) + 12
        ini = m.start()
        cinco = m.group(11) is not None and len(m.group(11)) == tam
        if m.group(11) is not None and not cinco:
            continue
        if not cinco:        # 4 comprobaciones: los códigos no alfabéticos saltaban a «no latino»; lo latino sigue
            no_latino = ini + tam + s8(m.group(3))
            latino = ini + tam * 4
            orden = [('en-US', 0x2d, latino), ('pt-BR', 0x2d, latino), ('ru', 0x2d, latino), ('uk', 0x2c, no_latino)]
        else:                # 5 comprobaciones + br.s
            fin = ini + tam + s8(m.group(3))
            ja = ini + tam * 4 + s8(m.group(10))
            latino = ini + tam * 5 + 2 + s8(m.group(12))
            orden = [('en-US', 0x2d, latino), ('pt-BR', 0x2d, latino), ('ru', 0x2d, latino), ('uk', 0x2d, latino),
                     ('ja', 0x2d, ja)]
        nuevo = bytearray()
        for k, (codigo, salto, dst) in enumerate(orden):
            nuevo += ld + b'\x72' + T(codigo) + b'\x28' + eq + bytes([salto]) + struct.pack('b', dst - (ini + tam * (k + 1)))
        if cinco:
            nuevo += b'\x2b' + struct.pack('b', fin - (ini + tam * 5 + 2))
        assert len(nuevo) == m.end() - ini
        dll[ini:m.end()] = nuevo
        revertidos += 1
    if revertidos:
        tmp = ruta + '.tmp_es'
        open(tmp, 'wb').write(dll)
        os.replace(tmp, ruta)
    if os.path.isfile(ruta + SUFIJO_BAK):
        os.remove(ruta + SUFIJO_BAK)
    return revertidos


def desinstalar(juego):
    n = 0
    assets = os.path.join(juego, 'Rubinite_Data', 'resources.assets')
    if os.path.isfile(assets + SUFIJO_BAK):
        shutil.copy2(assets + SUFIJO_BAK, assets); os.remove(assets + SUFIJO_BAK); n += 1
    dll = os.path.join(juego, 'Rubinite_Data', 'Managed', 'Assembly-CSharp.dll')
    if restaurar_dll(dll):
        n += 1
    print(f'Restaurados {n} archivos originales.' if n else 'No había nada que restaurar.')


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    accion = 'desinstalar' if '--desinstalar' in sys.argv else 'instalar' if '--instalar' in sys.argv else None
    print('=== Rubinite: traducción al español ===\n')
    juego = buscar_juego(args[0] if args else None)
    print(f'Juego: {juego}\n')
    if accion is None:
        if not CONGELADO:
            accion = 'instalar'
        else:
            print('  1) Instalar / actualizar la traducción')
            print('  2) Desinstalar (restaurar los archivos originales)')
            accion = {'1': 'instalar', '2': 'desinstalar'}.get(input('\nElige 1 o 2 y presiona Enter: ').strip())
            if not accion:
                salir('Opción no válida.')
            print()
    if os.name == 'nt':
        import subprocess
        tareas = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Rubinite.exe'], capture_output=True).stdout
        if b'Rubinite.exe' in tareas:
            salir('El juego está abierto. Ciérralo y vuelve a intentarlo.')
    if accion == 'desinstalar':
        desinstalar(juego)
    else:
        print('Parcheando resources.assets (tarda unos segundos)...')
        with silencio():
            avisos = parchear_assets(juego)
        print('\n'.join(avisos))
        print('Parcheando Assembly-CSharp.dll...')
        parchear_dll(juego)
        print('\n¡Listo! En el juego: Configuración > Juego > Idioma > Español.')
    salir(codigo=0)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        salir(f'\nOcurrió un error: {e}\nSi el problema sigue, repórtalo en '
              'https://github.com/Vizpok/rubinite-spanish-translation/issues')
