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
- Hardware:
  --
- Operating System and packages
- Applications 
- Services 

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
