#!/usr/bin/env python3
"""
ms_capture.py — Captura de trechos de partitura MuseScore como SVG/PNG/PDF
===========================================================================
Equivalente à câmera do MuseScore 3, como ferramenta externa para MU4.

Uso básico:
    python ms_capture.py partitura.mscz -s 5 -e 8 -f svg -o saida.svg

Interface gráfica (sem argumentos):
    python ms_capture.py

Requisitos:
    - Python 3.8+
    - MuseScore 4 instalado
    - tkinter para GUI (Linux: sudo apt install python3-tk)
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
#  DETECÇÃO DO EXECUTÁVEL MUSESCORE
# ─────────────────────────────────────────────────────────────────────────────

def find_mscore_executable():
    system = platform.system()
    candidates = []
    if system == "Windows":
        candidates = [
            r"C:\Program Files\MuseScore 4\bin\MuseScore4.exe",
            r"C:\Program Files (x86)\MuseScore 4\bin\MuseScore4.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\MuseScore 4\bin\MuseScore4.exe"),
        ]
    elif system == "Darwin":
        candidates = [
            "/Applications/MuseScore 4.app/Contents/MacOS/mscore",
            "/Applications/MuseScore4.app/Contents/MacOS/mscore",
        ]
    else:
        candidates = [
            "/usr/bin/mscore4", "/usr/bin/mscore",
            "/usr/local/bin/mscore4",
            "/snap/bin/musescore",
        ]

    for path in candidates:
        if path and os.path.isfile(path):
            return path

    for name in ("mscore4", "mscore", "MuseScore4", "MuseScore"):
        found = shutil.which(name)
        if found:
            return found
    return None


# ─────────────────────────────────────────────────────────────────────────────
#  LEITURA DO MSCZ
# ─────────────────────────────────────────────────────────────────────────────

def read_mscz(mscz_path):
    """
    Extrai o conteúdo de um .mscz.
    Retorna (mscx_content_str, zip_namelist, zip_other_files_dict)
    onde zip_other_files_dict = {arcname: bytes} para todos exceto o .mscx principal.
    """
    with zipfile.ZipFile(mscz_path, "r") as zf:
        names = zf.namelist()
        mscx_name = None
        for n in names:
            if n.endswith(".mscx") and "/" not in n:   # raiz do zip
                mscx_name = n
                break
        if mscx_name is None:
            # Tenta qualquer .mscx
            for n in names:
                if n.endswith(".mscx"):
                    mscx_name = n
                    break
        if mscx_name is None:
            raise FileNotFoundError(f"Nenhum .mscx encontrado em {mscz_path}")

        mscx_content = zf.read(mscx_name).decode("utf-8")
        others = {}
        for n in names:
            if n != mscx_name:
                others[n] = zf.read(n)

    return mscx_content, mscx_name, others


def write_mscz(out_path, mscx_name, mscx_content_str, others):
    """
    Escreve um novo .mscz com o conteúdo modificado.
    mscx_name: nome do arquivo dentro do zip (ex: "partitura.mscx")
    """
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(mscx_name, mscx_content_str.encode("utf-8"))
        for arcname, data in others.items():
            # Exclui thumbnail pois pode ser inválido após edição
            if "thumbnail" not in arcname.lower():
                zf.write.__doc__  # no-op
                zf.writestr(arcname, data)


# ─────────────────────────────────────────────────────────────────────────────
#  INFORMAÇÕES DA PARTITURA
# ─────────────────────────────────────────────────────────────────────────────

def parse_mscx(mscx_content):
    """Faz parse do XML e retorna o ElementTree."""
    # Remove declaração XML se presente para evitar conflito de encoding
    content = mscx_content
    if content.startswith("<?xml"):
        content = content[content.index("?>") + 2:].lstrip()
    return ET.fromstring(content)


def count_measures(root):
    """Conta compassos no Staff id=1 (evita duplicatas de multi-staff)."""
    # MU4: Score > Staff[@id="1"] > Measure
    for staff in root.iter("Staff"):
        if staff.get("id") == "1":
            return len(list(staff.findall("Measure")))
    # Fallback
    measures = list(root.iter("Measure"))
    return len(measures)


def get_instrument_names(root):
    names = []
    for part in root.iter("Part"):
        for tag in ("longName", "trackName", "shortName", "Instrument"):
            el = part.find(tag)
            if el is not None and el.text and el.text.strip():
                names.append(el.text.strip())
                break
        else:
            names.append(f"Instrumento {len(names)+1}")
    return names





# ─────────────────────────────────────────────────────────────────────────────
#  RECORTE DE COMPASSOS
# ─────────────────────────────────────────────────────────────────────────────

def crop_measures(root, start_measure, end_measure):
    """
    Remove compassos fora do intervalo [start_measure, end_measure] (1-based).
    Modifica o ElementTree in-place.
    """
    s = start_measure - 1   # 0-based
    e = end_measure          # exclusive 0-based

    for staff in root.iter("Staff"):
        measures = list(staff.findall("Measure"))
        for i, m in enumerate(measures):
            if i < s or i >= e:
                staff.remove(m)

    # Renumera compassos a partir de 1
    for staff in root.iter("Staff"):
        for i, m in enumerate(staff.findall("Measure")):
            m.set("number", str(i + 1))


# ─────────────────────────────────────────────────────────────────────────────
#  FILTRAGEM DE PAUTAS
# ─────────────────────────────────────────────────────────────────────────────

def _int_or_none(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _sort_numeric_strings(values):
    def key(v):
        n = _int_or_none(v)
        return n if n is not None else 10**9
    return sorted(values, key=key)


def _score_node(root):
    score = root.find("Score")
    return score if score is not None else root


def _staff_id_from_track(value):
    """Converte track MuseScore em id de pauta 1-based. Cada pauta tem 4 tracks/vozes."""
    n = _int_or_none(value)
    if n is None or n < 0:
        return None
    return str(n // 4 + 1)


def _staff_id_from_staff_index(value):
    """Converte staffIdx 0-based em id de pauta 1-based."""
    n = _int_or_none(value)
    if n is None or n < 0:
        return None
    return str(n + 1)


def _staff_id_from_staff_number(value):
    """Lê referências diretas a pauta em tags/atributos staff/staffId 1-based."""
    n = _int_or_none(value)
    if n is None or n <= 0:
        return None
    return str(n)


def _remap_track_number(value, staff_id_map):
    n = _int_or_none(value)
    if n is None or n < 0:
        return value
    old_staff_id = str(n // 4 + 1)
    voice_index = n % 4
    new_staff_id = staff_id_map.get(old_staff_id)
    if new_staff_id is None:
        return value
    return str((int(new_staff_id) - 1) * 4 + voice_index)


def _remap_staff_index(value, staff_id_map):
    n = _int_or_none(value)
    if n is None or n < 0:
        return value
    old_staff_id = str(n + 1)
    new_staff_id = staff_id_map.get(old_staff_id)
    if new_staff_id is None:
        return value
    return str(int(new_staff_id) - 1)


def _remap_staff_number(value, staff_id_map):
    n = _int_or_none(value)
    if n is None or n <= 0:
        return value
    new_staff_id = staff_id_map.get(str(n))
    if new_staff_id is None:
        return value
    return str(new_staff_id)


def _parent_map(root):
    return {child: parent for parent in root.iter() for child in list(parent)}


def _depth_map(root):
    depths = {root: 0}
    stack = [root]
    while stack:
        parent = stack.pop()
        for child in list(parent):
            depths[child] = depths[parent] + 1
            stack.append(child)
    return depths


def _remove_elements(root, elements):
    """Remove elementos do XML, processando primeiro os mais profundos."""
    if not elements:
        return
    parents = _parent_map(root)
    depths = _depth_map(root)
    protected = {"Score", "Staff", "Measure", "voice", "Part"}
    for el in sorted(elements, key=lambda e: depths.get(e, 0), reverse=True):
        if el is root or el.tag in protected:
            continue
        parent = parents.get(el)
        if parent is not None:
            try:
                parent.remove(el)
            except ValueError:
                pass


def _clean_and_remap_staff_references(root, keep_staff_ids, staff_id_map=None):
    """
    Remove objetos que apontam para pautas descartadas e, opcionalmente,
    remapeia tracks/staff/staffIdx das pautas mantidas.

    Detalhe importante do MSCX/MU4:
      - tracks são 0-based e agrupados em blocos de 4 por pauta;
      - staffIdx é 0-based;
      - algumas referências usam staff/staffId 1-based diretamente;
      - <Staff> maiúsculo é estrutura de pauta e não deve ser confundido
        com tags <staff> minúsculas usadas como referência por alguns objetos.
    """
    keep_set = set(str(x) for x in keep_staff_ids)
    track_names = {
        "track", "track2", "starttrack", "endtrack",
        "stafftrack", "sourcetrack", "destinationtrack",
        "track1", "track3", "track4",
    }
    staff_index_names = {"staffidx", "staffidx2", "staffindex", "staffindex2"}
    staff_number_names = {
        "staff", "staff2", "staffid", "staffid2",
        "staffno", "staffno2", "staffn", "staffn2",
    }

    parents = _parent_map(root)
    to_remove = set()

    def mark_parent_or_self(el, is_child=True):
        target = parents.get(el) if is_child else el
        if target is not None:
            to_remove.add(target)

    # 1. Remove objetos que ainda apontam para pautas descartadas.
    for el in root.iter():
        tag_original = el.tag if isinstance(el.tag, str) else ""
        tag = tag_original.lower()
        text = el.text.strip() if el.text else ""

        # Tags de referência textual. Não tratar <Staff> estrutural como <staff>.
        if text:
            if tag in track_names:
                sid = _staff_id_from_track(text)
                if sid is not None and sid not in keep_set:
                    mark_parent_or_self(el, is_child=True)
            elif tag in staff_index_names:
                sid = _staff_id_from_staff_index(text)
                if sid is not None and sid not in keep_set:
                    mark_parent_or_self(el, is_child=True)
            elif tag_original != "Staff" and tag in staff_number_names:
                sid = _staff_id_from_staff_number(text)
                if sid is not None and sid not in keep_set:
                    mark_parent_or_self(el, is_child=True)

        # Atributos de referência.
        for attr, value in list(el.attrib.items()):
            a = attr.lower()
            if a in track_names:
                sid = _staff_id_from_track(value)
                if sid is not None and sid not in keep_set:
                    mark_parent_or_self(el, is_child=False)
            elif a in staff_index_names:
                sid = _staff_id_from_staff_index(value)
                if sid is not None and sid not in keep_set:
                    mark_parent_or_self(el, is_child=False)
            elif a in staff_number_names and el.tag != "Staff":
                sid = _staff_id_from_staff_number(value)
                if sid is not None and sid not in keep_set:
                    mark_parent_or_self(el, is_child=False)

    _remove_elements(root, to_remove)

    # 2. Remapeia as referências restantes, se a estratégia pedir compactação
    # para 1,2,3... .
    if not staff_id_map:
        return

    for el in root.iter():
        tag_original = el.tag if isinstance(el.tag, str) else ""
        tag = tag_original.lower()
        if el.text is not None:
            text = el.text.strip()
            if tag in track_names:
                new_text = _remap_track_number(text, staff_id_map)
                if new_text != text:
                    el.text = new_text
            elif tag in staff_index_names:
                new_text = _remap_staff_index(text, staff_id_map)
                if new_text != text:
                    el.text = new_text
            elif tag_original != "Staff" and tag in staff_number_names:
                new_text = _remap_staff_number(text, staff_id_map)
                if new_text != text:
                    el.text = new_text

        for attr, value in list(el.attrib.items()):
            a = attr.lower()
            if a in track_names:
                el.set(attr, _remap_track_number(value, staff_id_map))
            elif a in staff_index_names:
                el.set(attr, _remap_staff_index(value, staff_id_map))
            elif a in staff_number_names and el.tag != "Staff":
                el.set(attr, _remap_staff_number(value, staff_id_map))


def _remove_layout_caches(score):
    """Remove caches/estruturas auxiliares que podem manter pautas antigas visíveis."""
    # Excerpts/partes extraídas não são necessários para uma captura temporária
    # e frequentemente contêm referências antigas a staff/track.
    for tag in ("Excerpt", "PageList", "pages", "Pages"):
        for el in list(score.findall(tag)):
            score.remove(el)


def _part_staff_descriptors(part):
    """Retorna os <Staff> descritores dentro de <Part>, inclusive aninhados."""
    return [el for el in part.iter("Staff")]


def _numeric_staff_ids(score):
    """IDs globais dos <Staff> musicais diretos do <Score>, em ordem visual."""
    ids = []
    for staff in score.findall("Staff"):
        sid = staff.get("id")
        if sid is not None:
            ids.append(str(sid))
    return _sort_numeric_strings(ids)


def _build_part_to_global_staff_map(score):
    """
    Mapeia cada <Part> para os IDs globais de pauta do <Score>.

    O MSCX do MuseScore costuma guardar duas camadas diferentes:
      1. <Score>/<Part>/.../<Staff>  = definição visual/instrumental da pauta;
      2. <Score>/<Staff id="N">      = conteúdo musical da pauta N.

    Em alguns arquivos, o id do Staff dentro de Part coincide com o id global.
    Em outros, especialmente após edições/importações, ele pode ser local ou
    insuficiente para decidir qual Part remover. Por isso usamos duas etapas:
      - se os IDs dos descritores cobrem exatamente os IDs globais, usamos eles;
      - caso contrário, fazemos o pareamento pela ordem das Parts e pela
        quantidade de Staffs descritores em cada Part.
    """
    parts = list(score.findall("Part"))
    global_ids = _numeric_staff_ids(score)
    global_set = set(global_ids)

    # Tentativa 1: IDs explícitos nos descritores de Part.
    explicit = []
    flat = []
    for part in parts:
        pairs = []
        for desc in _part_staff_descriptors(part):
            sid = desc.get("id")
            if sid in global_set:
                pairs.append((desc, sid))
                flat.append(sid)
        explicit.append((part, pairs))

    if flat and len(flat) == len(set(flat)) and set(flat) == global_set:
        return explicit, global_ids

    # Tentativa 2: pareamento ordinal. Essa é a rota que corrige o caso em que
    # a pauta 2 selecionada era remapeada para o instrumento visual da pauta 1.
    mapped = []
    offset = 0
    for part in parts:
        descs = _part_staff_descriptors(part)
        # Uma Part sem descritor explícito ainda costuma equivaler a uma pauta.
        count = len(descs) if descs else 1
        assigned = global_ids[offset:offset + count]
        pairs = []
        for i, sid in enumerate(assigned):
            desc = descs[i] if i < len(descs) else None
            pairs.append((desc, sid))
        mapped.append((part, pairs))
        offset += count

    return mapped, global_ids


def _renumber_score_staffs(score, staff_id_map):
    for staff in score.findall("Staff"):
        old = staff.get("id")
        if old in staff_id_map:
            staff.set("id", staff_id_map[old])


def _renumber_kept_part_descriptors(part_map, staff_id_map):
    """Atualiza IDs dos descritores <Part>/<Staff> mantidos."""
    for part, pairs in part_map:
        for desc, old_sid in pairs:
            if desc is not None and old_sid in staff_id_map:
                desc.set("id", staff_id_map[old_sid])


def _prune_parts_by_global_staffs(root, score, keep_set):
    """
    Remove Parts/instrumentos não escolhidos e descritores de pautas descartadas.
    Retorna o mapa Part -> pautas globais antigas ainda mantidas.
    """
    part_map, global_ids = _build_part_to_global_staff_map(score)
    parents = _parent_map(root)
    kept_part_map = []

    for part, pairs in list(part_map):
        kept_pairs = [(desc, sid) for desc, sid in pairs if sid in keep_set]

        # Se nenhuma pauta global dessa Part foi pedida, remove a Part inteira.
        if not kept_pairs:
            try:
                score.remove(part)
            except ValueError:
                pass
            continue

        # Se a Part tem várias pautas e só algumas foram pedidas, remove apenas
        # os descritores das pautas descartadas dentro dessa Part.
        kept_descs = {desc for desc, _sid in kept_pairs if desc is not None}
        for desc, sid in pairs:
            if desc is not None and desc not in kept_descs:
                parent = parents.get(desc)
                if parent is not None:
                    try:
                        parent.remove(desc)
                    except ValueError:
                        pass

        kept_part_map.append((part, kept_pairs))

    return kept_part_map, global_ids


def hide_staves(root, keep_staff_ids, renumber=True):
    """
    Mantém apenas as pautas/partes solicitadas.

    Esta versão remove o instrumento/Part correspondente às pautas descartadas,
    e não apenas o conteúdo musical do <Score>/<Staff>. Isso evita o resultado
    "uma pauta preenchida + outra pauta vazia" no SVG/PNG/PDF.
    """
    keep_set = {str(i).strip() for i in keep_staff_ids if str(i).strip()}
    if not keep_set:
        raise ValueError("Informe ao menos uma pauta para exportar, ou use 'all'.")

    score = _score_node(root)
    all_score_staff_ids = set(_numeric_staff_ids(score))

    invalid = keep_set - all_score_staff_ids
    if invalid:
        available = ", ".join(_sort_numeric_strings(all_score_staff_ids)) or "nenhuma"
        requested = ", ".join(_sort_numeric_strings(invalid))
        raise ValueError(
            f"Pauta(s) inexistente(s): {requested}. "
            f"Pautas disponíveis neste arquivo: {available}."
        )

    # Remove estruturas auxiliares que podem preservar layout/partes antigas.
    _remove_layout_caches(score)

    # 1. Remove de fato as Parts/instrumentos não escolhidos.
    kept_part_map, _global_ids = _prune_parts_by_global_staffs(root, score, keep_set)

    # 2. Remove o conteúdo musical das pautas descartadas.
    for staff in list(score.findall("Staff")):
        sid = staff.get("id")
        if sid not in keep_set:
            score.remove(staff)

    # 3. Calcula compactação dos IDs restantes. Ex.: selecionar pauta 2 sozinha
    # vira id=1, mas preservando a Part/instrumento original da pauta 2.
    remaining_old_ids = _sort_numeric_strings(
        [s.get("id") for s in score.findall("Staff") if s.get("id")]
    )
    staff_id_map = {old: str(i + 1) for i, old in enumerate(remaining_old_ids)} if renumber else {}

    # 4. Remove/remapeia referências a tracks/staffIdx/staff antes de trocar os
    # IDs estruturais. Assim os cálculos ainda usam os IDs antigos.
    _clean_and_remap_staff_references(root, keep_set, staff_id_map=staff_id_map if renumber else None)

    # 5. Troca os IDs estruturais por último.
    if renumber:
        _renumber_score_staffs(score, staff_id_map)
        _renumber_kept_part_descriptors(kept_part_map, staff_id_map)

# ─────────────────────────────────────────────────────────────────────────────
#  EXPORTAÇÃO VIA MSCORE CLI
# ─────────────────────────────────────────────────────────────────────────────

def export_score(mscz_path, output_path, fmt, dpi=150, transparent=False, mscore_exe=None):
    exe = mscore_exe or find_mscore_executable()
    if not exe:
        raise FileNotFoundError(
            "Executável do MuseScore não encontrado.\n"
            "Informe o caminho em 'Executável mscore' ou instale o MuseScore 4."
        )

    cmd = [exe, "-f", "-o", output_path]
    if fmt == "png":
        cmd += ["-r", str(dpi)]
        if transparent:
            cmd += ["-T", "0"]
    cmd.append(mscz_path)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)

    if result.returncode != 0:
        raise RuntimeError(
            f"MuseScore retornou erro {result.returncode}:\n"
            f"stderr: {result.stderr.strip()}"
        )

    # MU4 às vezes gera "nome-1.svg" em vez de "nome.svg"
    if not os.path.exists(output_path):
        base, ext = os.path.splitext(output_path)
        alt = f"{base}-1{ext}"
        if os.path.exists(alt):
            os.rename(alt, output_path)
        else:
            # Procura qualquer arquivo gerado com prefixo semelhante
            out_dir = os.path.dirname(output_path) or "."
            stem = os.path.basename(base)
            for f in os.listdir(out_dir):
                if f.startswith(stem) and f.endswith(ext):
                    os.rename(os.path.join(out_dir, f), output_path)
                    break

    return output_path


# ─────────────────────────────────────────────────────────────────────────────
#  FLUXO PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_root(root):
    # ET.indent existe a partir do Python 3.9. Mantém compatibilidade com 3.8.
    if hasattr(ET, "indent"):
        ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")


def _write_temp_mscz(mscx_name, mscx_content, others):
    tmp_fd, tmp_mscz = tempfile.mkstemp(suffix=".mscz", prefix="ms_capture_")
    os.close(tmp_fd)
    write_mscz(tmp_mscz, mscx_name, mscx_content, others)
    return tmp_mscz


def run_capture(input_file, start_measure, end_measure,
                staves, fmt, dpi, transparent, output_path, mscore_exe=None):

    input_path = Path(input_file).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {input_file}")

    # ── Lê o arquivo ────────────────────────────────────────────────────────
    if input_path.suffix.lower() == ".mscz":
        mscx_content, mscx_name, others = read_mscz(str(input_path))
    elif input_path.suffix.lower() == ".mscx":
        mscx_content = input_path.read_text(encoding="utf-8")
        mscx_name = input_path.name
        others = {}
    else:
        raise ValueError(f"Formato não suportado: {input_path.suffix}")

    # Validação inicial sem modificar o XML original em memória.
    root0 = parse_mscx(mscx_content)
    total = count_measures(root0)
    if total == 0:
        raise ValueError("Não foi possível ler compassos. Verifique o arquivo.")

    s = max(1, start_measure)
    e = min(end_measure if end_measure is not None else total, total)
    if s > e:
        raise ValueError(f"Compasso inicial ({s}) maior que final ({e}).")

    # Se não há filtro de pauta, mantém o fluxo simples.
    # Se há filtro, a estratégia padrão agora é somente compactar/renumerar.
    # A antiga estratégia preserve_ids evitava o erro 1320 em alguns arquivos,
    # mas podia gerar exatamente o resultado errado: duas pautas, uma vazia.
    strategies = [("all", None)]
    if staves is not None:
        strategies = [("compact", True)]
        allow_legacy_fallback = os.environ.get("MS_CAPTURE_ALLOW_PRESERVE_IDS", "").strip() in ("1", "true", "True")
        if allow_legacy_fallback:
            strategies.append(("preserve_ids_legacy", False))

    last_error = None
    keep_temp = os.environ.get("MS_CAPTURE_KEEP_TEMP", "").strip() not in ("", "0", "false", "False")
    attempted_temps = []

    for strategy_name, renumber in strategies:
        tmp_mscz = None
        try:
            root = parse_mscx(mscx_content)
            crop_measures(root, s, e)
            if staves is not None:
                hide_staves(root, staves, renumber=renumber)

            new_mscx = _serialize_root(root)
            tmp_mscz = _write_temp_mscz(mscx_name, new_mscx, others)
            attempted_temps.append((strategy_name, tmp_mscz))

            # ── Define saída ────────────────────────────────────────────────
            if output_path is None:
                stem = input_path.stem
                out_dir = input_path.parent
                tag = f"c{s}-{e}"
                staff_tag = "all" if staves is None else "p" + "-".join(str(x) for x in staves)
                out = str(out_dir / f"{stem}_{tag}_{staff_tag}.{fmt}")
            else:
                out = output_path

            export_score(tmp_mscz, out, fmt, dpi, transparent, mscore_exe)

            if tmp_mscz and os.path.exists(tmp_mscz) and not keep_temp:
                os.remove(tmp_mscz)

            return out

        except Exception as ex:
            last_error = ex
            if tmp_mscz and os.path.exists(tmp_mscz) and not keep_temp:
                os.remove(tmp_mscz)
            # Em uso normal há uma única estratégia correta. Uma segunda tentativa
            # só ocorre se MS_CAPTURE_ALLOW_PRESERVE_IDS=1 estiver definido.
            continue

    msg = f"Falha ao exportar após {len(strategies)} tentativa(s). Último erro: {last_error}"
    if keep_temp and attempted_temps:
        msg += "\nArquivos temporários preservados por MS_CAPTURE_KEEP_TEMP=1:"
        for name, path in attempted_temps:
            msg += f"\n  - {name}: {path}"
    raise RuntimeError(msg)


# ─────────────────────────────────────────────────────────────────────────────
#  INTERFACE GRÁFICA (tkinter)
# ─────────────────────────────────────────────────────────────────────────────

def run_gui():
    try:
        import tkinter as tk
        from tkinter import ttk, filedialog, messagebox
    except ImportError:
        print("tkinter não disponível. Use: sudo apt install python3-tk")
        sys.exit(1)

    root_win = tk.Tk()
    root_win.title("ms_capture — Captura de Partitura")
    root_win.geometry("580x580")
    root_win.resizable(False, False)

    BG = "#1e1e2e"; BG2 = "#282a36"; FG = "#f8f8f2"
    ACC = "#7c3aed"; OK = "#50fa7b"; ERR = "#ff5555"; GRAY = "#6272a4"
    FONT = ("Segoe UI", 10) if platform.system() == "Windows" else ("Helvetica", 10)
    MONO = ("Consolas", 10) if platform.system() == "Windows" else ("Courier", 10)
    root_win.configure(bg=BG)

    var_file    = tk.StringVar()
    var_start   = tk.StringVar(value="1")
    var_end     = tk.StringVar(value="")
    var_fmt     = tk.StringVar(value="svg")
    var_dpi     = tk.StringVar(value="150")
    var_transp  = tk.BooleanVar(value=True)
    var_out     = tk.StringVar()
    var_staves  = tk.StringVar(value="all")
    var_mscore  = tk.StringVar(value=find_mscore_executable() or "")
    var_status  = tk.StringVar(value="Selecione um arquivo .mscz para começar.")
    var_total   = tk.StringVar(value="—")
    var_instru  = tk.StringVar(value="")
    status_color = [OK]

    def lbl(parent, text, **kw):
        return tk.Label(parent, text=text, bg=kw.pop("bg", BG2), fg=kw.pop("fg", GRAY),
                        font=FONT, **kw)

    def entry(parent, var, width=32):
        return tk.Entry(parent, textvariable=var, width=width,
                        bg="#44475a", fg=FG, insertbackground=FG,
                        relief="flat", font=MONO)

    def btn(parent, text, cmd, color=None):
        b = tk.Button(parent, text=text, command=cmd,
                      bg=color or "#44475a", fg="white" if color else FG,
                      relief="flat", font=FONT, cursor="hand2",
                      activebackground=color or "#555770")
        return b

    def on_file_select():
        path = filedialog.askopenfilename(
            title="Abrir partitura",
            filetypes=[("MuseScore", "*.mscz *.mscx"), ("Todos", "*.*")]
        )
        if not path:
            return
        var_file.set(path)
        try:
            mscx_content, _, _ = read_mscz(path) if path.lower().endswith(".mscz") \
                                  else (Path(path).read_text(encoding="utf-8"), path, {})
            r = parse_mscx(mscx_content)
            total = count_measures(r)
            names = get_instrument_names(r)
            var_total.set(str(total))
            var_end.set(str(total))
            var_instru.set("Instrumentos: " + ", ".join(names))
            var_status.set(f"✓ {Path(path).name}  •  {total} compassos  •  {len(names)} instrumento(s)")
            status_lbl.config(fg=OK)
        except Exception as ex:
            var_status.set(f"✗ Erro ao ler: {ex}")
            status_lbl.config(fg=ERR)

    def on_export():
        f = var_file.get().strip()
        if not f:
            messagebox.showwarning("Aviso", "Selecione um arquivo .mscz primeiro.")
            return
        try:
            s   = int(var_start.get())
            ev  = var_end.get().strip()
            e   = int(ev) if ev else None
            fmt = var_fmt.get()
            dpi = int(var_dpi.get())
            tr  = var_transp.get()
            out = var_out.get().strip() or None
            ms  = var_mscore.get().strip() or None
            sv  = var_staves.get().strip()
            staves = None
            if sv.lower() != "all" and sv:
                staves = [int(x.strip()) for x in sv.split(",")]

            var_status.set("⏳ Exportando…")
            status_lbl.config(fg="#f1fa8c")
            root_win.update()

            result = run_capture(f, s, e, staves, fmt, dpi, tr, out, ms)
            var_status.set(f"✓ Exportado: {result}")
            status_lbl.config(fg=OK)
        except Exception as ex:
            var_status.set(f"✗ Erro: {ex}")
            status_lbl.config(fg=ERR)

    # ── Layout ───────────────────────────────────────────────────────────────
    # Cabeçalho
    hdr = tk.Frame(root_win, bg=BG)
    hdr.pack(fill="x", padx=16, pady=(14, 2))
    tk.Label(hdr, text="📷", bg=BG, fg=FG, font=("Segoe UI", 22)).pack(side="left")
    tk.Label(hdr, text="  ms_capture", bg=BG, fg=FG,
             font=("Segoe UI" if platform.system()=="Windows" else "Helvetica", 15, "bold")).pack(side="left")
    tk.Label(hdr, text="  captura de trechos de partitura para SVG / PNG / PDF",
             bg=BG, fg=GRAY, font=FONT).pack(side="left", padx=4)

    tk.Frame(root_win, bg="#44475a", height=1).pack(fill="x", padx=16, pady=4)

    frm = tk.Frame(root_win, bg=BG2)
    frm.pack(fill="both", padx=16, pady=4)

    def row_frame(r):
        f = tk.Frame(frm, bg=BG2)
        f.grid(row=r, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        frm.columnconfigure(0, weight=1)
        return f

    # Arquivo
    rf0 = row_frame(0)
    lbl(rf0, "Arquivo:", bg=BG2, width=18, anchor="e").pack(side="left")
    entry(rf0, var_file, width=33).pack(side="left", padx=(4,3))
    btn(rf0, "…", on_file_select).pack(side="left")

    # Info instrumentos
    tk.Label(frm, textvariable=var_instru, bg=BG2, fg="#bd93f9",
             font=("Segoe UI" if platform.system()=="Windows" else "Helvetica", 9),
             anchor="w").grid(row=1, column=0, columnspan=2, sticky="w", padx=26, pady=0)

    # Compassos
    rf2 = row_frame(2)
    lbl(rf2, "Compassos:", bg=BG2, width=18, anchor="e").pack(side="left")
    entry(rf2, var_start, width=6).pack(side="left", padx=(4,3))
    lbl(rf2, "→", bg=BG2).pack(side="left", padx=2)
    entry(rf2, var_end, width=6).pack(side="left", padx=(2,8))
    lbl(rf2, "de", bg=BG2).pack(side="left")
    tk.Label(rf2, textvariable=var_total, bg=BG2, fg=OK,
             font=(FONT[0], FONT[1], "bold")).pack(side="left", padx=2)

    # Pautas
    rf3 = row_frame(3)
    lbl(rf3, "Pautas:", bg=BG2, width=18, anchor="e").pack(side="left")
    entry(rf3, var_staves, width=20).pack(side="left", padx=(4,8))
    lbl(rf3, "all  ou  1,2  (números separados por vírgula)", bg=BG2, fg=GRAY).pack(side="left")

    # Formato
    rf4 = row_frame(4)
    lbl(rf4, "Formato:", bg=BG2, width=18, anchor="e").pack(side="left")
    for fv in ("svg", "png", "pdf"):
        tk.Radiobutton(rf4, text=fv.upper(), variable=var_fmt, value=fv,
                       bg=BG2, fg=FG, selectcolor=ACC, activebackground=BG2,
                       font=FONT).pack(side="left", padx=5)
    lbl(rf4, "  DPI:", bg=BG2).pack(side="left")
    ttk.Combobox(rf4, textvariable=var_dpi, values=["96","150","300"],
                 width=5, state="readonly").pack(side="left", padx=4)
    tk.Checkbutton(rf4, text="Transparente", variable=var_transp,
                   bg=BG2, fg=FG, selectcolor=ACC, activebackground=BG2,
                   font=FONT).pack(side="left", padx=8)

    # Saída
    rf5 = row_frame(5)
    lbl(rf5, "Saída:", bg=BG2, width=18, anchor="e").pack(side="left")
    entry(rf5, var_out, width=30).pack(side="left", padx=(4,3))
    btn(rf5, "…", lambda: var_out.set(
        filedialog.asksaveasfilename(
            defaultextension=f".{var_fmt.get()}",
            filetypes=[("SVG","*.svg"),("PNG","*.png"),("PDF","*.pdf"),("Todos","*.*")]
        )
    )).pack(side="left")
    lbl(rf5, " (vazio = automático)", bg=BG2, fg=GRAY).pack(side="left")

    # Executável
    rf6 = row_frame(6)
    lbl(rf6, "mscore exe:", bg=BG2, width=18, anchor="e").pack(side="left")
    entry(rf6, var_mscore, width=30).pack(side="left", padx=(4,3))
    btn(rf6, "…", lambda: var_mscore.set(
        filedialog.askopenfilename(title="Localizar MuseScore4.exe")
    )).pack(side="left")

    tk.Frame(root_win, bg="#44475a", height=1).pack(fill="x", padx=16, pady=6)

    # Status
    status_lbl = tk.Label(root_win, textvariable=var_status, bg=BG, fg=OK,
                          font=("Segoe UI" if platform.system()=="Windows" else "Helvetica", 9),
                          wraplength=540, justify="left", anchor="w")
    status_lbl.pack(fill="x", padx=20, pady=2)

    # Botão principal
    btn(root_win, "📷  Exportar Trecho", on_export, color=ACC).pack(
        pady=(6, 16), ipadx=20, ipady=8
    )

    root_win.mainloop()


# ─────────────────────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Captura trechos de partitura MuseScore.")
    parser.add_argument("arquivo", nargs="?")
    parser.add_argument("-s", "--start",      type=int, default=1)
    parser.add_argument("-e", "--end",        type=int, default=None)
    parser.add_argument("-t", "--staves",     default="all")
    parser.add_argument("-f", "--format",     default="svg", choices=["svg","png","pdf"])
    parser.add_argument("-d", "--dpi",        type=int, default=150)
    parser.add_argument("-o", "--output",     default=None)
    parser.add_argument("--transparent",      action="store_true")
    parser.add_argument("--mscore-path",      default=None)
    parser.add_argument("--gui",              action="store_true")
    args = parser.parse_args()

    if args.gui or args.arquivo is None:
        run_gui()
        return

    staves = None
    if args.staves.strip().lower() != "all":
        staves = [int(x.strip()) for x in args.staves.split(",")]

    try:
        result = run_capture(
            args.arquivo, args.start, args.end, staves,
            args.format, args.dpi, args.transparent, args.output, args.mscore_path
        )
        print(f"✓ Exportado: {result}")
    except Exception as e:
        print(f"✗ Erro: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
