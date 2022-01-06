import time
import sys
sys.path.append('./drive')
import SPI
import SSD1305
import requests
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from datetime import datetime
import subprocess
import argparse
from unidecode import unidecode

# add parser
parser = argparse.ArgumentParser()

parser.add_argument("-fint", "--fetch_interval", help="Fetch interval (in seconds)")
parser.add_argument("-nint", "--next_interval", help="How fast the pages should change? (in seconds)")
parser.add_argument("-stop", "--selected_stop", help="Type stop name if preffered")
parser.add_argument("-vehicle", "--selected_vehicle", help="Selected vehicle - tram or bus")

args = parser.parse_args()

# Raspberry Pi pin configuration:
RST = None
DC = 24
SPI_PORT = 0
SPI_DEVICE = 0
SHOW_PAGE = 0
SECONDS_COUNTER = 0
ERROR = False

# Mapping the names for the stop codes
dict = {}
dict['Starowislna'] = '358'
dict['Bienczycka'] = '867'
dict['Krowodrza Gorka'] = '63'
dict['Czerwone Maki'] = '3038'
dict['Rondo Czyzynskie'] = '408'

# get args from parser, if not available, take the defaults
try:
    if args.fetch_interval:
        if int(args.fetch_interval) < 30:
            raise ValueError
        FETCH_DATA_INTERVAL = int(args.fetch_interval)
    else:
        FETCH_DATA_INTERVAL = 60
except ValueError:
    print("Interval is invalid or too short!")
    sys.exit()

try:
    if args.next_interval:
        if int(args.next_interval) < 5:
            raise ValueError
        NEXT_PAGE_INTERVAL = int(args.next_interval)
    else:
        NEXT_PAGE_INTERVAL = 10 
except ValueError:
    print("Interval is invalid or too short!")
    sys.exit()

try:
    if args.selected_stop:
        if not dict[args.selected_stop]:
            raise KeyError
        SELECTED_STOP = args.selected_stop
    else:
        SELECTED_STOP = 'Bienczycka'
except KeyError:
    print("Selected stop name is invalid or not found in our database!")
    sys.exit()

try:
    if args.selected_vehicle:
        if args.selected_vehicle.lower()=="tram" or args.selected_vehicle.lower()=="bus" :
            SELECTED_VEHICLE = args.selected_vehicle.lower()
        else:
            raise KeyError
    else:
        SELECTED_VEHICLE = 'tram'

except KeyError:
    print("Selected vehicle name is invalid! Select bus or tram")
    sys.exit()

if (SELECTED_VEHICLE == 'tram'):
    URL = "http://www.ttss.krakow.pl/internetservice/services/passageInfo/stopPassages/stop?stop=" + dict[SELECTED_STOP]
else:
    URL = "http://91.223.13.70/internetservice/services/passageInfo/stopPassages/stop?stop=" + dict[SELECTED_STOP]

# 128x32 display with hardware SPI:
disp = SSD1305.SSD1305_128_32(rst=RST, dc=DC, spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz=8000000))

# Initialize library.
disp.begin()

# Clear display.
disp.clear()
disp.display()

# Create blank image for drawing.
width = disp.width
height = disp.height
image = Image.new('1', (width, height))
draw = ImageDraw.Draw(image)

# Draw a black filled box to clear the image.
draw.rectangle((0,0,width,height), outline=0, fill=0)

# Draw some shapes.
padding = 0
top = padding
bottom = height-padding
x = 0

# Some other nice fonts to try: http://www.dafont.com/bitmap.php
font = ImageFont.truetype('04B_08__.TTF',8)

def chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def requestData():
    global STOP_NAME, ERROR_MESSAGE
    try:
        r = requests.get(url = URL)
    except requests.exceptions.RequestException as e:
        displayError()
    
    data = r.json()

    # let's split the data into chunks of 2, because of the display capabilities.
    # later it is going to change the page view every n seconds in order to be able
    # to fully present the fetched data
    
    STOP_NAME = unidecode(str(data['stopName']))
    departures = chunks(data['actual'], 2)
    
    return STOP_NAME, list(departures)

def convertTime(time):
    if time:
        minutes = time.split()[0]
        if minutes == '0':
            return '>>>>>'
        else:
            if len(time.split()) > 1 and '%UNIT_MIN%' in time.split()[1]:
                return time.split()[0] + ' min'
            else:
                return time.split()[0]
    else:
        return 'i dont know :('

def convertDirection(direction):
    if len(direction) > 12:
        return unidecode(direction[:12] + '..')
    else:
        return unidecode(direction)


def printDeparture(departures): 
    global SHOW_PAGE, NEXT_PAGE_INTERVAL, SECONDS_COUNTER
    
    departures = list(departures)    
    if len(departures) > 0:
        if SECONDS_COUNTER % NEXT_PAGE_INTERVAL == 0:
            SHOW_PAGE+=1
            if SHOW_PAGE == len(departures):
                SHOW_PAGE = 0

        if(len(departures[SHOW_PAGE]) > 1):
            number = str(departures[SHOW_PAGE][1]['patternText'])
            direction = str(departures[SHOW_PAGE][1]['direction'])
            time = str(unidecode(departures[SHOW_PAGE][1]['mixedTime'])[:14])
            
            direction = convertDirection(direction)
            time = convertTime(time)

            draw.text((x, top+16),str(number), font=font, fill=255)
            draw.text((x+18, top+16),str(direction), font=font, fill=255)
            draw.text((x+(103-len(str(time))), top+16),str(time), font=font, fill=255)

        if(len(departures[SHOW_PAGE]) > 0):
            number = str(departures[SHOW_PAGE][0]['patternText'])
            direction = str(departures[SHOW_PAGE][0]['direction'])
            time = str(unidecode(departures[SHOW_PAGE][0]['mixedTime'])[:14])

            direction = convertDirection(direction)
            time = convertTime(time)

            draw.text((x, top+24),str(number), font=font, fill=255)
            draw.text((x+18, top+24),str(direction), font=font, fill=255)
            draw.text((x+(103-len(str(time))), top+24),str(time), font=font, fill=255)
    else:
        draw.text((x, top+16),str('Brak rozkladu :('), font=font, fill=255)

def displayError():
    while True:
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        draw.rectangle((0,0,width,height), outline=0, fill=0) 
        draw.text((x+88, top), str(current_time),  font=font, fill=255)  
        draw.text((x, top+16), "MPK API error", font=font, fill=255)
        disp.image(image)
        disp.display()
        time.sleep(1)

def main():
    global FETCH_DATA_INTERVAL, SECONDS_COUNTER, STOP_NAME, DEPARTURES, ERROR_MESSAGE

    STOP_NAME, DEPARTURES = requestData()
    
    while True: 
        SECONDS_COUNTER+=1
        draw.rectangle((0,0,width,height), outline=0, fill=0)   

        if SECONDS_COUNTER < 10:
            loading = ""
            for i in range(0, SECONDS_COUNTER):
                loading+="."
            draw.text((x, top), "MPK Stop Timetable" + loading,  font=font, fill=255)

            draw.text((x+65, top+24), "#psiecinski",  font=font, fill=255)
        
        else:
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")
        
            draw.text((x, top), convertDirection(STOP_NAME),  font=font, fill=255)
            draw.text((x+88, top),    str(current_time),  font=font, fill=255)

            if SECONDS_COUNTER % FETCH_DATA_INTERVAL == 0:
                STOP_NAME, DEPARTURES = requestData()
            printDeparture(DEPARTURES)


        # Display image.
        disp.image(image)
        disp.display()
        time.sleep(1)

main()
