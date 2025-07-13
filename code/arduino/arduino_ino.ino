#include <Wire.h>                 // I2C haberleşme kütüphanesi
#include <MPU6050_light.h>        // MPU6050 IMU modülü için hafif kütüphane
#include <ArduinoJson.h>          // Seri haberleşmeden gelen JSON komutları ayrıştırmak için
#include <math.h>                 // Matematiksel işlemler (örn. abs, map, trigonometrik fonk.)

// === Motor Sürücü Pin Tanımlamaları (L298N H-Köprüsü) ===
#define IN1 7    // Sol motor ileri
#define IN2 6    // Sol motor geri
#define ENA 5    // Sol motor PWM kontrolü
#define IN3 8    // Sağ motor ileri
#define IN4 9    // Sağ motor geri
#define ENB 10   // Sağ motor PWM kontrolü

// === Ultrasonik Sensör Pinleri ===
#define FRONT_TRIG_PIN 13
#define FRONT_ECHO_PIN 11
#define BACK_TRIG_PIN 3
#define BACK_ECHO_PIN 2

// === Sistem Sabitleri ===
const int DRIVE_PWM = 120;              // İleri/geri sürüşte temel PWM değeri
const int MIN_TURN_PWM = 90;            // Dönüş sırasında minimum PWM
const int MAX_TURN_PWM = 110;           // Dönüş sırasında maksimum PWM
const float ANGLE_TOLERANCE = 3.0;      // Dönüş toleransı (derece cinsinden)
const unsigned long CMD_TIMEOUT_MS = 3000;     // Komut zaman aşımı süresi
const unsigned long TURN_TIMEOUT_MS = 8000;    // Dönüş zaman aşımı süresi
const int PWM_LEFT_CORRECTION = 0;             // Sol motor için PWM düzeltmesi (denge amaçlı)
const int PWM_RIGHT_CORRECTION = 0;            // Sağ motor için PWM düzeltmesi

// === Global Değişkenler ===
MPU6050 mpu(Wire);         // MPU6050 IMU nesnesi
float initialYaw = 0;      // Başlangıç yönü (Z ekseni)
String incomingBuffer;     // JSON komutlarının tutulduğu tampon
unsigned long cmdStartTime = 0;  // Komut alımının başladığı zaman

// === Fonksiyon Prototipleri ===
void setupPins();
void setupMPU();
void readSerialCommand();
void handleCommand(JsonDocument &doc);
void turnLeft(float angle_deg);
void turnRight(float angle_deg);
void stopMotors();
long measureDistanceCM(int trigPin, int echoPin);
void moveUntilObstacle(int trigPin, int echoPin, bool forward);
void moveUntilTimedOrObstacle(int trigPin, int echoPin, bool forward, int duration_s);
long getAverageDistance(int trigPin, int echoPin, int numSamples = 5);

void setup() {
  Serial.begin(115200);     // Seri portu başlat
  while (!Serial);          // Seri bağlantı hazır olana kadar bekle
  setupPins();              // Pin yönlendirmelerini ayarla
  Wire.begin();             // I2C başlat
  Wire.setWireTimeout(3000, true);  // I2C zaman aşımı
  setupMPU();               // MPU6050 başlat ve kalibre et
  Serial.println("{\"status\":\"ready\"}"); // Hazır mesajı
}

void loop() {
  mpu.update();             // MPU verilerini güncelle
  readSerialCommand();      // Seri porttan komut oku
}

// Motor, sensör ve PWM pinlerini OUTPUT/INPUT olarak yapılandırır
void setupPins() {
  pinMode(ENA, OUTPUT); pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(ENB, OUTPUT); pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  pinMode(FRONT_TRIG_PIN, OUTPUT); pinMode(FRONT_ECHO_PIN, INPUT);
  pinMode(BACK_TRIG_PIN, OUTPUT); pinMode(BACK_ECHO_PIN, INPUT);
}

// Açının -180 ila +180 aralığında normalize edilmesi
float normalizeAngle(float angle) {
  while (angle > 180.0) angle -= 360.0;
  while (angle < -180.0) angle += 360.0;
  return angle;
}

