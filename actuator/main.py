from machine import Pin, Timer, reset
from lib.wifi_manager import WifiManager
from lib.robust import MQTTClient
import config
import ntptime
import ssl
import time
import uos
import gc
import sys
import json

# Configuración inicial
CONFIG_FILE = "interval.conf"
WIFI_FILE = "wifi.dat"
TIMEZONE_FILE = "timezone.conf"
DEFAULT_INTERVAL = 5
sensor_interval = DEFAULT_INTERVAL
sensor_data = {}  # Diccionario para datos de sensores
wm = WifiManager()

# Variables globales
wlan = None
wifi_connected = False
last_led_toggle = time.ticks_ms()
led_state = False
mqtt_client = None
last_wifi_check = 0
WIFI_CHECK_INTERVAL = 10000  # 10 segundos

# Configurar botón BOOT (GPIO0) con pull-up
boot_button = Pin(0, Pin.IN, Pin.PULL_UP)
led = Pin(2, Pin.OUT) # LED azul en GPIO2 (común en ESP32)

# Inicialización de sensores
print("Inicializando sensores")

# relay_water
try:
    # Configuración de pines (1 = Apagado, 0 = Encendido)
    # Sistema principal
    relay_water = Pin(19, Pin.OUT, value=1)     # Bomba de agua
    relay_aerator = Pin(21, Pin.OUT, value=1)   # Aireador
    relay_vent = Pin(22, Pin.OUT, value=1)      # Ventilación
    relay_light = Pin(23, Pin.OUT, value=1)     # Iluminación

    # Control de pH y nutrientes
    relay_ph_plus = Pin(32, Pin.OUT, value=1)   # pH+
    relay_ph_minus = Pin(33, Pin.OUT, value=1)  # pH-
    relay_nutri_1 = Pin(25, Pin.OUT, value=1)    # Nutriente 1
    relay_nutri_2 = Pin(26, Pin.OUT, value=1)    # Nutriente 2
    relay_nutri_3 = Pin(27, Pin.OUT, value=1)    # Nutriente 3
    relay_nutri_4 = Pin(14, Pin.OUT, value=1)    # Nutriente 4
    
        # --- Variables globales para control de relays ---
    active_relays = {}  # Formato: {"relay_name": end_timestamp}
    relay_pins = {
        "relay_water": relay_water,
        "relay_aerator": relay_aerator,
        "relay_vent": relay_vent,
        "relay_light": relay_light,
        "relay_ph_plus": relay_ph_plus,
        "relay_ph_minus": relay_ph_minus,
        "relay_nutri_1": relay_nutri_1,
        "relay_nutri_2": relay_nutri_2,
        "relay_nutri_3": relay_nutri_3,
        "relay_nutri_4": relay_nutri_4
    }
    
    print("Relays inicializados correctamente")
except Exception as e:
    print("Error inicializando relays:", e)
 
# Variables globales para manejar el estado de relays y bloqueos
relay_locks = {name: False for name in relay_pins.keys()}  # Bloqueo por relay
last_relay_operations = {name: 0 for name in relay_pins.keys()}  # Tiempo última operación

# Liberamos la memoria
gc.collect()

# Método para encender y apagar relays cuando expire su tiempo
def check_active_relays():
    global active_relays
    
    current_time = time.ticks_ms()
    changed = False
    relays_to_remove = []
    
    for relay_name, end_time in active_relays.items():
        if relay_locks[relay_name]:  # Si este relay está siendo operado
            continue
            
        if time.ticks_diff(current_time, end_time) >= 0:
            relay_locks[relay_name] = True  # Bloquear este relay específico
            try:
                if relay_pins[relay_name].value() == 0:  # Solo si está encendido
                    # Verificar tiempo mínimo entre operaciones
                    if time.ticks_diff(current_time, last_relay_operations[relay_name]) < 1000:
                        continue
                        
                    relay_pins[relay_name].value(1)
                    changed = True
                    relays_to_remove.append(relay_name)
                    last_relay_operations[relay_name] = current_time
                    
                    response = {
                        "actuator_code": config.ACTUATOR_CODE,
                        "status": "COMPLETED",
                        "relay": relay_name,
                        "command": "OFF",
                        "timestamp": current_time
                    }
                    mqtt_client.publish(config.AWS_TOPIC_SUB, json.dumps(response), qos=0)
            finally:
                relay_locks[relay_name] = False  # Liberar siempre el bloqueo
    
    for relay_name in relays_to_remove:
        active_relays.pop(relay_name, None)
    
    if changed:
        leer_sensores()
        
