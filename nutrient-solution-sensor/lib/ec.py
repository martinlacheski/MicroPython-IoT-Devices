from machine import ADC, Pin
import time

class ECSensor:
    def __init__(self):
        """
        Inicializa el sensor de Conductividad Eléctrica (EC)
        con las especificaciones del sensor DJS-1 (0-20mS/cm)
        """
        # Parámetros del sensor
        self.EC_RANGE = 20.0          # 20mS/cm (20000 µS/cm)
        self.OUTPUT_VOLTAGE = 3.4     # Máximo voltaje de salida
        self.CELL_CONSTANT = 1.0       # Constante de celda
        self.TEMP_COEFF = 0.02        # 2% por °C
        
        # Configuración ADC (ESP32)
        self.ec_adc = ADC(Pin(33))
        self.ec_adc.atten(ADC.ATTN_11DB)  # Rango completo 0-3.3V
        self.adc_range = 4095          # 12-bit ADC
        
        # Calibración
        self.calibration_factor = 1.0
        
    def _read_voltage(self, samples=10):
        """Lee el voltaje promediando varias muestras"""
        total = 0
        for _ in range(samples):
            total += self.ec_adc.read()
            time.sleep_ms(10)
        return (total / samples) * 3.3 / self.adc_range
    
    def _voltage_to_ec(self, voltage, temperature=25.0):
        """
        Convierte voltaje a EC (mS/cm) con compensación de temperatura
        Fórmula adaptada para rango 0-20mS/cm
        """
        # Normalizar al rango del sensor (0-3.4V)
        normalized_voltage = min(voltage, self.OUTPUT_VOLTAGE)
        
        # Calcular EC bruta (lineal para este sensor)
        ec_raw = (normalized_voltage / self.OUTPUT_VOLTAGE) * self.EC_RANGE
        
        # Aplicar constante de celda y factor de calibración
        ec_value = ec_raw * self.CELL_CONSTANT * self.calibration_factor
        
        # Compensación por temperatura (2% por °C)
        ec_25 = ec_value / (1 + self.TEMP_COEFF * (temperature - 25.0))
        
        return ec_25
    
    def read_ec(self, temperature=25.0, unit='mS', decimal_places=2):
        """
        Lee la conductividad eléctrica
        
        Args:
            temperature: Temperatura del agua en °C
            unit: 'mS' para mS/cm o 'uS' para µS/cm
            decimal_places: Número de decimales
        Returns:
            Valor de EC en las unidades seleccionadas
        """
        voltage = self._read_voltage()
        ec_mS = self._voltage_to_ec(voltage, temperature)
        
        if unit.lower() == 'us':
            ec_value = ec_mS * 1000  # Convertir a µS/cm
        else:
            ec_value = ec_mS
        
        if decimal_places == 0:
            return int(round(ec_value))
        return round(ec_value, decimal_places)
    
    def calibrate(self, known_ec, temperature=25.0, unit='mS'):
        """
        Calibra el sensor con solución conocida
        
        Args:
            known_ec: Valor conocido de EC
            temperature: Temperatura durante calibración
            unit: 'mS' o 'uS' según la solución
        """
        if unit.lower() == 'us':
            known_ec /= 1000  # Convertir a mS/cm
        
        voltage = self._read_voltage()
        ec_raw = (voltage / self.OUTPUT_VOLTAGE) * self.EC_RANGE
        self.calibration_factor = known_ec / (ec_raw * self.CELL_CONSTANT)
        
        return self.calibration_factor