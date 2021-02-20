from time import sleep, mktime
import time as t
import sys
import os
from DbAccess import *
from Mqtt import *
import serial
from threading import Thread
import Adafruit_DHT
from gpiozero import LED, Buzzer, Button
import telepot
from rpi_lcd import LCD
from threading import Lock
from datetime import datetime as dt
import datetime as datetime
from picamera import PiCamera
import boto3
import base64
from signal import pause
import uuid

basedir = os.path.abspath(os.path.dirname(__file__))
config = ConfigParser()
config.read(os.path.join(basedir, 'config.conf'))

RASPBERRY_PI_DEVICE_NAME = config['RASPBERRY-PI']['DEVICE_NAME']

""" SENSORS CONFIG"""
SENSOR_DHT11_PIN = int(config['SENSOR-DHT11']['PIN'])
SENSOR_LED_PIN = int(config['SENSOR-LED']['PIN'])
SENSOR_BUZZER_PIN = int(config['SENSOR-BUZZER']['PIN'])
SENSOR_BUTTON_PIN = int(config['SENSOR-BUTTON']['PIN'])
SENSOR_LIGHT_SERIAL_PORT = config['SENSOR-LIGHT']['SERIAL_PORT']
SENSOR_LIGHT_BAUDRATE = int(config['SENSOR-LIGHT']['BAUDRATE'])


serial = serial.Serial(SENSOR_LIGHT_SERIAL_PORT, SENSOR_LIGHT_BAUDRATE)  #change ACM number as found from ls /dev/tty/ACM*
serial.baudrate=SENSOR_LIGHT_BAUDRATE


# Initialise AWS MQTT Publisher 
mqtt_publisher = MQTTPublisher()

led = LED(SENSOR_LED_PIN)
buzzer = Buzzer(SENSOR_BUZZER_PIN)
button = Button(SENSOR_BUTTON_PIN, pull_up=False)

lock = Lock()

my_bot_token = '1478147032:AAHHhcMUfsMvt5JkK9jLmQL_k1zubcYlJkY'
chat_id = 961348895 # own chat id from bot

realtime_dict = {
                    'light': 0,
                    'temperature': 0,
                    'humidity': 0
                }

gobal_dict = { "alarm": None, "rang": False }

directory = basedir + '/static/detection_images/' + RASPBERRY_PI_DEVICE_NAME #folder name on your raspberry pi
access_directory = '/detection_images/' + RASPBERRY_PI_DEVICE_NAME + "/" #folder name on your raspberry pi
os.makedirs(directory, exist_ok=True) 
P=PiCamera()
collectionId='mycollection' #collection name
rek_client=boto3.client('rekognition', region_name='us-east-1')

def analyse_face():
    access = ""
    file_name = 'image_{}.jpg'.format(uuid.uuid4())
    image = '{}/{}'.format(directory,file_name)
    P.capture(image) #capture an image
    print('captured '+image)
    with open(image, 'rb') as image:
        try: #match the captured imges against the indexed faces
            match_response = rek_client.search_faces_by_image(CollectionId=collectionId, Image={'Bytes': image.read()}, MaxFaces=1, FaceMatchThreshold=85)
            if match_response['FaceMatches']:
                print('Hello, ',match_response['FaceMatches'][0]['Face']['ExternalImageId'])
                print('Similarity: ',match_response['FaceMatches'][0]['Similarity'])
                print('Confidence: ',match_response['FaceMatches'][0]['Face']['Confidence'])
                mqtt_publisher.publish_facial_recognition_data(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), access_directory + file_name, match_response['FaceMatches'][0]['Face']['ExternalImageId'])
                return 'Hello, ' + match_response['FaceMatches'][0]['Face']['ExternalImageId']
            else:
                print('No faces matched')
                mqtt_publisher.publish_facial_recognition_data(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), access_directory + file_name, "Access Denied")
                return "NA"
        except:
            print('No face detected')
            mqtt_publisher.publish_facial_recognition_data(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), access_directory + file_name, "Access Denied")
            return "NA"

    mqtt_publisher.publish_facial_recognition_data(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), access_directory + file_name, "Access Denied")
    return "NA"

def analyse_face_for_physical_button():
    access = ""
    file_name = 'image_{}.jpg'.format(uuid.uuid4())
    image = '{}/{}'.format(directory,file_name)
    P.capture(image) #capture an image
    print('captured '+image)
    with open(image, 'rb') as image:
        try: #match the captured imges against the indexed faces
            match_response = rek_client.search_faces_by_image(CollectionId=collectionId, Image={'Bytes': image.read()}, MaxFaces=1, FaceMatchThreshold=85)
            if match_response['FaceMatches']:
                print('Hello, ',match_response['FaceMatches'][0]['Face']['ExternalImageId'])
                print('Similarity: ',match_response['FaceMatches'][0]['Similarity'])
                print('Confidence: ',match_response['FaceMatches'][0]['Face']['Confidence'])
                mqtt_publisher.publish_facial_recognition_data(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), access_directory + file_name, match_response['FaceMatches'][0]['Face']['ExternalImageId'])
                ring()
                return 'Hello, ' + match_response['FaceMatches'][0]['Face']['ExternalImageId']
            else:
                print('No faces matched')
                mqtt_publisher.publish_facial_recognition_data(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), access_directory + file_name, "Access Denied")
                return "NA"
        except:
            print('No face detected')
            mqtt_publisher.publish_facial_recognition_data(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), access_directory + file_name, "Access Denied")
            return "NA"

    mqtt_publisher.publish_facial_recognition_data(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), access_directory + file_name, "Access Denied")
    return "NA"