# Liberamos la memoria
gc.collect()
    
# Método para conectar Wi-Fi con mejor manejo de errores
def connect_wifi():
    global wifi_connected
    try:
        if not wm.is_connected():
            print("Intentando conectar red Wi-Fi...")
            wlan = wm.connect()
            if wm.is_connected():
                wifi_connected = True
                led.on()
                return True  
        wifi_connected = False
        led.off()
        return False
    except Exception as e:
        print("Error en la conexión de Wi-Fi:", e)
        wifi_connected = False
        led.off()
        return False

# Método para verificar estado del WiFi
def check_wifi_connection():
    
    global wifi_connected, last_wifi_check
    current_time = time.ticks_ms()
    
    if time.ticks_diff(current_time, last_wifi_check) > WIFI_CHECK_INTERVAL:
        last_wifi_check = current_time
        
        if not wm.is_connected():
            print("Wi-Fi desconectado. Intentando reconectar...")
            if connect_wifi():
                wifi_connected = True
                return True
            else:
                wifi_connected = False
                return False
        
        wifi_connected = True
    return wifi_connected

# Método para sincronizar tiempo con NTP
def sync_time(max_retries=5):
    for i in range(max_retries):
        try:
            print(f"Intentando sincronizar hora (intento {i+1}/{max_retries})...")
            ntptime.host = "time.google.com"  # Servidor alternativo
            ntptime.settime()
            print("Hora sincronizada:", time.localtime())
            return True
        except OSError as e:
            print("Error sincronizando hora:", e)
            time.sleep(2)
    print("Error: No se pudo sincronizar la hora después de", max_retries, "intentos")
    return False

# Carga de certificados
try:
    print("Cargando certificados...")
    with open("aws/client.key", "rb") as f:
        CLIENT_KEY = f.read()
    with open("aws/client.crt", "rb") as f:
        CLIENT_CRT = f.read()
    with open("aws/root.crt", "rb") as f:
        ROOT_CRT = f.read()
    print("Certificados cargados correctamente")
except Exception as e:
    print("Error cargando certificados:", e)
    raise

#Leer la zona horaria desde el archivo de configuración
#TIMEZONE_FILE = "timezone.conf"
try:
    with open(TIMEZONE_FILE, 'r') as f:
        TIMEZONE = f.read().strip()
        print("Zona horaria configurada:", TIMEZONE)
except Exception as e:
    print("Error leyendo zona horaria:", e)
    raise

# Liberamos la memoria
gc.collect()

# Configuración de conexión MQTT
try:
    print("Configurando SSL...")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(CLIENT_CRT, CLIENT_KEY)
    context.load_verify_locations(cadata=ROOT_CRT)
    print("SSL configurado correctamente")
except Exception as e:
    print("Error configurando SSL:", e)
    raise

# Creación de cliente MQTT
try:
    print("Creando cliente MQTT...")
    mqtt_client = MQTTClient(
        client_id=config.AWS_CLIENT_ID,
        server=config.AWS_ENDPOINT,
        port=8883,
        keepalive=5000,
        ssl=context,
    )
    print("Cliente MQTT creado")
except Exception as e:
    print("Error creando cliente MQTT:", e)
    raise

