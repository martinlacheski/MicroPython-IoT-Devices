# ph.py
from machine import ADC, Pin

class PHSensor:
    def __init__(self):
        self.adc = ADC(Pin(35))
        self.adc.atten(ADC.ATTN_11DB)  # Rango hasta ~3.6V
        self.scale = 4095 / 14  # Equivalente a 73.07 en Arduino

    def read_ph(self):
        adc_val = self.adc.read()
        ph = (4095 - adc_val) / self.scale
        return round(ph, 2), adc_val

