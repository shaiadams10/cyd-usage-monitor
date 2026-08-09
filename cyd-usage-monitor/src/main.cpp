#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <SPI.h>
#include <TFT_eSPI.h>
#include <XPT2046_Touchscreen.h>
#include <lvgl.h>
#include "secrets.h"
#include "mascot_img.h"

// Touch controller pins for CYD (ESP32-2432S028R)
#define XPT2046_IRQ 36
#define XPT2046_MOSI 32
#define XPT2046_MISO 39
#define XPT2046_CLK 25
#define XPT2046_CS 33

// Onboard RGB LED
#define LED_RED 4
#define LED_GREEN 16
#define LED_BLUE 17

TFT_eSPI tft = TFT_eSPI();
// TFT_eSPI uses VSPI by default. The touch controller has its own CYD pins,
// so place it on HSPI to avoid registering the same ESP32 APB callback twice.
SPIClass touchSPI = SPIClass(HSPI);
XPT2046_Touchscreen touch(XPT2046_CS, XPT2046_IRQ);
WiFiClient telemetryPlainClient;

// LVGL buffer
static lv_disp_draw_buf_t draw_buf;
static lv_color_t buf[320 * 30];

unsigned long lastFetchTime = 0;
// The host collector refreshes CLI data every few minutes.  A short local-LAN
// poll makes a dashboard "Show" selection visible on the physical CYD within
// three seconds, without triggering another provider CLI invocation.
const unsigned long FETCH_INTERVAL = 3000;
const size_t MAX_TELEMETRY_BYTES = 16384;
const unsigned long TELEMETRY_CONNECT_TIMEOUT_MS = 3000;
const unsigned long TELEMETRY_READ_TIMEOUT_MS = 5000;
static volatile bool nextAccountRequested = false;

// Dashboard Screen & Widgets
static lv_obj_t *scr_dashboard;

// Header Widgets
static lv_obj_t *header_img;
static lv_obj_t *lbl_ag_mascot;
static lv_obj_t *lbl_account_name;
static lv_obj_t *btn_next_account;
static lv_obj_t *lbl_next_icon;

// Card 1: Primary Quota (Weekly / Monthly Limit)
static lv_obj_t *card_primary;
static lv_obj_t *lbl_primary_val;
static lv_obj_t *lbl_primary_tag;
static lv_obj_t *bar_primary;
static lv_obj_t *lbl_primary_warn;
static lv_obj_t *lbl_primary_sub;

// Card 2: Extra Credits & Server Details
static lv_obj_t *card_details;
static lv_obj_t *lbl_extra_credits;
static lv_obj_t *lbl_server_status;

// Dedicated collector-error screen. It replaces quota widgets when the server
// deliberately reports unavailable/stale telemetry.
static lv_obj_t *card_error;
static lv_obj_t *lbl_error_title;
static lv_obj_t *lbl_error_detail;

// --- Antigravity 2x2 Grid Layout Objects ---
static lv_obj_t *lbl_col_gemini;
static lv_obj_t *lbl_col_claude;

static lv_obj_t *box_gemini_5h;
static lv_obj_t *lbl_g5_val;
static lv_obj_t *bar_g5;
static lv_obj_t *lbl_g5_sub;

static lv_obj_t *box_gemini_wk;
static lv_obj_t *lbl_gw_val;
static lv_obj_t *bar_gw;
static lv_obj_t *lbl_gw_sub;

static lv_obj_t *box_claude_5h;
static lv_obj_t *lbl_c5_val;
static lv_obj_t *bar_c5;
static lv_obj_t *lbl_c5_sub;

static lv_obj_t *box_claude_wk;
static lv_obj_t *lbl_cw_val;
static lv_obj_t *bar_cw;
static lv_obj_t *lbl_cw_sub;

// Footer Ticker
static lv_obj_t *lbl_ticker;

String accountName = "ChatGPT User";
String extraCredits = "None";
String prefetchedTelemetryPayload;

void fetchQuotaData();
void showTelemetryError(const String &detail);

bool isPrivateLanTelemetryUrl(const String &url) {
    if (!url.startsWith("http://")) {
        return false;
    }
    const int authorityStart = 7;
    int authorityEnd = url.indexOf('/', authorityStart);
    if (authorityEnd < 0) {
        authorityEnd = url.length();
    }
    String host = url.substring(authorityStart, authorityEnd);
    const int portSeparator = host.indexOf(':');
    if (portSeparator >= 0) {
        host = host.substring(0, portSeparator);
    }
    unsigned int a, b, c, d;
    char trailing;
    if (sscanf(host.c_str(), "%u.%u.%u.%u%c", &a, &b, &c, &d, &trailing) != 4 ||
        a > 255 || b > 255 || c > 255 || d > 255) {
        return false;
    }
    return a == 10 || (a == 172 && b >= 16 && b <= 31) || (a == 192 && b == 168);
}

bool beginTelemetryRequest(HTTPClient &http, WiFiClient &client, const String &url) {
    if (!isPrivateLanTelemetryUrl(url)) {
        showTelemetryError("Device URL must use HTTP with a private LAN IPv4 address.");
        return false;
    }
    return http.begin(client, url);
}