# Callback para mensajes entrantes (Seteo de nuevo intervalo)
def subscription_cb(topic, message):
    print("\nMensaje recibido:")
    print("Tópico:", topic.decode("utf-8"))
    print("Mensaje:", message.decode("utf-8"))
    
    try:
        msg = json.loads(message.decode("utf-8"))
        
        # Verificar si es para este dispositivo
        if msg.get("actuator_code") != config.ACTUATOR_CODE:
            return
        
        # Comando para lectura inmediata
        if msg.get("command") == "read_now":
            print("Comando de lectura inmediata recibido")
            
            # Enviar confirmación
            response = {
                "actuator_code": config.ACTUATOR_CODE,
                "command": "read_now_ack",
                "status": "received"
            }
            mqtt_client.publish(config.AWS_TOPIC_SUB, json.dumps(response), qos=0)
            print("Confirmación de lectura enviada al servidor")
            
            # Ejecutar lectura inmediata
            leer_sensores()
            
        # Comando para lectura inmediata
        if msg.get("command") == "read_now_ack":
            pass

        # Comandos de relay
        if msg.get("command") and msg.get("relay"):
            handle_relay_command(msg)

        # Cambio de intervalo (mantén tu código existente)
        elif msg.get("interval"):
            handle_interval_change(msg)
            
    except Exception as e:
        print("Error procesando mensaje:", e)
        send_error_response(str(e))
        
    # Liberamos la memoria
    gc.collect()
       
# Metodo para enviar respuesta de error 
def send_error_response(error_msg):
    response = {
        "actuator_code": config.ACTUATOR_CODE,
        "status": "ERROR",
        "message": error_msg,
        "timestamp": time.ticks_ms()
    }
    mqtt_client.publish(config.AWS_TOPIC_SUB, json.dumps(response), qos=0)
    # Liberamos la memoria
    gc.collect()
        
# Metodo para manejar mensajes de control
def handle_relay_command(msg):
    relay_name = msg["relay"]
    if relay_name not in relay_pins:
        send_error_response(f"Relay {relay_name} no válido")
        return
        
    if relay_locks[relay_name]:  # Si este relay está siendo operado
        send_error_response(f"Relay {relay_name} ocupado, intente luego")
        return
        
    command = msg["command"].upper()
    duration = msg.get("duration", 0)
    current_time = time.ticks_ms()

    relay_locks[relay_name] = True  # Bloquear este relay específico
    try:
        current_state = relay_pins[relay_name].value()
        
        if command == "ON":
            # Resto de validaciones ON...
            relay_pins[relay_name].value(0)
            active_relays[relay_name] = time.ticks_add(current_time, duration * 1000)
            
        elif command == "OFF":
            # Resto de validaciones OFF...
            relay_pins[relay_name].value(1)
            active_relays.pop(relay_name, None)
        
        last_relay_operations[relay_name] = current_time
        response = { ... }  # Tu estructura de respuesta
        #safe_publish(response)
        leer_sensores()
        
    finally:
        relay_locks[relay_name] = False  # Liberar siempre el bloqueo

# Metodo para manejar mensajes de intervalo    
def handle_interval_change(msg):	
    new_interval = msg.get("interval")
        
    # Validar intervalo
    if isinstance(new_interval, int) and 1 <= new_interval <= 86400:
        global sensor_interval, timer
            
        # Actualizar y guardar intervalo
        sensor_interval = new_interval
        if save_interval(sensor_interval):
            # Reconfigurar timer
            timer.deinit()
            timer.init(period=sensor_interval*1000, mode=Timer.PERIODIC, callback=lambda t: leer_sensores())
            print("Intervalo actualizado:", sensor_interval)
                
            # Enviar confirmación
            response = {
                "actuator_code": config.ACTUATOR_CODE,
                "interval": "OK",
                "seconds_to_report": sensor_interval
            }
            mqtt_client.publish(config.AWS_TOPIC_SUB, json.dumps(response), qos=0)
            print("Confirmación enviada al servidor")

