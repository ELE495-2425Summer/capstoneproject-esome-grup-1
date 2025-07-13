import socketio
import time
import json
import socket

SERVER_URL = "http://192.168.15.23:3000"
sio = socketio.Client() # Socket.IO istemcisi olusturuluyor

# global degisken - arac durumu
arac_aktif = False

# istemci server'a baglandiginda tetiklenir
@sio.event
def connect():
    print("Bağlantı sağlandı.")

# sunucu baglantisi kesildiginde tetiklenir
@sio.event
def disconnect():
    print("Bağlantı kesildi.")

# Araç kontrol komutlarını dinle
@sio.event
def arac_kontrol(data):
    global arac_aktif
    print(f"Araç kontrol komutu alındı: {data}")
    
    if data.get('durum') == 'ac':
        arac_aktif = True
        print("Araç AKTİF hale getirildi")
    elif data.get('durum') == 'kapat':
        arac_aktif = False
        print("Araç PASİF hale getirildi")

# arac aktifligini kontrol eden fonksiyon
def is_arac_aktif():
    return arac_aktif

# belirtilen sunucuya baglanilmaya calisilir, eger baglanti saglanilamazsa error mesaji ekrana basilir
try:
    sio.connect(SERVER_URL)
except Exception as e:
    print(f"Socket.IO bağlantı hatası: {e}")


# bu fonksiyon JSON formatindaki "data" verisini sunucuya gonderir 
def send_json_data(data):
    try:
        print(f"Emit ediliyor: {data}")
        
        # eger "data" icindeki verinin "type"i "arac_durumu" ise bu veriyi "arac_durumu_guncelle" isimli 
        # Socket.IO olayi icinde yayinlar 
        if data.get("type") == "arac_durumu": 
            sio.emit("arac_durumu_guncelle", data)

        # eger "data" icindeki verinin "type"i "arac_durumu" degil ise bu veriyi "veri_guncelle" isimli 
        # Socket.IO olayi icinde yayinlar
        else:
            sio.emit("veri_guncelle", data)

        print(f"mesaj")

    # gonderimde hata olursa hata mesaji basilir
    except Exception as e:
        print(f"Gönderim hatası: {e}")
