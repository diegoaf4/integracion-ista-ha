# Integración Ista para Home Assistant (HACS)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/diegoaf4/integracion-ista-ha?color=blue)](https://github.com/diegoaf4/integracion-ista-ha/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Integración personalizada para **Home Assistant** que conecta con la **Oficina Virtual de Ista España** ([oficina.ista.es](https://oficina.ista.es/GesCon/MainPageAbo.do)) para monitorizar las lecturas de telemedida por radio, los consumos mensuales y los importes de tus facturas y recibos.

---

## Características

- 💧 **Agua Caliente Sanitaria**:
  - Lectura acumulada actual por radiofrecuencia (en **m³**), compatible con el panel de **Agua** del Dashboard de Energía de Home Assistant (`device_class: water`, `state_class: total_increasing`).
  - Último consumo facturado (en **m³**).
  - Consumo no facturado estimado desde la última factura emitida (en **m³**).
  - Importe de la última factura de agua caliente (en **€**) con enlace directo de descarga del PDF.
- 🔥 **Calefacción (Optosonic / Repartidores)**:
  - Lectura acumulada actual por radiofrecuencia (en **kWh**), compatible con el Dashboard de **Energía** de Home Assistant (`device_class: energy`, `state_class: total_increasing`).
  - Último consumo facturado (en **kWh**).
  - Consumo no facturado estimado desde la última factura emitida (en **kWh**).
  - Importe de la última factura de calefacción (en **€**) con enlace directo de descarga del PDF.
- 🧾 **Facturación y Recibos**:
  - Sensor global de última factura emitida con atributos detallados: fecha, importe, equipo y URL directa para descargar el recibo en PDF.
- ⚙️ **Configuración sencilla mediante interfaz gráfica (UI)**:
  - Pide únicamente tu **correo electrónico (email)** y tu **contraseña**.
  - Soporta ajuste de intervalo de actualización (por defecto cada 6 horas).
  - Admite reautenticación automática si cambias de contraseña.

---

## Dispositivos y Entidades Creadas

La integración organiza las entidades en dispositivos independientes:

| Dispositivo | Sensor | Entidad sugerida | Unidad | Clase |
|---|---|---|---|---|
| **Ista Contador Agua Caliente** | Lectura Actual | `sensor.ista_agua_caliente_lectura_actual` | `m³` | `water` (`total_increasing`) |
| | Último Consumo Facturado | `sensor.ista_agua_caliente_ultimo_consumo` | `m³` | `water` |
| | Consumo No Facturado | `sensor.ista_agua_caliente_consumo_no_facturado` | `m³` | `water` |
| | Última Factura | `sensor.ista_agua_caliente_ultima_factura` | `€` | `monetary` |
| **Ista Contador Calefacción** | Lectura Actual | `sensor.ista_calefaccion_lectura_actual` | `kWh` | `energy` (`total_increasing`) |
| | Último Consumo Facturado | `sensor.ista_calefaccion_ultimo_consumo` | `kWh` | `energy` |
| | Consumo No Facturado | `sensor.ista_calefaccion_consumo_no_facturado` | `kWh` | `energy` |
| | Última Factura | `sensor.ista_calefaccion_ultima_factura` | `€` | `monetary` |
| **Ista Cuenta (Abonado)** | Última Factura General | `sensor.ista_ultima_factura` | `€` | `monetary` |

---

## Instalación

### Opción 1: A través de HACS (Recomendada)

1. Abre **HACS** en tu Home Assistant.
2. Pulsa en los tres puntos de la esquina superior derecha y selecciona **Repositorios personalizados** (*Custom repositories*).
3. Añade la URL de este repositorio:
   ```
   https://github.com/diegoaf4/integracion-ista-ha
   ```
4. Selecciona la categoría **Integración** (*Integration*) y haz clic en **Añadir**.
5. Busca **Ista España** en HACS y pulsa **Descargar**.
6. **Reinicia Home Assistant**.

### Opción 2: Instalación Manual

1. Descarga el contenido de este repositorio.
2. Copia la carpeta `custom_components/ista` dentro del directorio `custom_components` de tu instalación de Home Assistant:
   ```
   /config/custom_components/ista/
   ```