# Método para reiniciar el dispositivo 
def check_boot_button():
    try:
        if boot_button.value() == 0:  
            time.sleep(0.1)  # Esperar 100ms para confirmar pulsación
            if boot_button.value() == 0:  # Si sigue presionado, iniciar conteo
                print("\nBotón BOOT detectado - Iniciando conteo...")
                start_time = time.ticks_ms()
                pressed = True
                while time.ticks_diff(time.ticks_ms(), start_time) < 3000:
                    if boot_button.value() == 1:
                        pressed = False
                        break
                    time.sleep_ms(100)
                
                if pressed:
                    print("\n--- RESETEO DE CONFIGURACIÓN ---")
                    try:
                        uos.remove(WIFI_FILE)
                        print(f"Archivo {WIFI_FILE} eliminado")
                    except OSError as e:
                        print(f"Error eliminando el archivo: {e}")
                    
                    print("Reiniciando dispositivo...\n")
                    time.sleep(1)
                    reset()
                else:
                    print("Reset cancelado")
        return False
    except Exception as e:
        print("Error en check_boot_button:", e)
        
# Cargar y guardar intervalo de envío de datos
def load_interval():
    try:
        with open(CONFIG_FILE, 'r') as f:
            interval = int(f.read())
            print(f"Intervalo de envío de datos configurado en: {interval} segundos")
            return interval
    except:
        print(f"No se pudo cargar el intervalo, usando valor por defecto: {DEFAULT_INTERVAL} segundos")
        return DEFAULT_INTERVAL

# Guardar intervalo de envío de datos
def save_interval(value):
    try:
        with open(CONFIG_FILE, 'w') as f:
            f.write(str(value))
        print(f"Intervalo guardado: {value} segundos")
        return True
    except Exception as e:
        print(f"Error guardando intervalo: {e}")
        return False

# Leer sensores y enviar datos por MQTT
def leer_sensores(new_interval=None):        
        
    global sensor_interval, timer
    
    try:
        if new_interval is not None and 1 <= new_interval <= 86400:
            sensor_interval = new_interval
            save_interval(sensor_interval)
            timer.deinit()
            timer.init(period=sensor_interval*1000, mode=Timer.PERIODIC, callback=lambda t: leer_sensores())
    except Exception as e:
        print("Error en new_interval:", e)

    try:
        # Verificación silenciosa de WiFi
        if not check_wifi_connection():
            return
        
        # Obtener la hora local ajustada por timezone
        def adjust_time_with_timezone(utc_time, timezone_offset):
            """Ajusta la hora UTC según el offset de timezone (ej: '-03:00')"""
            try:
                # Parsear el offset de timezone
                sign = -1 if timezone_offset[0] == '-' else 1
                hours = int(timezone_offset[1:3])
                minutes = int(timezone_offset[4:6])
                total_offset = sign * (hours * 3600 + minutes * 60)
                
                # Convertir tiempo local a segundos desde epoch
                epoch_time = time.mktime(utc_time)
                
                # Aplicar el offset
                adjusted_time = epoch_time + total_offset
                return time.localtime(adjusted_time)
            except Exception as e:
                print("Error ajustando zona horaria:", e)
                return utc_time  # Si hay error, devolver la hora sin ajuste
        
        # Se toma la fecha y hora del ESP32 y se ajusta por timezone
        current_time = time.localtime()
        adjusted_time = adjust_time_with_timezone(current_time, TIMEZONE)
        # print("La hora ajustada segun zona horaria es: ", adjusted_time)
        
        # Formateamos la fecha y hora
        year, month, day, hour, minute, second = adjusted_time[:6]
        fecha_formateada = f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
        
        # Se acceden a los sensores      
        try:
            sensor_data.update({
                "actuator_code": config.ACTUATOR_CODE,
                "relay_water": 0 if relay_water.value() == 1 else 1,
                "relay_aerator": 0 if relay_aerator.value() == 1 else 1,
                "relay_vent": 0 if relay_vent.value() == 1 else 1,
                "relay_light": 0 if relay_light.value() == 1 else 1,
                "relay_ph_plus": 0 if relay_ph_plus.value() == 1 else 1,
                "relay_ph_minus": 0 if relay_ph_minus.value() == 1 else 1,
                "relay_nutri_1": 0 if relay_nutri_1.value() == 1 else 1,
                "relay_nutri_2": 0 if relay_nutri_2.value() == 1 else 1,
                "relay_nutri_3": 0 if relay_nutri_3.value() == 1 else 1,
                "relay_nutri_4": 0 if relay_nutri_4.value() == 1 else 1,
                "datetime": fecha_formateada,
            })
        except Exception as e:
            print("Error en sensor_data.update:", e)

        # Enviar por MQTT si está conectado
        try:
            mqtt_client.publish(topic=config.AWS_TOPIC_PUB, msg=json.dumps(sensor_data), qos=0)
            print("Mensaje publicado: ", json.dumps(sensor_data))
        except Exception as e:
            print("Error en cliente MQTT, reconectando...")
            mqtt_client.connect()
            mqtt_client.publish(topic=config.AWS_TOPIC_PUB, msg=json.dumps(sensor_data), qos=0)
        
        # Liberamos la memoria
        gc.collect()
    
    except Exception as e:
        print("Error en check_wifi_connection:", e)

