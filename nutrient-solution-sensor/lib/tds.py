from machine import ADC, Pin
import utime

class TDSMeter:
    def __init__(self, vref=3.3, scount=30):
        self.vref = vref
        self.scount = scount
        self.adc = ADC(Pin(34))
        self.adc.atten(ADC.ATTN_11DB)  # Para leer hasta 3.3V
        self.adc.width(ADC.WIDTH_12BIT)  # 0-4095 resolución
        self.buffer = [0] * scount
        self.index = 0

    def update(self):
        # Tomar una nueva muestra cada 40ms
        self.buffer[self.index] = self.adc.read()
        self.index = (self.index + 1) % self.scount
        utime.sleep_ms(40)

    def median(self, values):
        sorted_vals = sorted(values)
        mid = len(sorted_vals) // 2
        if len(sorted_vals) % 2 == 0:
            return (sorted_vals[mid - 1] + sorted_vals[mid]) // 2
        else:
            return sorted_vals[mid]

    def get_tds(self, temperature=25.0):
        # Calcular voltaje promedio
        median_adc = self.median(self.buffer)
        voltage = median_adc * self.vref / 4096.0

        # Compensación por temperatura
        compensation_coefficient = 1.0 + 0.02 * (temperature - 25.0)
        compensation_voltage = voltage / compensation_coefficient

        # Cálculo de TDS (ppm)
        tds_value = (
            133.42 * compensation_voltage**3
            - 255.86 * compensation_voltage**2
            + 857.39 * compensation_voltage
        ) * 0.5

        return int(tds_value), voltage, median_adc
    
    def get_tds_and_ec(self, temperature=25.0):
        median_adc = self.median(self.buffer)
        voltage = median_adc * self.vref / 4096.0

        compensation_coefficient = 1.0 + 0.02 * (temperature - 25.0)
        compensation_voltage = voltage / compensation_coefficient

        # TDS en ppm
        tds_value = (
            133.42 * compensation_voltage**3
            - 255.86 * compensation_voltage**2
            + 857.39 * compensation_voltage
        ) * 0.5

        # Estimar EC en mS/cm
        ec_value = tds_value / 500.0  # Conversión típica: TDS = EC * 500 o TDS = EC * 640

        return int(tds_value), round(ec_value, 3), round(voltage, 3), median_adc