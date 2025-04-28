# Consumption Sensor Node

Este nodo IoT mide el consumo de energía eléctrica y la distancia de nivel, enviando los datos a AWS IoT Core vía MQTT.

## Sensores integrados
- **PZEM-004T**: Medición de tensión, corriente, potencia y energía consumida.
- **HC-SR04**: Medición de distancia (ultrasónico).

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

