#!/usr/bin/env python3
"""
Script para descargar todos los recibos/facturas en PDF desde la oficina virtual de Ista España.

Uso:
  python3 descargar_recibos.py -u tu_email@correo.com -p tu_contraseña
  python3 descargar_recibos.py -u tu_email@correo.com -p tu_contraseña --fecha-desde 01/01/2026
  python3 descargar_recibos.py -u tu_email@correo.com -p tu_contraseña --fecha-desde 2026-01-01 -o ./mis_facturas
"""

from __future__ import annotations

import argparse
from datetime import datetime
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

# Permite importar ista_client si se ejecuta desde el repo o directamente
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "custom_components", "ista")
    ),
)
sys.path.insert(
    0,
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "custom_components", "ista")
    ),
)

try:
    from ista_client import IstaAuthError, IstaClient, IstaConnectionError
except ImportError:
    # Definición mínima de excepciones si no estuviera disponible el módulo
    class IstaAuthError(Exception):
        pass

    class IstaConnectionError(Exception):
        pass


def parse_date_arg(date_str: Optional[str]) -> Optional[datetime]:
    """Parse flexible date strings (DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY)."""
    if not date_str:
        return None

    formats = [
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%Y/%m/%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue

    raise argparse.ArgumentTypeError(
        f"Formato de fecha inválido: '{date_str}'. Formatos admitidos: DD/MM/AAAA o AAAA-MM-DD"
    )


def sanitize_filename(name: str) -> str:
    """Sanitize string to be safe for filenames."""
    name = name.strip().lower()
    name = re.sub(r"[^\w\s-]", "", name)
    name = re.sub(r"[\s]+", "_", name)
    return name


def fetch_all_receipts(client: IstaClient, session: requests.Session) -> List[Dict[str, Any]]:
    """Fetch receipt entries from all available pages in the portal."""
    all_receipts: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    page = 1

    while True:
        url = (
            f"{client.BASE_URL}/GesCon/GestionFacturacion.do"
            f"?d-148657-p={page}&metodo=listadoRecibos"
        )
        try:
            r = session.get(url, timeout=30)
            r.raise_for_status()
        except requests.RequestException as err:
            print(f"  [!] Error al obtener la página {page} de recibos: {err}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table", {"id": "lista"})
        if not table:
            break

        rows = table.find_all("tr")[1:]  # skip header
        if not rows:
            break

        page_new_count = 0
        for tr in rows:
            cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
            if len(cells) < 3 or cells[0] == "No se han encontrado resultados":
                continue

            date_str = cells[0]
            equipment_type = cells[1]
            amount_str = cells[2]
            amount = client.parse_number(amount_str)

            pdf_link = ""
            receipt_id = ""
            link_elem = tr.find(
                "a", href=re.compile(r"duplicarReciboIndividualCalista")
            )
            if link_elem:
                href = link_elem.get("href", "")
                pdf_link = (
                    f"{client.BASE_URL}{href}"
                    if href.startswith("/")
                    else href
                )
                m = re.search(r"idRecibo=([^&]+)", href)
                if m:
                    receipt_id = m.group(1)

            if not receipt_id or receipt_id in seen_ids:
                continue

            seen_ids.add(receipt_id)
            page_new_count += 1

            # Parse datetime object for filtering
            receipt_dt = None
            try:
                receipt_dt = datetime.strptime(date_str, "%d/%m/%Y")
            except ValueError:
                pass

            all_receipts.append({
                "receipt_id": receipt_id,
                "date_str": date_str,
                "date_dt": receipt_dt,
                "type": equipment_type,
                "amount": amount,
                "amount_str": amount_str,
                "pdf_url": pdf_link,
            })

        # DisplayTag repeats previous page when reaching end of list
        if page_new_count == 0:
            break

        page += 1

    return all_receipts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Descarga todos los recibos y facturas en PDF desde oficina.ista.es",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Ejemplos de uso:
  python3 descargar_recibos.py -u mi_email@gmail.com -p "mi_password"
  python3 descargar_recibos.py -u mi_email@gmail.com -p "mi_password" --fecha-desde 01/01/2026
  python3 descargar_recibos.py -u mi_email@gmail.com -p "mi_password" -d 2025-06-01 -o ./facturas
""",
    )

    parser.add_argument(
        "-u",
        "--usuario",
        "--email",
        dest="username",
        required=True,
        help="Correo electrónico (usuario) de acceso al portal de Ista",
    )
    parser.add_argument(
        "-p",
        "--password",
        "--contrasena",
        dest="password",
        required=True,
        help="Contraseña de acceso a la oficina virtual",
    )
    parser.add_argument(
        "-d",
        "--fecha-desde",
        dest="fecha_desde",
        type=parse_date_arg,
        default=None,
        help="Fecha inicial a partir de la cual descargar (formato DD/MM/AAAA o AAAA-MM-DD). Si no se especifica, descarga todos los recibos.",
    )
    parser.add_argument(
        "-o",
        "--directorio",
        dest="output_dir",
        default="./facturas_ista",
        help="Directorio donde guardar los archivos PDF (por defecto: ./facturas_ista)",
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Volver a descargar los archivos aunque ya existan en la carpeta de destino.",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("  DESCARGA DE FACTURAS Y RECIBOS - ISTA ESPAÑA")
    print("=" * 60)
    print(f"Usuario: {args.username}")
    if args.fecha_desde:
        print(f"Filtro: Recibos desde {args.fecha_desde.strftime('%d/%m/%Y')}")
    else:
        print("Filtro: Todos los recibos históricos disponibles")
    print(f"Directorio de destino: {os.path.abspath(args.output_dir)}")
    print("-" * 60)

    # 1. Autenticación
    print("[1/3] Conectando y autenticando con la oficina virtual de Ista...")
    client = IstaClient(username=args.username, password=args.password)
    try:
        client.login()
    except IstaAuthError as err:
        print(f"\n[ERROR] Fallo de autenticación: {err}")
        sys.exit(1)
    except IstaConnectionError as err:
        print(f"\n[ERROR] Error de conexión: {err}")
        sys.exit(1)
    except Exception as err:
        print(f"\n[ERROR] Error inesperado al iniciar sesión: {err}")
        sys.exit(1)

    print("  -> Autenticación correcta.")

    # 2. Obtener lista completa de recibos
    print("[2/3] Buscando historial completo de facturas...")
    receipts = fetch_all_receipts(client, client.session)
    print(f"  -> Se han encontrado {len(receipts)} recibo(s) en total en tu cuenta.")

    # Aplicar filtro de fecha si se especificó
    filtered_receipts: List[Dict[str, Any]] = []
    for r in receipts:
        if args.fecha_desde and r["date_dt"]:
            if r["date_dt"] < args.fecha_desde:
                continue
        filtered_receipts.append(r)

    if args.fecha_desde:
        print(
            f"  -> {len(filtered_receipts)} recibo(s) coinciden con el filtro desde {args.fecha_desde.strftime('%d/%m/%Y')}."
        )

    if not filtered_receipts:
        print("\nNo se encontraron recibos que cumplan el criterio de fecha.")
        return

    # 3. Descarga de archivos
    print(f"\n[3/3] Descargando {len(filtered_receipts)} archivo(s) PDF...")
    os.makedirs(args.output_dir, exist_ok=True)

    descargados = 0
    omitidos = 0
    errores = 0
    suma_total = 0.0

    for i, r in enumerate(filtered_receipts, start=1):
        dt_str = (
            r["date_dt"].strftime("%Y-%m-%d")
            if r["date_dt"]
            else r["date_str"].replace("/", "-")
        )
        safe_type = sanitize_filename(r["type"])
        amt_str = f"{r['amount']:.2f}".replace(".", "_") if r["amount"] is not None else "0_00"
        safe_id = sanitize_filename(r["receipt_id"])[:8]

        filename = f"factura_ista_{dt_str}_{safe_type}_{amt_str}eur_{safe_id}.pdf"
        target_path = os.path.join(args.output_dir, filename)

        if r["amount"]:
            suma_total += r["amount"]

        # Comprobar si ya existe
        if os.path.exists(target_path) and not args.forzar:
            print(f"  [{i}/{len(filtered_receipts)}] Omitido (ya existe): {filename}")
            omitidos += 1
            continue

        print(
            f"  [{i}/{len(filtered_receipts)}] Descargando {r['date_str']} - {r['type']} ({r['amount_str']} €)... ",
            end="",
            flush=True,
        )

        try:
            pdf_bytes = client.download_receipt_pdf(r["receipt_id"])
            with open(target_path, "wb") as f:
                f.write(pdf_bytes)
            print("OK")
            descargados += 1
        except Exception as err:
            print(f"ERROR ({err})")
            errores += 1

    print("\n" + "=" * 60)
    print("  RESUMEN DE DESCARGA")
    print("=" * 60)
    print(f"Total recibos procesados:  {len(filtered_receipts)}")
    print(f"Descargados correctamente: {descargados}")
    print(f"Omitidos (ya existían):    {omitidos}")
    if errores > 0:
        print(f"Fallos en la descarga:     {errores}")
    print(f"Suma total importes:       {suma_total:.2f} €")
    print(f"Carpeta de destino:        {os.path.abspath(args.output_dir)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
