from datetime import datetime, time, date, timedelta
import requests
import logging
import locale
import pickle
import json
import sys
import os

logging.basicConfig(filename='logs_pvpc.log', encoding='utf-8', level=logging.INFO)
logging.info(str(datetime.now()) + " - Comienza el proceso")

## Configura locale para usar el formato de fechas español
locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")

## Definición de los días
hoy = date.today()
manana = hoy + timedelta(1)
dia = datetime.now()

# Variables para el Token y la URL del chatbot de Telegram
TOKEN = os.environ.get('TOKEN')
url_telegram = "https://api.telegram.org/bot" + TOKEN + "/"
idchat = os.environ.get('IDCHAT')

## Comprueba si han salido los datos del día siguiente, si no, muestra el día actual
nuevos_datos = time(20, 5, 0)
if(datetime.now().time() >= nuevos_datos):
    dia = manana
else:
    dia = hoy

## Prepara la llamada a la API
url = 'https://apidatos.ree.es/es/datos/mercados/precios-mercados-tiempo-real?start_date='+str(dia)+'T00:00&end_date='+str(dia)+'T23:59&time_trunc=hour'

## Hace la llamada
response = requests.get(url)

## Si la respuesta desde la web de ESIOS es 200 (OK)
if response.status_code != 200:
    logging.error(str(datetime.now()) + " - Status: " + str(response.status_code) + " - No se han podido recuperar los datos de la API")
    requests.get(url_telegram + "sendMessage?text=" + "No se han podido recuperar los datos de la API" +  "&chat_id=" + str(idchat))
    sys.exit(1)

## Crea una JSON String con la información recibida de la API
json_data = json.loads(response.text)

## Coge únicamente los datos del PVPC por horas
datos = json_data['included'][0]['attributes']['values']
logging.info(str(datetime.now()) + " - Última actualización: " + json_data['included'][0]['attributes']['last-update'])
ultimaHora = datetime.fromisoformat(json_data['included'][0]['attributes']['last-update'])
## Mira si existe fecha de última actualización y la crea si no existe
try:
    open("ultimoUpdate.pickle", "rb")
except (OSError, IOError) as e:
    pickle.dump(datetime.fromisoformat(json_data['included'][0]['attributes']['last-update']), open("ultimoUpdate.pickle", "wb"))

## Carga la fecha de última actualización
ultimoUpdate = pickle.load(open("ultimoUpdate.pickle", "rb"))

## Proceso que prepara y envía los datos
def procesarDatos():
    ## Variables que usa el proceso
    fecha = ""
    hora = ""
    precio = 0.0
    precios_dia = {}
    medio = 0.0
    lista = ""
    emojis = []

    ## Extrae la información del JSON
    for i in datos:
        fecha = i['datetime'].split("T")[1][0:2]
        hora = str(int(fecha)) + "h - " + str(int(fecha) + 1) + "h"
        precio = i['value']/1000
        precios_dia[hora] = precio.__round__(5)

    ## Calcula el precio medio
    for i in precios_dia:
        medio += precios_dia[i]
    medio = medio/24

    ## Ordena los precios diarios para calcular el mínimo y el máximo
    precios_ordenados = [(hora, precio) for hora, precio in {hora: precio for hora, precio in sorted(precios_dia.items(), key=lambda item: item[1])}.items()]
    minimo = precios_ordenados[0][1]
    maximo = precios_ordenados[-1][1]

    ## Lista con los precios del día
    precios = [(hora, precio) for hora, precio in precios_dia.items()]

    ## Crea las tuplas con la hora, el precio y el emoji a mostrar
    for i in precios:
        if i[1] <= minimo*1.175:
            emojis.append(("\U0001F7E2", i[0], i[1]))
        elif i[1] >= maximo*0.9:
            emojis.append(("\U0001F534", i[0], i[1]))
        else:
            emojis.append(("\U0001F7E1", i[0], i[1]))

    ## Crea la lista con los precios por hora para mostrar en Telegram
    for i in emojis:
        lista += i[0] + i[1] + " " + str(i[2]) + " €/kWh" + "\n"

    ## Crea las strings con los precios mínimo, máximo y medio
    precio_minimo = "Mínimo: " + str(minimo) + " - " + str(minimo) + " €/kWh"
    precio_maximo = "Máximo: " + str(maximo) + " - " + str(maximo) + " €/kWh"
    precio_medio = "Medio: " + str((medio).__round__(5)) + " €/kWh"

    ## String con el mensaje completo
    mensaje = "Precio luz " + dia.__format__('%A %d/%m/%y') + "\n\n" + str(precio_minimo) + "\n" +  str(precio_maximo) + "\n" +  str(precio_medio) + "\n\n" + lista
    logging.info(str(datetime.now()) + " -\n" + mensaje)

    ## Manda el mensaje completo al bot de Telegram
    response =requests.get(url_telegram + "sendMessage?text=" + "Precio luz " + dia.__format__('%A %d/%m/%y') + "\n\n" + str(precio_minimo) + "\n" +  str(precio_maximo) + "\n" +  str(precio_medio) + "\n\n" + lista + "&chat_id=" + str(idchat))

    ## Comprueba si la ejecución ha sido correcta
    if response.status_code == 200:
        logging.info(str(datetime.now()) + " - Finaliza el proceso correctamente")
    else:
        logging.warning(str(datetime.now()) + " - Status: " + str(response.status_code) + " - Puede que el proceso no haya finalizado correctamente")
        sys.exit(1)

## Si ha habido actualización, ejecutamos el procesado de datos y guardamos la nueva fecha
if ultimaHora > ultimoUpdate:
    procesarDatos()
    pickle.dump(datetime.fromisoformat(json_data['included'][0]['attributes']['last-update']), open("ultimoUpdate.pickle", "wb"))
else:
    logging.info(str(datetime.now()) + " - Los datos no han sido actualizados")
    sys.exit(0)
