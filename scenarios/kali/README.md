# Generador Kali acotado

Este ejecutor acepta únicamente cuatro estímulos HTTP predeterminados contra
`10.20.0.10:8080`. Comprueba que Kali tenga `10.20.0.30`, deshabilita proxies,
limita cada ejecución a 30 solicitudes y no acepta objetivos proporcionados por
el operador. Se transmite por SSH desde `evalctl`; no contiene credenciales.

Kali se utiliza como fuente externa de laboratorio. No aloja componentes SOC,
no recibe un agente Wazuh y no debe conservar una ruta de salida a Internet
durante la evaluación.