void addTelemetryAuth(HTTPClient &http) {
#ifdef TELEMETRY_API_TOKEN
    if (String(TELEMETRY_API_TOKEN).length() > 0) {
        http.addHeader("Authorization", "Bearer " + String(TELEMETRY_API_TOKEN));
    }
#endif
}

void triggerNextAccount() {
    Serial.println("[ACTION] Switching to Next Account...");
    digitalWrite(LED_BLUE, LOW);

    if (WiFi.status() == WL_CONNECTED) {
        HTTPClient http;
        String nextUrl = String(TELEMETRY_SERVER_URL);
        nextUrl.replace("/api/v1/cyd-status", "/api/v1/next-account");
        if (!beginTelemetryRequest(http, telemetryPlainClient, nextUrl)) {
            digitalWrite(LED_BLUE, HIGH);
            return;
        }
        http.setReuse(true);
        http.setConnectTimeout(TELEMETRY_CONNECT_TIMEOUT_MS);
        http.setTimeout(TELEMETRY_READ_TIMEOUT_MS);
        addTelemetryAuth(http);
        int response = http.GET();
        if (response >= 200 && response < 300) {
            // The server returns the newly selected display state. Reuse that
            // payload directly instead of issuing a second HTTP request.
            prefetchedTelemetryPayload = http.getString();
            http.end();
            fetchQuotaData();
        } else if (response == HTTP_CODE_UNAUTHORIZED) {
            http.end();
            showTelemetryError("Device token was rejected by the monitor server.");
        } else if (response < 0) {
            Serial.printf("[NET] LAN request failed: HTTPClient=%d (%s)\n",
                          response, HTTPClient::errorToString(response).c_str());
            http.end();
            showTelemetryError("Local monitor connection failed. Check LAN address and server.");
        } else {
            http.end();
            showTelemetryError("Account switch failed with HTTP " + String(response) + ".");
        }
    }

    digitalWrite(LED_BLUE, HIGH);
}

/* Display Flushing Callback for LVGL */
void my_disp_flush(lv_disp_drv_t *disp_drv, const lv_area_t *area, lv_color_t *color_p) {
    uint32_t w = (area->x2 - area->x1 + 1);
    uint32_t h = (area->y2 - area->y1 + 1);

    tft.startWrite();
    tft.setAddrWindow(area->x1, area->y1, w, h);
    tft.pushColors((uint16_t *)&color_p->full, w * h, true);
    tft.endWrite();

    lv_disp_flush_ready(disp_drv);
}

/* Touch Input Callback */
void my_touchpad_read(lv_indev_drv_t *indev_driver, lv_indev_data_t *data) {
    if (millis() < 3000) {
        data->state = LV_INDEV_STATE_REL;
        return;
    }

    if (touch.touched()) {
        TS_Point p = touch.getPoint();
        if (p.z > 200) {
            data->state = LV_INDEV_STATE_PR;
            data->point.x = constrain(map(p.x, 200, 3700, 0, 319), 0, 319);
            data->point.y = constrain(map(p.y, 240, 3800, 0, 239), 0, 239);

            return;
        }
    }

    data->state = LV_INDEV_STATE_REL;
}

void nextAccountButtonEvent(lv_event_t *event) {
    if (lv_event_get_code(event) == LV_EVENT_CLICKED) {
        nextAccountRequested = true;
    }
}

