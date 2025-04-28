import machine
import network
import socket
import re
import time


class WifiManager:

    def __init__(self, ssid = 'WifiManager', password = 'EnviroSense', reboot = True, debug = False):
        self.wlan_sta = network.WLAN(network.STA_IF)
        self.wlan_sta.active(True)
        self.wlan_ap = network.WLAN(network.AP_IF)
        
        if len(ssid) > 32:
            raise Exception('El SSID no puede tener más de 32 caracteres.')
        else:
            self.ap_ssid = ssid
        if len(password) < 4:
            raise Exception('La contraseña no puede tener menos de 4 caracteres.')
        else:
            self.ap_password = password
            
        # Set the access point authentication mode to WPA2-PSK.
        self.ap_authmode = 3
        
        # The file were the credentials will be stored.
        # There is no encryption, it's just a plain text archive. Be aware of this security problem!
        self.wifi_credentials = 'wifi.dat'
        
        # Prevents the device from automatically trying to connect to the last saved network without first going through the steps defined in the code.
        self.wlan_sta.disconnect()
        
        # Change to True if you want the device to reboot after configuration.
        # Useful if you're having problems with web server applications after WiFi configuration.
        self.reboot = reboot
        
        self.debug = debug
        
        # Archivo para guardar la zona horaria
        self.timezone_file = 'timezone.conf'
        
        # Lista de zonas horarias comunes
        self.timezones = {
            '-12:00': 'UTC-12:00: Isla Baker, Isla Howland',
            '-11:00': 'UTC-11:00: Samoa Americana, Niue',
            '-10:00': 'UTC-10:00: Honolulu, Papeete',
            '-09:30': 'UTC-09:30: Islas Marquesas',
            '-09:00': 'UTC-09:00: Anchorage, Juneau',
            '-08:00': 'UTC-08:00: Los Ángeles, Tijuana, Vancouver',
            '-07:00': 'UTC-07:00: Denver, Phoenix, Chihuahua',
            '-06:00': 'UTC-06:00: Ciudad de México, San José, Chicago',
            '-05:00': 'UTC-05:00: Bogotá, Lima, Quito, Nueva York',
            '-04:30': 'UTC-04:30: Caracas (hora antigua)',
            '-04:00': 'UTC-04:00: Caracas, La Paz, Santiago (verano)',
            '-03:30': 'UTC-03:30: St. John’s (Terranova)',
            '-03:00': 'UTC-03:00: Buenos Aires, São Paulo, Montevideo',
            '-02:00': 'UTC-02:00: Atlántico Sur, Islas Georgias del Sur',
            '-01:00': 'UTC-01:00: Azores, Cabo Verde',
            '+00:00': 'UTC+00:00: Londres, Lisboa, Casablanca',
            '+01:00': 'UTC+01:00: Madrid, París, Berlín, Roma',
            '+02:00': 'UTC+02:00: El Cairo, Atenas, Jerusalén',
            '+03:00': 'UTC+03:00: Moscú, Nairobi, Bagdad',
            '+03:30': 'UTC+03:30: Teherán',
            '+04:00': 'UTC+04:00: Dubái, Bakú',
            '+04:30': 'UTC+04:30: Kabul',
            '+05:00': 'UTC+05:00: Islamabad, Taskent',
            '+05:30': 'UTC+05:30: Nueva Delhi, Colombo',
            '+05:45': 'UTC+05:45: Katmandú',
            '+06:00': 'UTC+06:00: Daca, Thimphu',
            '+06:30': 'UTC+06:30: Rangún, Islas Cocos',
            '+07:00': 'UTC+07:00: Bangkok, Hanoi, Yakarta',
            '+08:00': 'UTC+08:00: Beijing, Hong Kong, Perth',
            '+08:45': 'UTC+08:45: Eucla (Australia)',
            '+09:00': 'UTC+09:00: Tokio, Seúl, Yakutsk',
            '+09:30': 'UTC+09:30: Adelaida, Darwin',
            '+10:00': 'UTC+10:00: Sídney, Port Moresby',
            '+10:30': 'UTC+10:30: Isla Lord Howe',
            '+11:00': 'UTC+11:00: Honiara, Nueva Caledonia',
            '+12:00': 'UTC+12:00: Auckland, Fiyi',
            '+12:45': 'UTC+12:45: Islas Chatham',
            '+13:00': 'UTC+13:00: Nukualofa (Tonga), Samoa',
            '+14:00': 'UTC+14:00: Islas Line (Kiribati)'
        }
        
    def save_timezone(self, timezone):
        """Guarda la zona horaria en el archivo de configuración"""
        try:
            with open(self.timezone_file, 'w') as f:
                f.write(str(timezone))
                print(f"Zona horaria guardada: {timezone}")
        except:
            print(f"No se pudo guardar la zona horaria")


    def connect(self):
        if self.wlan_sta.isconnected():
            return
        profiles = self.read_credentials()
        for ssid, *_ in self.wlan_sta.scan():
            ssid = ssid.decode("utf-8")
            if ssid in profiles:
                password = profiles[ssid]
                if self.wifi_connect(ssid, password):
                    return
        print('No se pudo conectar a ninguna red WiFi. Iniciando el servidor web...')
        self.web_server()
        
    
    def disconnect(self):
        if self.wlan_sta.isconnected():
            self.wlan_sta.disconnect()


    def is_connected(self):
        return self.wlan_sta.isconnected()


    def get_address(self):
        return self.wlan_sta.ifconfig()


    def write_credentials(self, profiles):
        lines = []
        for ssid, password in profiles.items():
            lines.append('{0};{1}\n'.format(ssid, password))
        with open(self.wifi_credentials, 'w') as file:
            file.write(''.join(lines))


    def read_credentials(self):
        lines = []
        try:
            with open(self.wifi_credentials) as file:
                lines = file.readlines()
        except Exception as error:
            if self.debug:
                print(error)
            pass
        profiles = {}
        for line in lines:
            ssid, password = line.strip().split(';')
            profiles[ssid] = password
        return profiles


    def wifi_connect(self, ssid, password):
        print('Intentando conectar a la red:', ssid)
        self.wlan_sta.connect(ssid, password)
        for _ in range(100):
            if self.wlan_sta.isconnected():
                print('\nConectado! Datos de conexión:', self.wlan_sta.ifconfig())
                return True
            else:
                print('.', end='')
                time.sleep_ms(100)
        print('\nFalló la conexión!')
        self.wlan_sta.disconnect()
        return False

    
    def web_server(self):
        self.wlan_ap.active(True)
        self.wlan_ap.config(essid = self.ap_ssid, password = self.ap_password, authmode = self.ap_authmode)
        server_socket = socket.socket()
        server_socket.close()
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('', 80))
        server_socket.listen(1)
        print('Conectarse a la red Wi-Fi con SSID', self.ap_ssid, 'y la contraseña', self.ap_password, '- Acceder al servidor web en:', self.wlan_ap.ifconfig()[0])
        while True:
            if self.wlan_sta.isconnected():
                self.wlan_ap.active(False)
                if self.reboot:
                    print('El dispositivo se reiniciará en 5 segundos.')
                    time.sleep(5)
                    machine.reset()
            self.client, addr = server_socket.accept()
            try:
                self.client.settimeout(5.0)
                self.request = b''
                try:
                    while True:
                        if '\r\n\r\n' in self.request:
                            # Fix for Safari browser
                            self.request += self.client.recv(512)
                            break
                        self.request += self.client.recv(128)
                except Exception as error:
                    # It's normal to receive timeout errors in this stage, we can safely ignore them.
                    if self.debug:
                        print(error)
                    pass
                if self.request:
                    if self.debug:
                        print(self.url_decode(self.request))
                    url = re.search('(?:GET|POST) /(.*?)(?:\\?.*?)? HTTP', self.request).group(1).decode('utf-8').rstrip('/')
                    if url == '':
                        self.handle_root()
                    elif url == 'configure':
                        self.handle_configure()
                    else:
                        self.handle_not_found()
            except Exception as error:
                if self.debug:
                    print(error)
                return
            finally:
                self.client.close()


    def send_header(self, status_code = 200):
        self.client.send("""HTTP/1.1 {0} OK\r\n""".format(status_code))
        self.client.send("""Content-Type: text/html\r\n""")
        self.client.send("""Connection: close\r\n""")


    def send_response(self, payload, status_code = 200):
        self.send_header(status_code)
        self.client.sendall("""
            <!DOCTYPE html>
            <html lang="en">
                <head>
                    <title>WiFi Manager</title>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <link rel="icon" href="data:,">
                </head>
                <body>
                    {0}
                </body>
            </html>
        """.format(payload))
        self.client.close()


    def handle_root(self):
        self.send_header()
        self.client.sendall("""
            <!DOCTYPE html>
            <html lang="en">
                <head>
                    <title>WiFi Manager</title>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <link rel="icon" href="data:,">
                </head>
                <body>
                    <h1>WiFi Manager</h1>
                    <form action="/configure" method="post" accept-charset="utf-8">
        """.format(self.ap_ssid))
        for ssid, *_ in self.wlan_sta.scan():
            ssid = ssid.decode("utf-8")
            self.client.sendall("""
                        <p><input type="radio" name="ssid" value="{0}" id="{0}"><label for="{0}">&nbsp;{0}</label></p>
            """.format(ssid))
        self.client.sendall("""
                        <p><label for="password">Password:&nbsp;</label><input type="password" id="password" name="password"></p>
                        <p>
                            <label for="timezone">Zona horaria:&nbsp;</label>
                            <select id="timezone" name="timezone">
        """)
        
        # Añadir opciones de zonas horarias
        for tz, desc in sorted(self.timezones.items()):
            self.client.sendall(f"""
                                <option value="{tz}">{desc}</option>
            """)
        
        self.client.sendall("""
                            </select>
                        </p>
                        <p><input type="submit" value="Conectar"></p>
                    </form>
                </body>
            </html>
        """)
        self.client.close()

    def handle_configure(self):
        match = re.search('ssid=([^&]*)&password=(.*?)&timezone=([^&]*)', self.url_decode(self.request))
        if match:
            ssid = match.group(1).decode('utf-8').replace('+', ' ')
            password = match.group(2).decode('utf-8')
            timezone = match.group(3).decode('utf-8')
            
            if len(ssid) == 0:
                self.send_response("""
                    <p>Se debe proporcionar el SSID!</p>
                    <p>Volver atrás para intentar de nuevo!</p>
                """, 400)
            elif self.wifi_connect(ssid, password):
                # Guardar la zona horaria seleccionada
                self.save_timezone(timezone)
                
                self.send_response(f"""
                    <p>Conectado exitosamente a</p>
                    <h1>{ssid}</h1>
                    <p>Dirección IP: {self.wlan_sta.ifconfig()[0]}</p>
                    <p>Zona horaria configurada: {self.timezones.get(timezone, timezone)}</p>
                """)
                profiles = self.read_credentials()
                profiles[ssid] = password
                self.write_credentials(profiles)
                time.sleep(5)
            else:
                self.send_response(f"""
                    <p>No se pudo conectar a</p>
                    <h1>{ssid}</h1>
                    <p>Volver atrás para intentar de nuevo!</p>
                """)
                time.sleep(5)
        else:
            self.send_response("""
                <p>Parámetros no encontrados!</p>
            """, 400)
            time.sleep(5)


    def handle_not_found(self):
        self.send_response("""
            <p>Página no encontrada!</p>
        """, 404)


    def url_decode(self, url_string):

        # Source: https://forum.micropython.org/viewtopic.php?t=3076
        # unquote('abc%20def') -> b'abc def'
        # Note: strings are encoded as UTF-8. This is only an issue if it contains
        # unescaped non-ASCII characters, which URIs should not.

        if not url_string:
            return b''

        if isinstance(url_string, str):
            url_string = url_string.encode('utf-8')

        bits = url_string.split(b'%')

        if len(bits) == 1:
            return url_string

        res = [bits[0]]
        appnd = res.append
        hextobyte_cache = {}

        for item in bits[1:]:
            try:
                code = item[:2]
                char = hextobyte_cache.get(code)
                if char is None:
                    char = hextobyte_cache[code] = bytes([int(code, 16)])
                appnd(char)
                appnd(item[2:])
            except Exception as error:
                if self.debug:
                    print(error)
                appnd(b'%')
                appnd(item)

        return b''.join(res)
