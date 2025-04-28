# Nutrient Solution Sensor Node

Este nodo IoT mide parámetros de calidad de una solución nutritiva (CE, pH y temperatura), enviando los datos a AWS IoT Core vía MQTT.

## Sensores integrados
- **TDS Sensor**: Conductividad eléctrica (CE).
- **pH Sensor**: Nivel de acidez o alcalinidad.
- **DS18B20**: Temperatura de la solución.

## Archivos principales
- `main.py`: Programa principal.
- `config.py`: Configuración de red y AWS.
- `wifi.dat`: Credenciales de Wi-Fi.
- `aws/`: Certificados para conexión segura.
- `lib/`: Librerías de sensores y de red.

## Instrucciones básicas
1. Configurar Wi-Fi en `wifi.dat`.
2. Configurar conexión a AWS en `config.py` y colocar certificados en `aws/`.
3. Cargar todos los archivos al ESP32 y ejecutar.
