# Environmental Sensor Node

Este nodo IoT mide parámetros ambientales como temperatura, humedad relativa, presión atmosférica, luminosidad y concentración de CO₂, enviando los datos a AWS IoT Core vía MQTT.

## Sensores integrados
- **BME280**: Temperatura, Humedad, Presión atmosférica
- **BH1750**: Intensidad de luz (lux)
- **MH-Z19**: Concentración de CO₂ (ppm)

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
