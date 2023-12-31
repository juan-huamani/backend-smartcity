from django.http import JsonResponse
from django.shortcuts import redirect
from rest_framework.decorators import api_view
import requests, json
import websockets
from django.conf import settings
import urllib.parse
import datetime
import pytz
from geopy.distance import geodesic


@api_view(['POST'])
def get_devices(request):
    try:
        # Obtener el token del usuario autenticado
        token = request.META.get('HTTP_AUTHORIZATION')

        if(token == settings.API_KEY_SSMC):
            url = settings.TRACCAR_URL_BASE + '/api/devices'
            
            # Realizar la solicitud GET a la API de Traccar con los parámetros
            params = {
                'all': True,
            }
            # response = requests.get(url, params=params, headers=headers)
            response = requests.get(url, params=params, auth=(settings.API_USR_TRACCAR, settings.API_PSS_TRACCAR))
            if response.status_code == 200:
                # Procesar la respuesta de la API de Traccar
                devices_data = response.json()
                
                # Obtener las posiciones de la respuesta y almacenarlas en la lista "posiciones"
                devices = []
                for device in devices_data:
                    id = device.get('id')
                    placa = device.get('name')
                    modelo = device.get('model')
                    categoria = device.get('category')
                    fecha_hora_utc = device.get('lastUpdate')
                    estado = device.get('status')
                    
                    preactualizado = datetime.datetime.strptime(fecha_hora_utc,'%Y-%m-%dT%H:%M:%S.%f%z')
                    zona_horaria = pytz.timezone('America/Lima')
                    fecha_hora_ajustada = preactualizado.astimezone(zona_horaria)
                    actualizado = fecha_hora_ajustada.strftime('%Y-%m-%d %H:%M:%S')


                    devices.append({
                        'id': id, 
                        'placa': placa,
                        'modelo': modelo, 
                        'categoria': categoria,
                        "actualizado": actualizado,
                        'estado': estado
                    })
                
                # Resto del código...
                return JsonResponse({'dispositivo': devices})
            else:
                return JsonResponse({'error': 'Error al obtener las posiciones de Traccar'}, status=response.status_code)
        else:
            return JsonResponse({'error': 'No está autorizado para acceder a esta información'}, status=401)
    except Exception as e:
        # Capturar errores no controlados y enviar un mensaje de error
        return JsonResponse({'error': str(e)})

def tracking(request):
    api_url = settings.TRACCAR_URL_BASE + '/api/session'
    
    queryParams = {
        'token': settings.API_TOKEN
    }
    
    encodedParams = urllib.parse.urlencode(queryParams)
    
    url = f'{api_url}?{encodedParams}'

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        coordenadas = {
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
        }
        return coordenadas
        # return JsonResponse({"data": coordenadas})

    else:
        return {'status': 'error'}

