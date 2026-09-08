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

## Licencia

Este proyecto está distribuido bajo la licencia [MIT](LICENSE).
