from machine import Pin, SoftI2C, Timer, reset
from lib.wifi_manager import WifiManager
import lib.bme280 as bme280
import lib.bh1750 as bh1750
import lib.mhz19 as mhz19
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

# BME280 en I2C (SCL=19, SDA=18)
try:
    i2c_bme280 = SoftI2C(scl=Pin(19), sda=Pin(18), freq=400000)
    bme280 = bme280.BME280(i2c=i2c_bme280)
except Exception as e:
    print("¡Error crítico detectado en i2c_bme280!")
    print("Detalles del error:", str(e))
    
# BH1750 en I2C (SCL=22, SDA=21)
try:
    i2c_bh1750 = SoftI2C(scl=Pin(22), sda=Pin(21), freq=400000)
    bh1750 = bh1750.BH1750(i2c_bh1750)
except Exception as e:
    print("¡Error crítico detectado en i2c_bh1750!")
    print("Detalles del error:", str(e))

# MH-Z19 en UART2 (TX=17, RX=16)
try:
    mhz19 = mhz19.MHZ19(2)
    mhz19_ready = False
    start_time = time.time()
    max_warmup = 180  # Máximo 3 minutos según datasheet
    stable_readings = 0
    required_stable = 3  # Número de lecturas estables consecutivas
    
    print("Iniciando verificación MH-Z19C...")
    
    while not mhz19_ready and (time.time() - start_time) < max_warmup:
        try:
            # Intentar lectura
            mhz19.get_data()
            ppm = mhz19.ppm
            elapsed = time.time() - start_time
            
            # Evaluar validez de la lectura
            if 400 <= ppm <= 5000:  # Rango válido según datasheet
                stable_readings += 1
                print(f"\rLectura estable {stable_readings}/{required_stable} | PPM: {ppm} | {elapsed:.0f}s", end='')
                
                if stable_readings >= required_stable:
                    mhz19_ready = True
                    print(f"\nMH-Z19C listo en {elapsed:.1f} segundos (PPM estable: {ppm})")
            else:
                stable_readings = 0  # Resetear contador si lectura no válida
                print(f"\rLectura inválida: {ppm} PPM | {elapsed:.0f}s", end='')
            
            time.sleep(5)  # Intervalo entre lecturas de verificación
            
        except Exception as e:
            print(f"\nError en verificación: {str(e)[:50]}...")
            time.sleep(10)
    
    if not mhz19_ready:
        print(f"\nMH-Z19C iniciado por timeout ({max_warmup}s)")
        mhz19_ready = True  # Forzar continuar después del tiempo máximo

except Exception as e:
    print("\n¡Error crítico en MH-Z19C!")
    print("Detalles:", str(e))
    mhz19 = None
    
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

# Callback para mensajes entrantes (Seteo de nuevo intervalo y lectura inmediata)
def subscription_cb(topic, message):
    print("\nMensaje recibido:")
    print("Tópico:", topic.decode("utf-8"))
    print("Mensaje:", message.decode("utf-8"))
    print("-------------------")
    
    try:
        msg = json.loads(message.decode("utf-8"))
        
        # Verificar si el mensaje es para este sensor
        if msg.get("sensor_code") != config.SENSOR_CODE:
            print("Mensaje no destinado a este sensor")
            return
        
        # Comando para lectura inmediata
        if msg.get("command") == "read_now":
            print("Comando de lectura inmediata recibido")
            
            # Enviar confirmación
            response = {
                "sensor_code": config.SENSOR_CODE,
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
        
        # Cambio de intervalo
        elif "interval" in msg:
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
                        "sensor_code": config.SENSOR_CODE,
                        "interval": "OK",
                        "seconds_to_report": sensor_interval
                    }
                    mqtt_client.publish(config.AWS_TOPIC_SUB, json.dumps(response), qos=0)
                    print("Confirmación enviada al servidor")
        
        # Comando no reconocido
        #else:
        #    print("Comando no reconocido en el mensaje", msg)
                
    except Exception as e:
        print("Error procesando mensaje:", e)
        
    # Liberamos la memoria
    gc.collect()

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
        lux = bh1750.luminance(bh1750.CONT_HIRES_1)
        temp, press, hum = bme280.read_compensated_data()
        mhz19.get_data()
               
        try:
            sensor_data.update({
                "sensor_code": config.SENSOR_CODE,
                "temperature": round(temp, 2),
                "humidity": round(hum, 2),
                "atmospheric_pressure": round(press / 100, 2),
                "luminosity": round(lux, 2),
                "co2": mhz19.ppm,
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
    gc.collect()
    # Tarea de lectura de sensores
    timer.init(period=sensor_interval*1000, mode=Timer.PERIODIC, callback=lambda t: leer_sensores())
    gc.collect()
        
    # Bucle principal
    while True:
        # Liberamos la memoria
        gc.collect()
        try:
            # Verificación periódica silenciosa
            check_wifi_connection()
                        
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