"""Client for interacting with the Ista Spain web portal (oficina.ista.es)."""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
import requests
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)


class IstaAuthError(Exception):
    """Exception raised when authentication fails."""


class IstaConnectionError(Exception):
    """Exception raised when a network or HTTP error occurs."""


class IstaClient:
    """API client to scrape and fetch data from oficina.ista.es."""

    BASE_URL = "https://oficina.ista.es"
    LOGIN_URL = "https://oficina.ista.es/GesCon/MainPageAbo.do"

    def __init__(self, username: str, password: str, session: Optional[requests.Session] = None) -> None:
        """Initialize the client with credentials."""
        self.username = username
        self.password = password
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
            ),
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        })

    def login(self) -> bool:
        """Authenticate via Keycloak OpenID Connect form."""
        try:
            r = self.session.get(self.LOGIN_URL, timeout=30)
        except requests.RequestException as err:
            raise IstaConnectionError(f"Error connecting to Ista portal: {err}") from err

        if "login.ista.com" not in r.url:
            if "GesCon/GestionOficinaVirtual.do" in r.url:
                return True

        soup = BeautifulSoup(r.text, "html.parser")
        form = soup.find("form")
        if not form:
            raise IstaConnectionError("Login form not found on portal landing page")

        action = form.get("action")
        if not action:
            raise IstaConnectionError("No action URL found on login form")

        login_data = {
            "username": self.username,
            "password": self.password,
        }

        try:
            r_post = self.session.post(action, data=login_data, timeout=30)
        except requests.RequestException as err:
            raise IstaConnectionError(f"Error submitting login form: {err}") from err

        lower_text = r_post.text.lower()
        if (
            "invalid username or password" in lower_text
            or "credenciales no son correctas" in lower_text
            or "usuario o contraseña incorrectos" in lower_text
        ):
            raise IstaAuthError("Usuario o contraseña incorrectos.")

        if "login.ista.com" in r_post.url:
            raise IstaAuthError("Error de autenticación en Keycloak (credenciales no válidas).")

        return True

    @staticmethod
    def parse_number(val_str: Optional[str]) -> Optional[float]:
        """Parse float from Spanish formatted strings, stripping units."""
        if not val_str:
            return None
        # Extract number with optional negative sign and comma/dot decimal separator
        m = re.search(r"[-+]?\d+(?:[.,]\d+)?", val_str.strip())
        if m:
            try:
                return float(m.group(0).replace(",", "."))
            except ValueError:
                return None
        return None

    def fetch_data(self) -> Dict[str, Any]:
        """Fetch all data: account, hot water readings, heating readings, and invoices."""
        self.login()

        data: Dict[str, Any] = {
            "account": {},
            "hot_water": {},
            "heating": {},
            "receipts": [],
        }

        # 1. Main Page (Account info & recent receipts)
        try:
            r_main = self.session.get(
                f"{self.BASE_URL}/GesCon/GestionOficinaVirtual.do?metodo=loginAbonado",
                timeout=30,
            )
        except requests.RequestException as err:
            raise IstaConnectionError(f"Error loading main office page: {err}") from err

        soup_main = BeautifulSoup(r_main.text, "html.parser")

        # Account info from header tables
        tables = soup_main.find_all("table")
        for table in tables:
            for tr in table.find_all("tr"):
                cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
                if len(cells) >= 4:
                    if "Nombre" in cells[0]:
                        data["account"]["name"] = cells[1]
                    if "Nº abonado" in cells[0]:
                        data["account"]["subscriber_number"] = cells[1]
                    if "Email" in cells[2]:
                        data["account"]["email"] = cells[3]

        # Receipts from main page table#lista
        recibos_table = soup_main.find("table", {"id": "lista"})
        receipts: List[Dict[str, Any]] = []
        if recibos_table:
            for tr in recibos_table.find_all("tr")[1:]:
                cells = [c.get_text(strip=True) for c in tr.find_all(["th", "td"])]
                if len(cells) >= 3 and cells[0] != "No se han encontrado resultados":
                    date_str = cells[0]
                    equipment_type = cells[1]
                    amount_str = cells[2]
                    amount = self.parse_number(amount_str)

                    pdf_link = ""
                    receipt_id = ""
                    link_elem = tr.find("a", href=re.compile(r"duplicarReciboIndividualCalista"))
                    if link_elem:
                        href = link_elem.get("href", "")
                        pdf_link = f"{self.BASE_URL}{href}" if href.startswith("/") else href
                        m = re.search(r"idRecibo=([^&]+)", href)
                        if m:
                            receipt_id = m.group(1)

                    receipts.append({
                        "date": date_str,
                        "type": equipment_type,
                        "amount": amount,
                        "pdf_url": pdf_link,
                        "receipt_id": receipt_id,
                    })
        data["receipts"] = receipts

        # Find latest receipts per equipment
        for rec in receipts:
            rec_type = rec["type"].lower()
            if "agua" in rec_type and "latest_receipt" not in data["hot_water"]:
                data["hot_water"]["latest_receipt"] = rec
            elif "optosonic" in rec_type and "latest_receipt" not in data["heating"]:
                data["heating"]["latest_receipt"] = rec

        # 2. Radio readings (Daily cumulative readings)
        try:
            r_radio = self.session.get(
                f"{self.BASE_URL}/GesCon/GestionFincas.do?metodo=preCargaLecturasRadio",
                timeout=30,
            )
        except requests.RequestException as err:
            _LOGGER.warning("Could not fetch radio readings: %s", err)
            r_radio = None

        if r_radio and r_radio.status_code == 200:
            soup_radio = BeautifulSoup(r_radio.text, "html.parser")
            radio_table = soup_radio.find("table", {"id": "listaLecturasRadio"}) or soup_radio.find(
                "table", {"class": "recibos"}
            )
            if radio_table:
                header_row = radio_table.find("tr")
                if header_row:
                    headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
                    date_cols = headers[5:] if len(headers) > 5 else []
                    for tr in radio_table.find_all("tr")[1:]:
                        cells = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                        if len(cells) > 4:
                            eq_type = cells[3]
                            serial = cells[2]
                            unit = cells[4]
                            values = cells[5:]

                            readings_history: Dict[str, Optional[float]] = {}
                            latest_reading: Optional[float] = None
                            latest_reading_date: Optional[str] = None
                            for d, val_s in zip(date_cols, values):
                                val_f = self.parse_number(val_s)
                                readings_history[d] = val_f
                                if latest_reading is None and val_f is not None:
                                    latest_reading = val_f
                                    latest_reading_date = d

                            target = (
                                data["hot_water"]
                                if "agua" in eq_type.lower()
                                else data["heating"]
                            )
                            target["serial"] = serial
                            target["unit"] = unit
                            target["current_reading"] = latest_reading
                            target["current_reading_date"] = latest_reading_date
                            target["daily_readings"] = readings_history

        # 3. Monthly consumptions (Billed periods)
        # 4657: Radio agua caliente, 4790: Optosonic
        equipment_map = [("4657", "hot_water"), ("4790", "heating")]
        for code, key in equipment_map:
            try:
                r_c = self.session.post(
                    f"{self.BASE_URL}/GesCon/GestionLecturasBusqueda.do?metodo=buscarLecturas&idTipoEquipo={code}",
                    timeout=30,
                )
            except requests.RequestException as err:
                _LOGGER.warning("Could not fetch monthly consumptions for code %s: %s", code, err)
                continue

            if r_c.status_code == 200:
                soup_c = BeautifulSoup(r_c.text, "html.parser")
                c_table = soup_c.find("table", {"id": "lista"})
                if c_table:
                    monthly_rows: List[Dict[str, Any]] = []
                    for tr in c_table.find_all("tr")[1:]:
                        cells = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                        if len(cells) >= 7 and cells[0] != "No se han encontrado resultados":
                            prev_reading = self.parse_number(cells[4])
                            curr_reading = self.parse_number(cells[5])
                            consumption = self.parse_number(cells[6])
                            monthly_rows.append({
                                "serial": cells[0],
                                "equipment": cells[1],
                                "date": cells[2],
                                "incidence": cells[3],
                                "previous_reading": prev_reading,
                                "current_reading": curr_reading,
                                "consumption": consumption,
                            })
                    data[key]["monthly_history"] = monthly_rows
                    if monthly_rows:
                        latest = monthly_rows[0]
                        data[key]["last_billed_consumption"] = latest["consumption"]
                        data[key]["last_billed_reading"] = latest["current_reading"]
                        data[key]["previous_billed_reading"] = latest["previous_reading"]
                        data[key]["last_billed_date"] = latest["date"]

                        # Calculate estimated unbilled consumption if current meter reading is available
                        current_r = data[key].get("current_reading")
                        billed_r = latest.get("current_reading")
                        if current_r is not None and billed_r is not None:
                            unbilled = current_r - billed_r
                            data[key]["unbilled_consumption"] = round(unbilled, 3)

        return data