3. **Reinicia Home Assistant**.

---

## Configuración

1. En Home Assistant, dirígete a **Ajustes** -> **Dispositivos y Servicios**.
2. Haz clic en **Añadir Integración** (botón azul en la esquina inferior derecha).
3. Busca **Ista**.
4. Rellena el formulario con tus credenciales de la oficina virtual:
   - **Correo electrónico (Email)**: Tu email de acceso a [oficina.ista.es](https://oficina.ista.es).
   - **Contraseña**: Tu clave de acceso.
   - **Intervalo de actualización**: Frecuencia en horas (por defecto: `6` horas).
5. Pulsa **Enviar**. La integración comprobará las credenciales y creará automáticamente los dispositivos y sensores.

---

## Integración en el Panel de Energía de Home Assistant

Los sensores de lectura acumulada están listos para ser utilizados directamente en el panel nativo de Energía de Home Assistant:

### Consumo de Agua:
1. Ve a **Ajustes** -> **Paneles de control** -> **Energía**.
2. En la sección **Consumo de agua**, pulsa en **Añadir fuente de agua**.
3. Selecciona: `sensor.ista_agua_caliente_lectura_actual`.

### Consumo de Calefacción / Gas / Electricidad:
1. En la misma sección de **Energía**, puedes añadir `sensor.ista_calefaccion_lectura_actual` como consumo de red eléctrica individual o en la sección de gas si utilizas conversión.

---

## Tarjeta Lovelace de Ejemplo

Puedes crear una tarjeta visual en tu panel de control con el siguiente código YAML:

```yaml
type: entities
title: Consumos y Facturas Ista
show_header_toggle: false
entities:
  - type: section
    label: Agua Caliente
  - entity: sensor.ista_agua_caliente_lectura_actual
    name: Lectura Contador
  - entity: sensor.ista_agua_caliente_consumo_no_facturado
    name: Consumo en curso (no facturado)
  - entity: sensor.ista_agua_caliente_ultimo_consumo
    name: Último mes facturado
  - entity: sensor.ista_agua_caliente_ultima_factura
    name: Importe último recibo
  - type: section
    label: Calefacción
  - entity: sensor.ista_calefaccion_lectura_actual
    name: Lectura Contador
  - entity: sensor.ista_calefaccion_consumo_no_facturado
    name: Consumo en curso (no facturado)
  - entity: sensor.ista_calefaccion_ultimo_consumo
    name: Último mes facturado
  - entity: sensor.ista_calefaccion_ultima_factura
    name: Importe último recibo
```

---

## Descarga Automática de Facturas y Automatizaciones (Email / FTP)

La integración incluye un sistema de detección y descarga de facturas nuevas:

1. Cuando Ista emite un nuevo recibo, la integración descarga automáticamente el PDF a la carpeta configurada (por defecto: `/config/www/ista_facturas/`).
2. Se dispara de forma nativa el evento **`ista_new_invoice`** en Home Assistant con toda la información necesaria:
   - `file_path`: Ruta local al archivo PDF descargado (ej. `/config/www/ista_facturas/factura_ista_10-08-2026_agua_caliente_N5p2.pdf`).
   - `file_name`: Nombre del archivo.
   - `url_path`: Enlace web local (accesible en `/local/ista_facturas/...` para visualización en el navegador).
   - `amount`: Importe en euros.
   - `type`: Tipo de factura (`Agua caliente` u `Optosonic`).
   - `date`: Fecha de la factura.

> [!TIP]
> Puedes configurar la carpeta de destino o desactivar la descarga automática desde **Ajustes** -> **Dispositivos y Servicios** -> **Ista** -> **Configurar / Opciones**.

### Ejemplo 1: Enviar la nueva factura por Correo Electrónico (Email / SMTP)

Utilizando el servicio de notificación por correo de Home Assistant ([SMTP](https://www.home-assistant.io/integrations/smtp/)):

```yaml
alias: "Ista: Enviar nueva factura por Email"
description: "Envía el PDF de la factura recién emitida por correo electrónico"
trigger:
  - platform: event
    event_type: ista_new_invoice
action:
  - service: notify.notificaciones_correo # Reemplaza por tu entidad notify SMTP
    data:
      title: "Nueva factura Ista: {{ trigger.event.data.type }} ({{ trigger.event.data.amount }} €)"
      message: >
        Hola, se ha recibido una nueva factura de Ista.
        - Concepto: {{ trigger.event.data.type }}
        - Fecha: {{ trigger.event.data.date }}
        - Importe: {{ trigger.event.data.amount }} €
        Se adjunta el PDF correspondiente.
      data:
        images:
          - "{{ trigger.event.data.file_path }}"
mode: single
```

---

### Ejemplo 2: Subir la nueva factura a un Servidor FTP

Puedes subir automáticamente el archivo descargado a tu servidor FTP o NAS ejecutando un comando seguro mediante [`shell_command`](https://www.home-assistant.io/integrations/shell_command/):

1. En tu `configuration.yaml`, añade el comando curl para subida FTP:
```yaml
shell_command:
  subir_factura_ftp: 'curl -T "{{ archivo }}" "ftp://USUARIO:PASSWORD@SERVIDOR_FTP/facturas/{{ nombre }}"'
```
2. Crea la automatización en Home Assistant:
```yaml
alias: "Ista: Subir nueva factura a FTP"
description: "Sube el PDF de la nueva factura a un servidor FTP"
trigger:
  - platform: event
    event_type: ista_new_invoice
action:
  - service: shell_command.subir_factura_ftp
    data:
      archivo: "{{ trigger.event.data.file_path }}"
      nombre: "{{ trigger.event.data.file_name }}"
mode: single
```

---

### Ejemplo 3: Enviar la factura por Telegram

Si usas el bot de Telegram en Home Assistant:

```yaml
alias: "Ista: Enviar factura por Telegram"
trigger:
  - platform: event
    event_type: ista_new_invoice
action:
  - service: telegram_bot.send_document
    data:
      file: "{{ trigger.event.data.file_path }}"
      caption: "📄 Factura Ista de {{ trigger.event.data.type }}: {{ trigger.event.data.amount }} € ({{ trigger.event.data.date }})"
mode: single
```

---

### Servicio bajo demanda: `ista.download_receipt`

También dispones de una acción/servicio en Home Assistant para descargar cualquier factura en cualquier momento:

- **Servicio**: `ista.download_receipt`
- **Parámetros**:
  - `receipt_id` (opcional): ID del recibo. Si no se especifica, descarga la última factura emitida.
  - `target_path` (opcional): Ruta absoluta de destino del PDF.

---

## Script CLI para Descarga Masiva de Facturas (`descargar_recibos.py`)

Se incluye un script independiente en la raíz del repositorio para descargar el histórico de facturas en PDF desde la línea de comandos:

```bash
# Descargar TODOS los recibos históricos de la cuenta
python3 descargar_recibos.py -u mi_email@gmail.com -p "mi_contraseña"

# Descargar recibos a partir de una fecha concreta (opcional)
python3 descargar_recibos.py -u mi_email@gmail.com -p "mi_contraseña" --fecha-desde 01/01/2026

# Especificar carpeta de destino personalizada
python3 descargar_recibos.py -u mi_email@gmail.com -p "mi_contraseña" -d 2025-06-01 -o /ruta/mis_facturas
```

### Argumentos del script:
- `-u`, `--usuario`, `--email` (obligatorio): Correo electrónico de acceso a la oficina virtual.
- `-p`, `--password` (obligatorio): Contraseña de acceso.
- `-d`, `--fecha-desde` (opcional): Fecha inicial en formato `DD/MM/AAAA` o `AAAA-MM-DD`. Si se omite, se descargan **todas** las facturas históricas disponibles en tu cuenta (ej. 79 recibos).
- `-o`, `--directorio` (opcional): Directorio donde guardar los archivos PDF (por defecto: `./facturas_ista`).
- `--forzar` (opcional): Vuelve a descargar recibos aunque ya existan en la carpeta de destino.

---

## Licencia

Este proyecto está distribuido bajo la licencia [MIT](LICENSE).