// MPU6050 başlatma ve sıfırlama
void setupMPU() {
  delay(1000);
  mpu.begin();                // MPU başlat
  mpu.calcGyroOffsets();      // Kalibrasyon
  delay(1000);
  mpu.update();               // İlk veri güncellemesi
  initialYaw = mpu.getAngleZ(); // İlk yön kaydı
}

// Seri porttan gelen JSON komutlarını okur ve işler
void readSerialCommand() {
  if (Serial.available()) {
    if (incomingBuffer.length() == 0)
      cmdStartTime = millis();

    while (Serial.available()) {
      char c = Serial.read();
      incomingBuffer += c;

      if (c == '\n') {
        StaticJsonDocument<256> doc;
        DeserializationError err = deserializeJson(doc, incomingBuffer);
        if (!err) handleCommand(doc);  // Komutu işle
        incomingBuffer = "";
        return;
      }

      // Komut zaman aşımı kontrolü
      if (millis() - cmdStartTime > CMD_TIMEOUT_MS) {
        incomingBuffer = "";
        return;
      }
    }
  }
}

// Gelen JSON komutlarını karşılık gelen işlemlere yönlendirir
void handleCommand(JsonDocument &doc) {
  const char* cmd = doc["cmd"];
  bool hasSure = doc.containsKey("sure");
  bool hasAci = doc.containsKey("aci") || doc.containsKey("açı");

  if (strcmp(cmd, "FORWARD") == 0) {
    if (hasSure)
      moveUntilTimedOrObstacle(FRONT_TRIG_PIN, FRONT_ECHO_PIN, true, doc["sure"]);
    else
      moveUntilObstacle(FRONT_TRIG_PIN, FRONT_ECHO_PIN, true);

  } else if (strcmp(cmd, "BACKWARD") == 0) {
    if (hasSure)
      moveUntilTimedOrObstacle(BACK_TRIG_PIN, BACK_ECHO_PIN, false, doc["sure"]);
    else
      moveUntilObstacle(BACK_TRIG_PIN, BACK_ECHO_PIN, false);

  } else if (strcmp(cmd, "LEFT") == 0) {
    float angle = hasAci ? doc["aci"].as<float>()  : 90;
    turnLeft(angle);

  } else if (strcmp(cmd, "RIGHT") == 0) {
    float angle = hasAci ? doc["aci"].as<float>()  : 90;
    turnRight(angle);

  } else if (strcmp(cmd, "STOP") == 0) {
    stopMotors();
    if (hasSure)
      delay(doc["sure"].as<int>() * 1000);
  } else {
    Serial.println("{\"error\":\"unknown_cmd\"}");
  }

  // Komut onayı
  Serial.print("{\"ack\":\""); Serial.print(cmd); Serial.println("\"}");
}

// Belirtilen süre boyunca ya da engel tespit edilene kadar hareket eder
void moveUntilTimedOrObstacle(int trigPin, int echoPin, bool forward, int duration_s) {
  unsigned long start = millis();
  unsigned long duration = duration_s * 1000;
  int basePwm = constrain(DRIVE_PWM, 100, 200);

  // Yön belirleme
  if (forward) {
    digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
    digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
  } else {
    digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
    digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
  }

  // Hareket süresi ve engel kontrolü
  while ((millis() - start) < duration) {
    long distance = getAverageDistance(trigPin, echoPin);
    if (distance > 0 && distance <= 30) break;

    float progress = (float)(millis() - start) / duration;
    int pwm = basePwm * (1.0 - 0.7 * progress);  // PWM düşürerek duruşu yumuşatma

    analogWrite(ENA, pwm + PWM_LEFT_CORRECTION);
    analogWrite(ENB, pwm + PWM_RIGHT_CORRECTION);
    delay(100);
  }

  stopMotors();
}

