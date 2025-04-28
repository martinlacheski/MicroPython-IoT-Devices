# Actuator Node

Este nodo IoT permite el control remoto de actuadores (bombas, válvulas, ventiladores, etc.) mediante comandos enviados a través de AWS IoT Core vía MQTT.

## Funcionalidades
- Recepción de comandos MQTT para activar o desactivar actuadores conectados.
- Gestión segura de conexión Wi-Fi y AWS IoT Core.

## Archivos principales
- `main.py`: Programa principal.
- `config.py`: Configuración de red y AWS.
- `wifi.dat`: Credenciales de Wi-Fi.
- `aws/`: Certificados para conexión segura.
- `lib/`: Librerías de red.

## Instrucciones básicas
1. Configurar Wi-Fi en `wifi.dat`.
2. Configurar conexión a AWS en `config.py` y colocar certificados en `aws/`.
3. Cargar todos los archivos al ESP32 y ejecutar.