def ledOn():
    led.on()
    return "LED turned on"

def ledOff():
    led.off()
    return "LED turned off"

def ledStatus():
    if led.is_lit:
        return 'on'
    else:
        return 'off'

def ring():
    buzzer.on()
    sleep(3)
    buzzer.off()
    return "buzzer off"

def run_light_sensor():
    print("run_light_sensor()")
    try:
        update = True
        while update:
            try:
                read_serial = serial.readline() # read data sent from arduino
                light_value = read_serial.decode('ASCII').strip() # converts byte to string

                if light_value is not None:
                    lock.acquire()
                    result_value = mqtt_publisher.publish_light_data(light_value) # publish the light value to aws via mqtt and store in dynamodb

                    if result_value == True:
                        print(f"stored light value: {light_value}")

                    realtime_dict["light"] = light_value  # update realtime_dict
                    lock.release()
                    sleep(5)

            except KeyboardInterrupt:
                update = False

            except:
                print("Error while inserting light data...")
                print(sys.exc_info()[0])
                print(sys.exc_info()[1])

    except:
        print(sys.exc_info()[0])
        print(sys.exc_info()[1])




def run_dht11_sensor():
    print("run_dht11_sensor()")
    try:
        update = True
        while update:
            try:
                humidity, temperature = Adafruit_DHT.read_retry(11, SENSOR_DHT11_PIN)

                if humidity is not None and temperature is not None:
                    lock.acquire()
                    result_value = mqtt_publisher.publish_dht11_data(humidity, temperature)  # publish the dht 11 values to aws via mqtt and store in dynamodb

                    if result_value == True:
                        print("\n")
                        print(f"stored humidity: {humidity}")
                        print(f"stored temperature: {temperature}")
                        print("\n")

                    realtime_dict["humidity"] = humidity  # update realtime_dict
                    realtime_dict["temperature"] = temperature  # update realtime_dict
                    lock.release()
                    sleep(2)

            except KeyboardInterrupt:
                update = False

            except:
                print("Error while inserting dht11 data...")
                print(sys.exc_info()[0])
                print(sys.exc_info()[1])
    except:
        print(sys.exc_info()[0])
        print(sys.exc_info()[1])

def run_button_listener():

    button.when_pressed = analyse_face_for_physical_button
    pause()

# def lcd():
#    lcd = LCD()

#    dti = mktime(dt.now().timetuple())

#    while 1:
#        ndti = mktime(dt.now().timetuple())
#        if dti < ndti:
#            dti = ndti
#            lcd.clear()
#            lcd.text(dt.now().strftime('%b %d %Y'), 1)
#            lcd.text(dt.now().strftime('%H:%M:%S'), 2)
#            sleep(0.95)
#        else:
#            sleep(0.01)



'''
TELEGRAM BOT CODE 

def start_tele_bot():

    send_alert = False # prevent sending alert the first loop

    # Bot commands
    def respondToMsg(msg):
        command = msg['text']

        print('Got command: {}'.format(command))

        if command == 'onLED':
            bot.sendMessage(chat_id, ledOn())
        elif command =='offLED':
            bot.sendMessage(chat_id, ledOff())

    bot = telepot.Bot(my_bot_token)
    bot.message_loop(respondToMsg)
    print('Listening for RPi commands...')

    while True:
        # Unusual data alerts
        if int(realtime_dict["light"]) < 60 and send_alert:
            bot.sendMessage(chat_id, "Unusual light value detected. Current light value: {}".format(realtime_dict["light"]))
            # trigger buzzer for 5s if unusual data recorded
            buzzer.on()

        now = dt.now() # get current time

        ###### ALARM SYSTEM ##########
        # get time of set alarm (if alarm is set)
        if gobal_dict["alarm"] is not None:
            alarm_array = gobal_dict["alarm"].split(":")
            alarm_set = now.replace(hour=int(alarm_array[0]), minute=int(alarm_array[1]), second=int(alarm_array[2]), microsecond=0) 

            # if current time equal or exceed alarm time start actions
            if alarm_set <= now:
                start_time = time.time()
                seconds = 10

                # if alarm has not rang and light sensor value within threshold
                while not gobal_dict["rang"] and int(realtime_dict["light"]) < 100:

                    current_time = time.time()
                    elapsed_time = current_time - start_time

                    buzzer.on()
                    bot.sendMessage(chat_id, "Wake up! Alarm set for {} ringing".format(gobal_dict["alarm"]))
                    sleep(0.5)
                    buzzer.off()
                    buzzer.on()
                    bot.sendMessage(chat_id, "Wake up! Alarm set for {} ringing".format(gobal_dict["alarm"]))
                    sleep(0.5)
                    buzzer.off()

                    if elapsed_time > seconds:
                        gobal_dict["rang"] = True
                        gobal_dict["alarm"] = None
                        break

                gobal_dict["rang"] = True # disable alarm after alarm set exceed current time
                gobal_dict["alarm"] = None

        send_alert = True

        sleep(2)

        buzzer.off()
'''