void showTelemetryError(const String &detail) {
    lv_obj_add_flag(card_primary, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(card_details, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(lbl_col_gemini, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(lbl_col_claude, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(box_gemini_5h, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(box_gemini_wk, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(box_claude_5h, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(box_claude_wk, LV_OBJ_FLAG_HIDDEN);
    lv_obj_add_flag(lbl_ticker, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(card_error, LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(lbl_account_name, "Usage unavailable");
    lv_label_set_text(lbl_error_detail, detail.c_str());
    lv_obj_set_style_text_color(lbl_next_icon, lv_color_hex(0xEF4444), LV_PART_MAIN);
}

void buildDashboardUI() {
    scr_dashboard = lv_obj_create(NULL);
    lv_obj_set_style_bg_color(scr_dashboard, lv_color_hex(0x09090B), LV_PART_MAIN);
    lv_obj_set_style_pad_all(scr_dashboard, 0, LV_PART_MAIN);

    // --- Header Section ---
    header_img = lv_img_create(scr_dashboard);
    lv_img_set_src(header_img, &mascot_img);
    lv_obj_set_pos(header_img, 6, 3);

    lbl_ag_mascot = lv_label_create(scr_dashboard);
    lv_label_set_text(lbl_ag_mascot, "🚀");
    lv_obj_set_style_text_font(lbl_ag_mascot, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_set_pos(lbl_ag_mascot, 6, 4);
    lv_obj_add_flag(lbl_ag_mascot, LV_OBJ_FLAG_HIDDEN);

    lbl_account_name = lv_label_create(scr_dashboard);
    lv_label_set_text(lbl_account_name, "Loading Account...");
    lv_obj_set_style_text_color(lbl_account_name, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_account_name, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_set_size(lbl_account_name, 246, 24);
    lv_label_set_long_mode(lbl_account_name, LV_LABEL_LONG_DOT);
    lv_obj_set_pos(lbl_account_name, 36, 4);

    btn_next_account = lv_btn_create(scr_dashboard);
    lv_obj_set_size(btn_next_account, 28, 26);
    lv_obj_set_pos(btn_next_account, 290, 1);
    lv_obj_set_style_radius(btn_next_account, 6, LV_PART_MAIN);
    lv_obj_set_style_bg_color(btn_next_account, lv_color_hex(0x17212A), LV_PART_MAIN);
    lv_obj_set_style_border_color(btn_next_account, lv_color_hex(0x334155), LV_PART_MAIN);
    lv_obj_set_style_border_width(btn_next_account, 1, LV_PART_MAIN);
    lv_obj_set_style_pad_all(btn_next_account, 0, LV_PART_MAIN);
    lv_obj_add_event_cb(btn_next_account, nextAccountButtonEvent, LV_EVENT_CLICKED, NULL);
    lbl_next_icon = lv_label_create(btn_next_account);
    lv_label_set_text(lbl_next_icon, LV_SYMBOL_NEXT);
    lv_obj_set_style_text_color(lbl_next_icon, lv_color_hex(0x10B981), LV_PART_MAIN);
    lv_obj_center(lbl_next_icon);

    // --- ChatGPT Card 1: Primary Quota ---
    card_primary = lv_obj_create(scr_dashboard);
    lv_obj_set_size(card_primary, 312, 122);
    lv_obj_set_pos(card_primary, 4, 30);
    lv_obj_set_style_bg_color(card_primary, lv_color_hex(0x18181B), LV_PART_MAIN);
    lv_obj_set_style_border_color(card_primary, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_border_width(card_primary, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(card_primary, 12, LV_PART_MAIN);
    lv_obj_set_style_pad_all(card_primary, 8, LV_PART_MAIN);

    lbl_primary_val = lv_label_create(card_primary);
    lv_label_set_text(lbl_primary_val, "0%");
    lv_obj_set_style_text_color(lbl_primary_val, lv_color_hex(0x10B981), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_primary_val, &lv_font_montserrat_32, LV_PART_MAIN);
    lv_obj_set_pos(lbl_primary_val, 6, 2);

    lv_obj_t *badge1 = lv_obj_create(card_primary);
    lv_obj_set_size(badge1, 115, 24);
    lv_obj_align(badge1, LV_ALIGN_TOP_RIGHT, 0, -2);
    lv_obj_set_style_bg_color(badge1, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_border_width(badge1, 0, LV_PART_MAIN);
    lv_obj_set_style_radius(badge1, 10, LV_PART_MAIN);
    lv_obj_set_style_pad_all(badge1, 0, LV_PART_MAIN);

    lbl_primary_tag = lv_label_create(badge1);
    lv_label_set_text(lbl_primary_tag, "Usage Limit");
    lv_obj_set_style_text_color(lbl_primary_tag, lv_color_hex(0xE4E4E7), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_primary_tag, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_center(lbl_primary_tag);

    bar_primary = lv_bar_create(card_primary);
    lv_obj_set_size(bar_primary, 296, 14);
    lv_obj_set_pos(bar_primary, 4, 52);
    lv_bar_set_range(bar_primary, 0, 100);
    lv_bar_set_value(bar_primary, 0, LV_ANIM_ON);
    lv_obj_set_style_bg_color(bar_primary, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_border_color(bar_primary, lv_color_hex(0x3F3F46), LV_PART_MAIN);
    lv_obj_set_style_border_width(bar_primary, 1, LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_primary, lv_color_hex(0x10B981), LV_PART_INDICATOR);
    lv_obj_set_style_radius(bar_primary, 6, LV_PART_MAIN);
    lv_obj_set_style_radius(bar_primary, 6, LV_PART_INDICATOR);

    lbl_primary_warn = lv_label_create(card_primary);
    lv_label_set_text(lbl_primary_warn, "100% QUOTA EXHAUSTED");
    lv_obj_set_style_text_color(lbl_primary_warn, lv_color_hex(0xF43F5E), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_primary_warn, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_align_to(lbl_primary_warn, bar_primary, LV_ALIGN_CENTER, 0, 0);
    lv_obj_add_flag(lbl_primary_warn, LV_OBJ_FLAG_HIDDEN);

    lbl_primary_sub = lv_label_create(card_primary);
    lv_label_set_text(lbl_primary_sub, "100% left");
    lv_obj_set_style_text_color(lbl_primary_sub, lv_color_hex(0x10B981), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_primary_sub, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_pos(lbl_primary_sub, 6, 80);

    // --- ChatGPT Card 2: Footer / Credits ---
    card_details = lv_obj_create(scr_dashboard);
    lv_obj_set_size(card_details, 312, 60);
    lv_obj_set_pos(card_details, 4, 160);
    lv_obj_set_style_bg_color(card_details, lv_color_hex(0x18181B), LV_PART_MAIN);
    lv_obj_set_style_border_color(card_details, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_border_width(card_details, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(card_details, 10, LV_PART_MAIN);
    lv_obj_set_style_pad_all(card_details, 8, LV_PART_MAIN);

    lbl_extra_credits = lv_label_create(card_details);
    lv_label_set_recolor(lbl_extra_credits, true);
    lv_label_set_text(lbl_extra_credits, "Credits: #38bdf8 None#");
    lv_obj_set_style_text_color(lbl_extra_credits, lv_color_hex(0xE4E4E7), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_extra_credits, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_pos(lbl_extra_credits, 6, 12);

    lbl_server_status = lv_label_create(card_details);
    lv_label_set_text(lbl_server_status, "ChatGPT Plus");
    lv_obj_set_style_text_color(lbl_server_status, lv_color_hex(0x10B981), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_server_status, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_align(lbl_server_status, LV_ALIGN_TOP_RIGHT, -6, 12);

    // --- Collector Error Screen ---
    card_error = lv_obj_create(scr_dashboard);
    lv_obj_set_size(card_error, 312, 154);
    lv_obj_set_pos(card_error, 4, 48);
    lv_obj_set_style_bg_color(card_error, lv_color_hex(0x211316), LV_PART_MAIN);
    lv_obj_set_style_border_color(card_error, lv_color_hex(0xF43F5E), LV_PART_MAIN);
    lv_obj_set_style_border_width(card_error, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(card_error, 12, LV_PART_MAIN);
    lv_obj_set_style_pad_all(card_error, 14, LV_PART_MAIN);
    lbl_error_title = lv_label_create(card_error);
    lv_label_set_text(lbl_error_title, "Usage unavailable");
    lv_obj_set_style_text_color(lbl_error_title, lv_color_hex(0xF43F5E), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_error_title, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_set_pos(lbl_error_title, 0, 6);
    lbl_error_detail = lv_label_create(card_error);
    lv_label_set_text(lbl_error_detail, "Waiting for the CLI collector.");
    lv_obj_set_style_text_color(lbl_error_detail, lv_color_hex(0xF4D7DA), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_error_detail, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_size(lbl_error_detail, 276, 95);
    lv_label_set_long_mode(lbl_error_detail, LV_LABEL_LONG_WRAP);
    lv_obj_set_pos(lbl_error_detail, 0, 43);
    lv_obj_add_flag(card_error, LV_OBJ_FLAG_HIDDEN);

    // ====================================================
    // --- ANTIGRAVITY 2x2 GRID LAYOUT ELEMENTS ---
    // ====================================================

    lbl_col_gemini = lv_label_create(scr_dashboard);
    lv_label_set_text(lbl_col_gemini, "Gemini Models");
    lv_obj_set_style_text_color(lbl_col_gemini, lv_color_hex(0x2563EB), LV_PART_MAIN); // Deep Royal Blue
    lv_obj_set_style_text_font(lbl_col_gemini, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_pos(lbl_col_gemini, 2, 28);
    lv_obj_add_flag(lbl_col_gemini, LV_OBJ_FLAG_HIDDEN);

    lbl_col_claude = lv_label_create(scr_dashboard);
    lv_label_set_text(lbl_col_claude, "Claude Models");
    lv_obj_set_style_text_color(lbl_col_claude, lv_color_hex(0xF97316), LV_PART_MAIN); // Anthropic Orange
    lv_obj_set_style_text_font(lbl_col_claude, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_pos(lbl_col_claude, 160, 28);
    lv_obj_add_flag(lbl_col_claude, LV_OBJ_FLAG_HIDDEN);

    // Box 1: Gemini 5H
    box_gemini_5h = lv_obj_create(scr_dashboard);
    lv_obj_set_size(box_gemini_5h, 158, 88);
    lv_obj_set_pos(box_gemini_5h, 0, 48);
    lv_obj_set_style_bg_color(box_gemini_5h, lv_color_hex(0x18181B), LV_PART_MAIN);
    lv_obj_set_style_border_color(box_gemini_5h, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_border_width(box_gemini_5h, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(box_gemini_5h, 8, LV_PART_MAIN);
    lv_obj_set_style_pad_all(box_gemini_5h, 6, LV_PART_MAIN);
    lv_obj_add_flag(box_gemini_5h, LV_OBJ_FLAG_HIDDEN);

    lv_obj_t *lbl_g5_t = lv_label_create(box_gemini_5h);
    lv_label_set_text(lbl_g5_t, "5H Limit");
    lv_obj_set_style_text_color(lbl_g5_t, lv_color_hex(0x3B82F6), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_g5_t, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_g5_t, 4, 4);

    lbl_g5_val = lv_label_create(box_gemini_5h);
    lv_label_set_text(lbl_g5_val, "78%");
    lv_obj_set_style_text_color(lbl_g5_val, lv_color_hex(0x3B82F6), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_g5_val, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_align(lbl_g5_val, LV_ALIGN_TOP_RIGHT, -4, 2);

    bar_g5 = lv_bar_create(box_gemini_5h);
    lv_obj_set_size(bar_g5, 144, 10);
    lv_obj_set_pos(bar_g5, 4, 32);
    lv_bar_set_range(bar_g5, 0, 100);
    lv_obj_set_style_bg_color(bar_g5, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_g5, lv_color_hex(0x2563EB), LV_PART_INDICATOR);
    lv_obj_set_style_radius(bar_g5, 5, LV_PART_MAIN);
    lv_obj_set_style_radius(bar_g5, 5, LV_PART_INDICATOR);

    lbl_g5_sub = lv_label_create(box_gemini_5h);
    lv_label_set_text(lbl_g5_sub, "Refresh in: 4h 31m");
    lv_obj_set_style_text_color(lbl_g5_sub, lv_color_hex(0x94A3B8), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_g5_sub, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_g5_sub, 4, 52);

    // Box 2: Gemini Weekly
    box_gemini_wk = lv_obj_create(scr_dashboard);
    lv_obj_set_size(box_gemini_wk, 158, 88);
    lv_obj_set_pos(box_gemini_wk, 0, 142);
    lv_obj_set_style_bg_color(box_gemini_wk, lv_color_hex(0x18181B), LV_PART_MAIN);
    lv_obj_set_style_border_color(box_gemini_wk, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_border_width(box_gemini_wk, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(box_gemini_wk, 8, LV_PART_MAIN);
    lv_obj_set_style_pad_all(box_gemini_wk, 6, LV_PART_MAIN);
    lv_obj_add_flag(box_gemini_wk, LV_OBJ_FLAG_HIDDEN);

    lv_obj_t *lbl_gw_t = lv_label_create(box_gemini_wk);
    lv_label_set_text(lbl_gw_t, "Weekly");
    lv_obj_set_style_text_color(lbl_gw_t, lv_color_hex(0x3B82F6), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_gw_t, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_gw_t, 4, 4);

    lbl_gw_val = lv_label_create(box_gemini_wk);
    lv_label_set_text(lbl_gw_val, "48%");
    lv_obj_set_style_text_color(lbl_gw_val, lv_color_hex(0x3B82F6), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_gw_val, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_align(lbl_gw_val, LV_ALIGN_TOP_RIGHT, -4, 2);

    bar_gw = lv_bar_create(box_gemini_wk);
    lv_obj_set_size(bar_gw, 144, 10);
    lv_obj_set_pos(bar_gw, 4, 32);
    lv_bar_set_range(bar_gw, 0, 100);
    lv_obj_set_style_bg_color(bar_gw, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_gw, lv_color_hex(0x2563EB), LV_PART_INDICATOR);
    lv_obj_set_style_radius(bar_gw, 5, LV_PART_MAIN);
    lv_obj_set_style_radius(bar_gw, 5, LV_PART_INDICATOR);

    lbl_gw_sub = lv_label_create(box_gemini_wk);
    lv_label_set_text(lbl_gw_sub, "Refresh in: 1d 21h");
    lv_obj_set_style_text_color(lbl_gw_sub, lv_color_hex(0x94A3B8), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_gw_sub, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_gw_sub, 4, 52);

    // Box 3: Claude 5H
    box_claude_5h = lv_obj_create(scr_dashboard);
    lv_obj_set_size(box_claude_5h, 158, 88);
    lv_obj_set_pos(box_claude_5h, 160, 48);
    lv_obj_set_style_bg_color(box_claude_5h, lv_color_hex(0x18181B), LV_PART_MAIN);
    lv_obj_set_style_border_color(box_claude_5h, lv_color_hex(0xF97316), LV_PART_MAIN);
    lv_obj_set_style_border_width(box_claude_5h, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(box_claude_5h, 8, LV_PART_MAIN);
    lv_obj_set_style_pad_all(box_claude_5h, 6, LV_PART_MAIN);
    lv_obj_add_flag(box_claude_5h, LV_OBJ_FLAG_HIDDEN);

    lv_obj_t *lbl_c5_t = lv_label_create(box_claude_5h);
    lv_label_set_text(lbl_c5_t, "5H Limit");
    lv_obj_set_style_text_color(lbl_c5_t, lv_color_hex(0xFB923C), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_c5_t, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_c5_t, 4, 4);

    lbl_c5_val = lv_label_create(box_claude_5h);
    lv_label_set_text(lbl_c5_val, "100%");
    lv_obj_set_style_text_color(lbl_c5_val, lv_color_hex(0xFB923C), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_c5_val, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_align(lbl_c5_val, LV_ALIGN_TOP_RIGHT, -4, 2);

    bar_c5 = lv_bar_create(box_claude_5h);
    lv_obj_set_size(bar_c5, 144, 10);
    lv_obj_set_pos(bar_c5, 4, 32);
    lv_bar_set_range(bar_c5, 0, 100);
    lv_obj_set_style_bg_color(bar_c5, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_c5, lv_color_hex(0xF97316), LV_PART_INDICATOR);
    lv_obj_set_style_radius(bar_c5, 5, LV_PART_MAIN);
    lv_obj_set_style_radius(bar_c5, 5, LV_PART_INDICATOR);

    lbl_c5_sub = lv_label_create(box_claude_5h);
    lv_label_set_text(lbl_c5_sub, "Quota available");
    lv_obj_set_style_text_font(lbl_c5_sub, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_c5_sub, 4, 52);

    // Box 4: Claude Weekly
    box_claude_wk = lv_obj_create(scr_dashboard);
    lv_obj_set_size(box_claude_wk, 158, 88);
    lv_obj_set_pos(box_claude_wk, 160, 142);
    lv_obj_set_style_bg_color(box_claude_wk, lv_color_hex(0x18181B), LV_PART_MAIN);
    lv_obj_set_style_border_color(box_claude_wk, lv_color_hex(0xF97316), LV_PART_MAIN);
    lv_obj_set_style_border_width(box_claude_wk, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(box_claude_wk, 8, LV_PART_MAIN);
    lv_obj_set_style_pad_all(box_claude_wk, 6, LV_PART_MAIN);
    lv_obj_add_flag(box_claude_wk, LV_OBJ_FLAG_HIDDEN);

    lv_obj_t *lbl_cw_t = lv_label_create(box_claude_wk);
    lv_label_set_text(lbl_cw_t, "Weekly");
    lv_obj_set_style_text_color(lbl_cw_t, lv_color_hex(0xFB923C), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_cw_t, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_cw_t, 4, 4);

    lbl_cw_val = lv_label_create(box_claude_wk);
    lv_label_set_text(lbl_cw_val, "66%");
    lv_obj_set_style_text_color(lbl_cw_val, lv_color_hex(0xFB923C), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_cw_val, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_align(lbl_cw_val, LV_ALIGN_TOP_RIGHT, -4, 2);

    bar_cw = lv_bar_create(box_claude_wk);
    lv_obj_set_size(bar_cw, 144, 10);
    lv_obj_set_pos(bar_cw, 4, 32);
    lv_bar_set_range(bar_cw, 0, 100);
    lv_obj_set_style_bg_color(bar_cw, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_cw, lv_color_hex(0xF97316), LV_PART_INDICATOR);
    lv_obj_set_style_radius(bar_cw, 5, LV_PART_MAIN);
    lv_obj_set_style_radius(bar_cw, 5, LV_PART_INDICATOR);

    lbl_cw_sub = lv_label_create(box_claude_wk);
    lv_label_set_text(lbl_cw_sub, "Refresh in: 2d 15h");
    lv_obj_set_style_text_color(lbl_cw_sub, lv_color_hex(0x94A3B8), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_cw_sub, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_cw_sub, 4, 52);

    // --- Footer Ticker ---
    lbl_ticker = lv_label_create(scr_dashboard);
    lv_label_set_text(lbl_ticker, "* Initializing 24/7 AI Monitor...");
    lv_obj_set_style_text_color(lbl_ticker, lv_color_hex(0xF97316), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_ticker, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_size(lbl_ticker, 300, 20);
    lv_label_set_long_mode(lbl_ticker, LV_LABEL_LONG_DOT);
    lv_obj_align(lbl_ticker, LV_ALIGN_BOTTOM_MID, 0, -3);
}

void fetchQuotaData() {
    if (WiFi.status() != WL_CONNECTED) {
        showTelemetryError("Wi-Fi is disconnected. The device will retry automatically.");
        return;
    }

    lv_obj_set_style_text_color(lbl_next_icon, lv_color_hex(0x10B981), LV_PART_MAIN);

    HTTPClient http;
    String payload;
    int httpCode = HTTP_CODE_OK;
    if (prefetchedTelemetryPayload.length() > 0) {
        payload = prefetchedTelemetryPayload;
        prefetchedTelemetryPayload = "";
    } else {
        if (!beginTelemetryRequest(http, telemetryPlainClient, TELEMETRY_SERVER_URL)) {
            return;
        }
        http.setReuse(true);
        http.setConnectTimeout(TELEMETRY_CONNECT_TIMEOUT_MS);
        http.setTimeout(TELEMETRY_READ_TIMEOUT_MS);
        addTelemetryAuth(http);
        httpCode = http.GET();
    }

    if (httpCode == HTTP_CODE_OK) {
        int payloadSize = payload.length() > 0 ? static_cast<int>(payload.length()) : http.getSize();
        if (payloadSize > static_cast<int>(MAX_TELEMETRY_BYTES)) {
            http.end();
            showTelemetryError("Monitor response exceeded the safe size limit.");
            return;
        }
        if (payload.length() == 0) {
            payload = http.getString();
        }
        if (payload.length() > MAX_TELEMETRY_BYTES) {
            http.end();
            showTelemetryError("Monitor response exceeded the safe size limit.");
            return;
        }
        JsonDocument doc;
        DeserializationError error = deserializeJson(doc, payload);

        if (!error) {
            accountName = doc["account_name"] | "ChatGPT Account";
            extraCredits = doc["extra_credits"] | "None";

            String provider = doc["provider"] | "codex";
            String telemetryStatus = doc["status"] | "ok";
            if (telemetryStatus != "ok") {
                // Never render an error as an apparently healthy quota bar.
                provider = "error";
            }
            String default_ticker = "* " + accountName;
            String ticker = doc["status_ticker"] | default_ticker;

            // Apply Header
            lv_label_set_text(lbl_account_name, accountName.c_str());
            lv_obj_clear_flag(header_img, LV_OBJ_FLAG_HIDDEN);

            if (provider == "error") {
                lv_img_set_src(header_img, &mascot_img);
                lv_obj_add_flag(card_primary, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(card_details, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(lbl_col_gemini, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(lbl_col_claude, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(box_gemini_5h, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(box_gemini_wk, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(box_claude_5h, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(box_claude_wk, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(lbl_ticker, LV_OBJ_FLAG_HIDDEN);
                lv_obj_clear_flag(card_error, LV_OBJ_FLAG_HIDDEN);
                String error_detail = doc["primary_sub"] | "The CLI collector has no usable quota data.";
                lv_label_set_text(lbl_error_detail, error_detail.c_str());
            } else if (provider == "antigravity") {
                // ==========================================
                // 2x2 GRID UI FOR GOOGLE ANTIGRAVITY
                // ==========================================

                // Set Header Mascot: Official Antigravity Rainbow Arch Logo
                lv_img_set_src(header_img, &antigravity_mascot_img);

                // Hide ChatGPT Layout & Ticker
                lv_obj_add_flag(card_primary, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(card_details, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(lbl_ticker, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(card_error, LV_OBJ_FLAG_HIDDEN);

                // Show 2x2 Grid Layout
                lv_obj_clear_flag(lbl_col_gemini, LV_OBJ_FLAG_HIDDEN);
                lv_obj_clear_flag(lbl_col_claude, LV_OBJ_FLAG_HIDDEN);
                lv_obj_clear_flag(box_gemini_5h, LV_OBJ_FLAG_HIDDEN);
                lv_obj_clear_flag(box_gemini_wk, LV_OBJ_FLAG_HIDDEN);
                lv_obj_clear_flag(box_claude_5h, LV_OBJ_FLAG_HIDDEN);
                lv_obj_clear_flag(box_claude_wk, LV_OBJ_FLAG_HIDDEN);

                int g_5h = doc["gemini_5h_pct"] | 0;
                String g_5h_sub = doc["gemini_5h_sub"] | "No collector data";
                int g_wk = doc["gemini_weekly_pct"] | 0;
                String g_wk_sub = doc["gemini_weekly_sub"] | "No collector data";

                int c_5h = doc["claude_5h_pct"] | 0;
                String c_5h_sub = doc["claude_5h_sub"] | "No collector data";
                int c_wk = doc["claude_weekly_pct"] | 0;
                String c_wk_sub = doc["claude_weekly_sub"] | "No collector data";

                // Update Gemini 5H Box (Progress bar = % remaining)
                String g5_val_str = String(g_5h) + "%";
                lv_label_set_text(lbl_g5_val, g5_val_str.c_str());
                lv_bar_set_value(bar_g5, g_5h, LV_ANIM_ON);
                lv_label_set_text(lbl_g5_sub, g_5h_sub.c_str());

                // Update Gemini Weekly Box
                String gw_val_str = String(g_wk) + "%";
                lv_label_set_text(lbl_gw_val, gw_val_str.c_str());
                lv_bar_set_value(bar_gw, g_wk, LV_ANIM_ON);
                lv_label_set_text(lbl_gw_sub, g_wk_sub.c_str());

                // Update Claude 5H Box
                String c5_val_str = String(c_5h) + "%";
                lv_label_set_text(lbl_c5_val, c5_val_str.c_str());
                lv_bar_set_value(bar_c5, c_5h, LV_ANIM_ON);
                lv_label_set_text(lbl_c5_sub, c_5h_sub.c_str());

                // Update Claude Weekly Box
                String cw_val_str = String(c_wk) + "%";
                lv_label_set_text(lbl_cw_val, cw_val_str.c_str());
                lv_bar_set_value(bar_cw, c_wk, LV_ANIM_ON);
                lv_label_set_text(lbl_cw_sub, c_wk_sub.c_str());

            } else {
                // ==========================================
                // SINGLE-GROUP UI FOR CHATGPT
                // ==========================================

                // Set Header Mascot: Robot Icon
                lv_img_set_src(header_img, &mascot_img);

                // Hide 2x2 Grid Layout
                lv_obj_add_flag(lbl_col_gemini, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(lbl_col_claude, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(box_gemini_5h, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(box_gemini_wk, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(box_claude_5h, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(box_claude_wk, LV_OBJ_FLAG_HIDDEN);

                // Show ChatGPT Layout (Hide bottom ticker completely)
                lv_obj_clear_flag(card_primary, LV_OBJ_FLAG_HIDDEN);
                lv_obj_clear_flag(card_details, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(lbl_ticker, LV_OBJ_FLAG_HIDDEN);
                lv_obj_add_flag(card_error, LV_OBJ_FLAG_HIDDEN);

                int p_pct = doc["primary_pct"] | 0;
                int left_pct = 100 - p_pct;
                if (left_pct < 0) left_pct = 0;
                String default_p = String(p_pct) + "%";
                String p_val = doc["primary_val"] | default_p;
                String p_tag = doc["primary_tag"] | "Usage Limit";
                String p_sub = doc["primary_sub"] | "100% left";
                String plan_type = doc["plan_type"] | "ChatGPT Plus";

                lv_label_set_text(lbl_primary_val, p_val.c_str());
                lv_label_set_text(lbl_primary_tag, p_tag.c_str());
                lv_obj_set_style_text_color(lbl_primary_tag, lv_color_hex(0xE4E4E7), LV_PART_MAIN);
                lv_obj_set_style_text_font(lbl_primary_val, &lv_font_montserrat_32, LV_PART_MAIN);

                lv_obj_set_size(bar_primary, 296, 14);
                lv_obj_set_pos(bar_primary, 4, 52);
                lv_bar_set_value(bar_primary, left_pct, LV_ANIM_ON);

                lv_label_set_text(lbl_primary_sub, p_sub.c_str());
                lv_obj_set_style_text_font(lbl_primary_sub, &lv_font_montserrat_14, LV_PART_MAIN);
                lv_obj_set_pos(lbl_primary_sub, 6, 80);

                // Color-code primary bar & value
                if (p_pct >= 100) {
                    lv_obj_clear_flag(lbl_primary_warn, LV_OBJ_FLAG_HIDDEN);
                    lv_obj_set_style_bg_color(bar_primary, lv_color_hex(0xF43F5E), LV_PART_INDICATOR);
                    lv_obj_set_style_text_color(lbl_primary_val, lv_color_hex(0xF43F5E), LV_PART_MAIN);
                } else if (p_pct > 80) {
                    lv_obj_add_flag(lbl_primary_warn, LV_OBJ_FLAG_HIDDEN);
                    lv_obj_set_style_bg_color(bar_primary, lv_color_hex(0xF43F5E), LV_PART_INDICATOR);
                    lv_obj_set_style_text_color(lbl_primary_val, lv_color_hex(0xF43F5E), LV_PART_MAIN);
                } else if (p_pct > 50) {
                    lv_obj_add_flag(lbl_primary_warn, LV_OBJ_FLAG_HIDDEN);
                    lv_obj_set_style_bg_color(bar_primary, lv_color_hex(0xF59E0B), LV_PART_INDICATOR);
                    lv_obj_set_style_text_color(lbl_primary_val, lv_color_hex(0xF59E0B), LV_PART_MAIN);
                } else {
                    lv_obj_add_flag(lbl_primary_warn, LV_OBJ_FLAG_HIDDEN);
                    lv_obj_set_style_bg_color(bar_primary, lv_color_hex(0x10B981), LV_PART_INDICATOR);
                    lv_obj_set_style_text_color(lbl_primary_val, lv_color_hex(0x10B981), LV_PART_MAIN);
                }

                // Styled Credits in Cyan (#38bdf8) and Plan Type
                String cred_label = "Credits: #38bdf8 " + extraCredits + "#";
                lv_label_set_text(lbl_extra_credits, cred_label.c_str());
                lv_label_set_text(lbl_server_status, plan_type.c_str());
                lv_obj_set_style_text_color(lbl_server_status, lv_color_hex(0x10B981), LV_PART_MAIN);
            }

            // Flash Green LED on update
            digitalWrite(LED_GREEN, LOW);
            delay(20);
            digitalWrite(LED_GREEN, HIGH);
        } else {
            showTelemetryError("Monitor returned invalid telemetry JSON.");
        }
    } else if (httpCode == HTTP_CODE_UNAUTHORIZED) {
        showTelemetryError("Device token was rejected by the monitor server.");
    } else if (httpCode > 0) {
        showTelemetryError("Monitor request failed with HTTP " + String(httpCode) + ".");
    } else {
        Serial.printf("[NET] LAN request failed: HTTPClient=%d (%s)\n",
                      httpCode, HTTPClient::errorToString(httpCode).c_str());
        showTelemetryError("Local monitor connection failed. Check LAN address and server.");
    }
    http.end();
}

void setup() {
    Serial.begin(115200);
    delay(300);

    // RGB Setup
    pinMode(LED_RED, OUTPUT);
    pinMode(LED_GREEN, OUTPUT);
    pinMode(LED_BLUE, OUTPUT);
    digitalWrite(LED_RED, HIGH);
    digitalWrite(LED_GREEN, HIGH);
    digitalWrite(LED_BLUE, HIGH);

    // Touch setup
    touchSPI.begin(XPT2046_CLK, XPT2046_MISO, XPT2046_MOSI, XPT2046_CS);
    touch.begin(touchSPI);
    touch.setRotation(1);

    // Display & LVGL Setup
    tft.init();
    tft.setRotation(1); // Landscape 320x240 right-side up

    lv_init();
    lv_disp_draw_buf_init(&draw_buf, buf, NULL, 320 * 30);

    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = 320;
    disp_drv.ver_res = 240;
    disp_drv.flush_cb = my_disp_flush;
    disp_drv.draw_buf = &draw_buf;
    lv_disp_drv_register(&disp_drv);

    static lv_indev_drv_t indev_drv;
    lv_indev_drv_init(&indev_drv);
    indev_drv.type = LV_INDEV_TYPE_POINTER;
    indev_drv.read_cb = my_touchpad_read;
    lv_indev_drv_register(&indev_drv);

    // Build Dashboard UI
    buildDashboardUI();
    lv_scr_load(scr_dashboard);

    // Wi-Fi Connection
    WiFi.persistent(false);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 15) {
        delay(300);
        digitalWrite(LED_BLUE, !digitalRead(LED_BLUE));
        attempts++;
    }
    digitalWrite(LED_BLUE, HIGH);

    // Establish and validate the reusable secure session before the normal
    // interaction loop begins. Once the dashboard becomes interactive,
    // touch and serial actions use the already-open connection.
    lv_timer_handler();
    delay(5);
    fetchQuotaData();
    lv_timer_handler();
    lastFetchTime = millis();
}

void loop() {
    lv_timer_handler();
    delay(5);

    if (Serial.available()) {
        char c = Serial.read();
        if (c == 'n' || c == 'N' || c == ' ') {
            triggerNextAccount();
        }
    }

    if (nextAccountRequested) {
        nextAccountRequested = false;
        triggerNextAccount();
    }

    if (millis() - lastFetchTime >= FETCH_INTERVAL) {
        lastFetchTime = millis();
        fetchQuotaData();
    }
}