# @api_view(['POST'])
def get_history_gps(deviceId):
# def get_history_gps(dispositivo, inicio, fin):
    # dispositivo = request.data.get('dispositivo')
    dispositivo = deviceId
    fecha_actual = datetime.datetime.now().date()
    inicio = datetime.datetime.combine(fecha_actual, datetime.datetime.min.time())
    fin = datetime.datetime.combine(fecha_actual, datetime.datetime.max.time())
    
    inicio_str = inicio.isoformat()+"Z"
    fin_str = fin.isoformat()+"Z"
    api_url = settings.TRACCAR_URL_BASE + '/api/positions'
    
    # formatear fecha utc-5 a utc iso 8601

    encodedParams = {
        "deviceId": dispositivo,
        "from": inicio_str,
        "to": fin_str
    }

    response = requests.get(api_url, params=encodedParams, auth=(settings.API_USR_TRACCAR, settings.API_PSS_TRACCAR))

    if response.status_code == 200:
        data = response.json()

        # formatear fecha utc iso 8601 a utc-5

        registros = []

        ultima_posicion = 0 
        ultima_posicion_distancia = 0

        for posicion in data:
            velocidad = posicion.get('speed')
            motion = posicion['attributes']['motion']
            fecha_hora_utc = posicion.get('deviceTime')
            prefecha = datetime.datetime.strptime(fecha_hora_utc,'%Y-%m-%dT%H:%M:%S.%f%z')
            zona_horaria = pytz.timezone('America/Lima')
            fecha_hora_ajustada = prefecha.astimezone(zona_horaria)
            fecha = fecha_hora_ajustada.strftime('%Y-%m-%d %H:%M:%S')

            tiempo_detenido = 0

            if motion:
                tiempo_detenido = 0
                evento = 'Movimiento'
            else:
                evento = 'Detenido'

            if velocidad == 0:
                tiempo_actual = datetime.datetime.strptime(posicion.get('deviceTime'), "%Y-%m-%dT%H:%M:%S.%f%z")
            
                if ultima_posicion:
                    tiempo_detenido = (tiempo_actual - ultima_posicion).total_seconds()

                ultima_posicion = tiempo_actual

            distancia_recorrida = 0.0

            if ultima_posicion_distancia:
                coordenadas_actual = (posicion.get('latitude'), posicion.get('longitude'))
                coordenadas_anterior = (ultima_posicion_distancia.get('latitude'), ultima_posicion_distancia.get('longitude'))
                distancia_recorrida = geodesic(coordenadas_anterior, coordenadas_actual).meters
                

            posicion['tiempo_detenido'] = obtener_formato_tiempo(tiempo_detenido)
            posicion['distancia_recorrida'] = distancia_recorrida

            history = {
                "motion": motion,
                "evento": evento,
                "velocidad": formatear_decimales(posicion.get('speed')) + " Km/h",
                # "unidadVelocidad": 'Km/h',
                "latitud": posicion.get('latitude'),
                "longitud": posicion.get('longitude'),
                "fecha": fecha,
                "distancia": formatear_distancia(distancia_recorrida),
                "tiempoDetenido": posicion['tiempo_detenido']
            }
            registros.append(history)
            ultima_posicion_distancia = posicion

        # return registros
        return JsonResponse({"registros":registros})
    return JsonResponse({"error": "Ocurrió un error en la conexión"}, status=500)

def obtener_formato_tiempo(segundos):
    if segundos is None:
        return None

    td = datetime.timedelta(seconds=segundos)
    
    if segundos < 60:
        return f"{segundos} segundos"
    elif segundos < 3600:
        minutos = td.seconds // 60
        segundos_restantes = td.seconds % 60
        return f"{minutos} minutos {segundos_restantes} segundos"
    else:
        horas = td.seconds // 3600
        minutos_restantes = (td.seconds % 3600) // 60
        segundos_restantes = (td.seconds % 3600) % 60
        return f"{horas} horas {minutos_restantes} minutos {segundos_restantes} segundos"

def formatear_distancia(valor):
    if isinstance(valor, (int, float)):
        if valor > 999.99:
            valor = valor / 1000  # Convertir a kilómetros
            valor_formateado = formatear_decimales(valor)
            return "{} Km".format(valor_formateado)
        else:
            valor_formateado = formatear_decimales(valor)
            return "{} m".format(valor_formateado)
    elif isinstance(valor, str) and valor.isdigit():
        valor_num = float(valor)
        if valor_num > 999.99:
            valor_num = valor_num / 1000  # Convertir a kilómetros
            valor_formateado = formatear_decimales(valor_num)
            return "{} Km".format(valor_formateado)
        else:
            valor_formateado = formatear_decimales(valor_num)
            return "{} m".format(valor_formateado)
    else:
        return "0.0 m"
    
def formatear_decimales(valor):
    if isinstance(valor, (int, float)):
        return "{:.2f}".format(valor)
    elif isinstance(valor, str) and valor.isdigit():
        return "{:.2f}".format(float(valor))
    else:
        return 0