// Engel algılanana veya zaman aşımına kadar ileri/geri hareket
void moveUntilObstacle(int trigPin, int echoPin, bool forward) {
  const int basePwm = constrain(DRIVE_PWM, 100, 200);
  const int stopDistance = 70;
  unsigned long startTime = millis();

  if (forward) {
    digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
    digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
  } else {
    digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
    digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
  }

  while (true) {
    long distance = getAverageDistance(trigPin, echoPin);
    if (distance > 0 && distance <= stopDistance) break;
    if (millis() - startTime > 8000) break;

    int pwm = basePwm;
    if (distance > 0 && distance < 60) {
      pwm = map(distance, stopDistance, 50, 70, basePwm);
      pwm = constrain(pwm, 55, basePwm);
    }

    analogWrite(ENA, pwm + PWM_LEFT_CORRECTION);
    analogWrite(ENB, pwm + PWM_RIGHT_CORRECTION);
    delay(40);
  }

  stopMotors();
}

// Tek seferlik ultrasonik ölçüm (cm cinsinden)
long measureDistanceCM(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW); delayMicroseconds(2);
  digitalWrite(trigPin, HIGH); delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duration = pulseIn(echoPin, HIGH, 30000);
  return duration * 0.034 / 2;
}

// Ortalama mesafe hesaplamak için çoklu ölçüm alır
long getAverageDistance(int trigPin, int echoPin, int numSamples) {
  long total = 0;
  int validCount = 0;

  for (int i = 0; i < numSamples; i++) {
    long d = measureDistanceCM(trigPin, echoPin);
    if (d > 0 && d < 300) {
      total += d;
      validCount++;
    }
    delay(10);
  }

  if (validCount == 0) return -1;
  return total / validCount;
}

// Belirtilen açı kadar sola dönme işlemi (MPU6050 ile açı kontrolü)
void turnLeft(float angle_deg) {
  if (angle_deg <= 0) angle_deg = 90.0;

  mpu.update();
  float startYaw = mpu.getAngleZ();
  float rotated = normalizeAngle(startYaw - mpu.getAngleZ());
  unsigned long start = millis();

  while (millis() - start < TURN_TIMEOUT_MS) {
    mpu.update();
    rotated = normalizeAngle(startYaw - mpu.getAngleZ());
    if (abs(rotated) >= angle_deg - ANGLE_TOLERANCE) break;

    float progress = abs(rotated) / angle_deg;
    int pwm = map(progress * 100, 0, 100, MAX_TURN_PWM, MIN_TURN_PWM);
    pwm = constrain(pwm, MIN_TURN_PWM, MAX_TURN_PWM);

    digitalWrite(IN1, LOW); digitalWrite(IN2, HIGH);
    digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
    analogWrite(ENA, pwm);
    analogWrite(ENB, pwm);

    delay(20);
  }

  stopMotors();
  delay(10);
  mpu.update();
  initialYaw = mpu.getAngleZ();  // Yeni yön güncelle
}

// Belirtilen açı kadar sağa dönme işlemi (MPU6050 ile açı kontrolü)
void turnRight(float angle_deg) {
  if (angle_deg <= 0) angle_deg = 90.0;

  mpu.update();
  float startYaw = mpu.getAngleZ();
  float rotated = normalizeAngle(mpu.getAngleZ() - startYaw);
  unsigned long start = millis();

  while (millis() - start < TURN_TIMEOUT_MS) {
    mpu.update();
    rotated = normalizeAngle(mpu.getAngleZ() - startYaw);
    if (abs(rotated) >= angle_deg - ANGLE_TOLERANCE) break;

    float progress = abs(rotated) / angle_deg;
    int pwm = map(progress * 100, 0, 100, MAX_TURN_PWM, MIN_TURN_PWM);
    pwm = constrain(pwm, MIN_TURN_PWM, MAX_TURN_PWM);

    digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
    digitalWrite(IN3, LOW); digitalWrite(IN4, HIGH);
    analogWrite(ENA, pwm);
    analogWrite(ENB, pwm);

    delay(10);
  }

  stopMotors();
  delay(10);
  mpu.update();
  initialYaw = mpu.getAngleZ();  // Yeni yön güncelle
}

// Tüm motorları durdurur (acil durdurma)
void stopMotors() {
  digitalWrite(IN1, HIGH); digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, HIGH);
  analogWrite(ENA, 0);
  analogWrite(ENB, 0);
}