# Código principal
try:
    print("\nIniciando dispositivo...")
    led.off()  # Comenzar con LED apagado
    
    # Intento inicial de conexión WiFi
    try:
        if not connect_wifi():
            print("No se pudo conectar al Wi-Fi en el inicio")
        else:
            # Sincronizar hora si WiFi está conectado
            if not sync_time():
                print("Advertencia: No se pudo sincronizar la hora por NTP")
                
            # Liberamos la memoria
            gc.collect()
            
            # Conexión al servidor AWS IoT Core
            print("Intentando conectar a AWS IoT Core...")
            try:
                mqtt_client.connect()
                print("Conectado a AWS IoT Core correctamente")
                
                # Suscribirse a topic de MQTT
                try:
                    mqtt_client.set_callback(subscription_cb)
                    mqtt_client.subscribe(config.AWS_TOPIC_SUB)
                    print(f"Suscrito al tópico: {config.AWS_TOPIC_SUB}")
                except Exception as e:
                    print("Error al suscribirse:", e)
            except Exception as e:
                print("Error conectando a AWS IoT Core:", e)
    except Exception as e:
        print("Error en connect_wifi:", e)
    # Configuración inicial
    sensor_interval = load_interval()
    
    # Configurar timer y leer sensores y liberar memoria
    timer = Timer(-1)
    # Liberamos la memoria
    gc.collect()
    # Tarea de lectura de sensores
    timer.init(period=sensor_interval*1000, mode=Timer.PERIODIC, callback=lambda t: leer_sensores())
    # Liberamos la memoria
    gc.collect()
        
    # Bucle principal
    while True:
        # Liberamos la memoria
        gc.collect()
        try:
            # Verificar relays activos
            check_active_relays()
            
            # Verificar WiFi periódicamente
            if time.ticks_diff(time.ticks_ms(), last_wifi_check) > WIFI_CHECK_INTERVAL:
                check_wifi_connection()
                last_wifi_check = time.ticks_ms()
                                    
            # Verificar botón de reset
            check_boot_button()
                
            # Chequear mensajes MQTT
            if wifi_connected:
                try:
                    mqtt_client.check_msg()
                except Exception as e:
                    print("Error en el cliente MQTT:", e)
            
            # Pequeño delay para no saturar el procesador
            time.sleep(0.1)
            
        except Exception as e:
            print("Error crítico:", e)
            time.sleep(5)

except KeyboardInterrupt:
    print("\nPrograma detenido por el usuario")
    try:
        timer.deinit()
    except:
        pass
    led.off()
    reset()

except Exception as e:
    print("Error fatal:", e)
    sys.print_exception(e)
    time.sleep(2)
    reset()