# TOBB ETÜ ELE495 - Capstone Project

# Table of Contents
- [Introduction](#introduction)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Screenshots](#screenshots)
- [Acknowledgements](#acknowledgements)

## Introduction
This project, titled *"DOĞAL DİL İLE KONTROL EDİLEBİLEN OTONOM MİNİ ARAÇ"* (Voice-Controlled Autonomous Mini Vehicle), was developed as part of the 2024–2025 Summer ELE 495 Capstone Design Project(ELE495 Bitirme Tasarım Projesi) course.

The main objective of this project is to design a wheeled autonomous mini vehicle that can understand spoken natural Turkish commands and convert them into low-level movement instructions that it can execute. The vehicle uses a microphone and a speech-to-text (STT) system to capture voice commands from the user and sends the transcribed text to a large language model (LLM) for interpretation. The LLM parses the natural language and converts it into a sequence of basic movement commands (e.g., move forward, turn left, etc.).

These commands are then executed on the vehicle using onboard sensors and motor control logic. While performing these actions, the system provides natural-sounding Turkish spoken feedback to the user using the **Text-to-Speech (TTS) API**, enabling lifelike, expressive responses. The goal is to create a more human-like interaction by minimizing robotic speech patterns.

A typical usage scenario might include a user saying:  
*"Engel çıkana kadar düz git, sonra sola dön, 2 saniye ileri git, sağa dön."*  
The system records the command, processes it using STT and LLM modules, and executes the parsed instructions in order using motor drivers and sensor input. During execution, the system responds with real-time Turkish voice feedback such as *"İleri gidiyorum."* or *"Sola dönüyorum."*

## Features
### Hardware
  - OrangePi 4 LTS: [https://www.robotistan.com/orange-pi-4-lts-4gb](https://www.robotistan.com/orange-pi-4-lts-4gb)
  -  Arduino UNO R3: [https://www.robotistan.com/arduino-uno-r3-klon-usb-kablo-hediyeli-usb-chip-ch340?language=tr&h=424a5daa](https://www.robotistan.com/arduino-uno-r3-klon-usb-kablo-hediyeli-usb-chip-ch340?language=tr&h=424a5daa)
  -  4WD Robot Araba Platformu: [https://www.direnc.net/4wd-robot-araba-platform-4wd-smart-car](https://www.direnc.net/4wd-robot-araba-platform-4wd-smart-car)
  -  L298N Voltaj Regülatörlü Çift Motor Sürücü Kartı: [https://www.robotistan.com/l298n-voltaj-regulatorlu-cift-motor-surucu-karti](https://www.robotistan.com/l298n-voltaj-regulatorlu-cift-motor-surucu-karti)
  -  DAYTONA K9 Type-C Wireless Yaka Mikrofonu: [https://www.mediamarkt.com.tr/tr/product/_daytona-k9-type-c-wireless-yaka-mikrofonu-1224996.html](https://www.mediamarkt.com.tr/tr/product/_daytona-k9-type-c-wireless-yaka-mikrofonu-1224996.html)
  -  Mini Harici USB Stereo Hoparlör: [https://www.robotistan.com/raspberry-pi-icin-mini-harici-usb-stereo-hoparlor](https://www.robotistan.com/raspberry-pi-icin-mini-harici-usb-stereo-hoparlor)
  -  MPU6050 6 Eksenli Gyro ve Eğim Sensörü: [https://www.direnc.net/mpu6050-3-axis-gyro-ve-egim-sensoru](https://www.direnc.net/mpu6050-3-axis-gyro-ve-egim-sensoru)
  -  HC-SR04 Ultrasonik Mesafe Sensörü: [https://www.robocombo.com/Ultrasonik-Mesafe-Sensoru-HC-SR04,PR-1041.html](https://www.robocombo.com/Ultrasonik-Mesafe-Sensoru-HC-SR04,PR-1041.html)
  -  LG 18650 HG2 3000mAh Li-Ion Pil: [https://www.cimri.com/normal-sarj-edilebilir-piller/en-ucuz-lg-18650-hg2-3000mah-3-7v-20a-li-ion-sarj-edilebilir-pil-fiyatlari%2C1232320338?utm_source=chatgpt.com](https://www.cimri.com/normal-sarj-edilebilir-piller/en-ucuz-lg-18650-hg2-3000mah-3-7v-20a-li-ion-sarj-edilebilir-pil-fiyatlari%2C1232320338?utm_source=chatgpt.com)
  -  Ttec 2BB214UG 10.000mAh Powerbank: [https://www.teknosa.com/ttec-2bb214ug-recharger-pro-lcd-10000-mah-pd-30w-tasinabilir-hizli-sarj-aletipowerbank-uzay-grisi-p-125432432](https://www.teknosa.com/ttec-2bb214ug-recharger-pro-lcd-10000-mah-pd-30w-tasinabilir-hizli-sarj-aletipowerbank-uzay-grisi-p-125432432)
  -  Genel Markalar 18650 Tekli Lityum Ion Pil Yuvası: [https://www.trendyol.com/genel-markalar/18650-pil-yatagi-tekli-lityum-ion-pil-yuvasi-1-kanal-p-135522244?boutiqueId=61&merchantId=730358](https://www.trendyol.com/genel-markalar/18650-pil-yatagi-tekli-lityum-ion-pil-yuvasi-1-kanal-p-135522244?boutiqueId=61&merchantId=730358)
    
### Operating Systems and Packages
**Operating Systems:**
- **Orange Pi 4 LTS** runs a Linux-based Armbian operating system.
- **Arduino UNO** uses the Arduino platform with no full operating system (bare-metal programming in C/C++).
- **Development PC** uses Windows 11 for running the web server and interface.

**Packages:**

*Orange Pi Packages:*
- openai
- sounddevice
- scipy
- webrtcvad
- pyserial
- numpy
- flask
- python-socketio
- requests
- client_sender

*Interface Packages:*
- socketio
- time
- json

*Arduino Packages:*
- Wire.h
- MPU6050_light.h
- ArduinoJson.h
- math.h

### Applications
- **Voice-Controlled Home Assistant Robots:** The system can serve as a foundation for smart robots that assist users in domestic environments through spoken language. 
### Services 

## Installation
Describe the steps required to install and set up the project. Include any prerequisites, dependencies, and commands needed to get the project running.

```bash
# Example commands
git clone https://github.com/username/project-name.git
cd project-name
```

## Usage
Provide instructions and examples on how to use the project. Include code snippets or screenshots where applicable.

## Screenshots
Include screenshots of the project in action to give a visual representation of its functionality. You can also add videos of running project to YouTube and give a reference to it here. 

## Acknowledgements
Give credit to those who have contributed to the project or provided inspiration. Include links to any resources or tools used in the project.

[Contributor 1](https://github.com/user1)
[Resource or Tool](https://www.nvidia.com)
