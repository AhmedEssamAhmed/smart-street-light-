#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"

const char* ssid     = "YOUR_WIFI_NAME";
const char* password = "YOUR_WIFI_PASSWORD";

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

#define FLASH_PIN          4
#define FLASH_CHANNEL      7

httpd_handle_t stream_httpd = NULL;

static esp_err_t jpg_handler(httpd_req_t *req) {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) { httpd_resp_send_500(req); return ESP_FAIL; }
  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
  esp_err_t res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  esp_camera_fb_return(fb);
  return res;
}

static esp_err_t car_handler(httpd_req_t *req) {
  Serial1.println("CAR");
  httpd_resp_send(req, "OK", HTTPD_RESP_USE_STRLEN);
  return ESP_OK;
}

static esp_err_t flash_on_handler(httpd_req_t *req) {
  ledcWrite(FLASH_CHANNEL, 80);
  httpd_resp_send(req, "Flash ON", HTTPD_RESP_USE_STRLEN);
  return ESP_OK;
}

static esp_err_t flash_off_handler(httpd_req_t *req) {
  ledcWrite(FLASH_CHANNEL, 0);
  httpd_resp_send(req, "Flash OFF", HTTPD_RESP_USE_STRLEN);
  return ESP_OK;
}

void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 80;
  config.max_uri_handlers = 8;
  httpd_uri_t jpg_uri = { .uri="/jpg", .method=HTTP_GET, .handler=jpg_handler, .user_ctx=NULL };
  httpd_uri_t car_uri = { .uri="/car", .method=HTTP_GET, .handler=car_handler, .user_ctx=NULL };
  httpd_uri_t flash_on_uri = { .uri="/flash/on", .method=HTTP_GET, .handler=flash_on_handler, .user_ctx=NULL };
  httpd_uri_t flash_off_uri = { .uri="/flash/off", .method=HTTP_GET, .handler=flash_off_handler, .user_ctx=NULL };
  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &jpg_uri);
    httpd_register_uri_handler(stream_httpd, &car_uri);
    httpd_register_uri_handler(stream_httpd, &flash_on_uri);
    httpd_register_uri_handler(stream_httpd, &flash_off_uri);
  }
}

void setup() {
  Serial.begin(115200);
  Serial1.begin(9600, SERIAL_8N1, 3, 1);  // RX=GPIO3, TX=GPIO1 -> Blue Pill PA10
  delay(500);

  ledcSetup(FLASH_CHANNEL, 5000, 8);
  ledcAttachPin(FLASH_PIN, FLASH_CHANNEL);
  ledcWrite(FLASH_CHANNEL, 0);

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk     = XCLK_GPIO_NUM;
  config.pin_pclk     = PCLK_GPIO_NUM;
  config.pin_vsync    = VSYNC_GPIO_NUM;
  config.pin_href     = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn     = PWDN_GPIO_NUM;
  config.pin_reset    = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size   = FRAMESIZE_QVGA;
  config.jpeg_quality = 12;
  config.fb_count     = 1;

  if (esp_camera_init(&config) != ESP_OK) {
    Serial.println("Camera init failed");
    while (true) delay(1000);
  }

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) { delay(500); }

  startCameraServer();
}

void loop() {
  delay(1000);
}
