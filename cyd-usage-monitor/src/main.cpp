#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <SPI.h>
#include <TFT_eSPI.h>
#include <lvgl.h>
#include <Preferences.h>
#include "secrets.h"
#include "mascot_img.h"

// Hosyond/LCDWiki E32R40T onboard common-anode RGB LED.
#define LED_RED 22
#define LED_GREEN 16
#define LED_BLUE 17

TFT_eSPI tft = TFT_eSPI();
WiFiClient telemetryPlainClient;
Preferences displayPreferences;

// LVGL buffer (sized for 480x320 landscape)
static lv_disp_draw_buf_t draw_buf;
static lv_color_t buf[480 * 20];

unsigned long lastFetchTime = 0;
// The host collector refreshes CLI data every few minutes.  A short local-LAN
// poll makes a dashboard "Show" selection visible on the physical CYD within
// three seconds, without triggering another provider CLI invocation.
const unsigned long FETCH_INTERVAL = 3000;
const size_t MAX_TELEMETRY_BYTES = 16384;
const unsigned long TELEMETRY_CONNECT_TIMEOUT_MS = 3000;
const unsigned long TELEMETRY_READ_TIMEOUT_MS = 5000;
static volatile bool nextAccountRequested = false;
static volatile bool openUsageRequested = false;
static volatile bool openRouterRequested = false;
static volatile bool homeRequested = false;
static bool usageFetchPending = false;
static bool touchInputReady = false;
static unsigned long touchReleasedSince = 0;
static unsigned long wifiBeginTime = 0;
static unsigned long lastWifiUiUpdate = 0;
static unsigned long lastDisplayCommandPoll = 0;
static wl_status_t previousWifiStatus = WL_NO_SHIELD;
static String lastDisplayCommandId;
static uint16_t displayRotationDegrees = 0;
static bool displayCommandSeen = false;
static bool displayStateReportPending = false;
static unsigned long lastDisplayStateReportAttempt = 0;

enum class AppScreen : uint8_t {
    MainMenu,
    UsageMonitor,
    OpenRouter,
};

enum class AppId : uint8_t {
    UsageMonitor,
    OpenRouter,
};

struct AppDescriptor {
    AppId id;
    const char *title;
    const char *subtitle;
    uint32_t accent;
};

static AppScreen activeScreen = AppScreen::MainMenu;
static const AppDescriptor launcherApps[] = {
    {AppId::UsageMonitor, "Usage Monitor", "AI quota dashboard", 0xC4B5FD},
    {AppId::OpenRouter, "OpenRouter", "Credits & spend", 0xA7F3D0},
};

// A compact 56x56 RGB565 canvas (6,272 bytes) provides a custom app icon
// without paying the roughly 150 KB cost of a full-screen canvas.
static lv_color_t launcherIconBuffer[56 * 56];
static lv_point_t openRouterRoutePoints[] = {{4, 36}, {15, 15}, {30, 31}, {44, 10}};

// Launcher Screen & Widgets
static lv_obj_t *scr_launcher;
static lv_obj_t *launcher_wifi_pill;
static lv_obj_t *launcher_wifi_dot;
static lv_obj_t *launcher_wifi_label;

// Dashboard Screen & Widgets
static lv_obj_t *scr_dashboard;
static lv_obj_t *scr_openrouter;
static lv_obj_t *or_balance_arc;
static lv_obj_t *or_balance_value;
static lv_obj_t *or_account_label;
static lv_obj_t *or_today_value;
static lv_obj_t *or_week_value;
static lv_obj_t *or_month_value;
static lv_obj_t *or_chart;
static lv_chart_series_t *or_chart_series;
static lv_obj_t *or_top_model;
static lv_obj_t *or_state_label;

// Header Widgets
static lv_obj_t *header_img;
static lv_obj_t *lbl_ag_mascot;
static lv_obj_t *lbl_account_name;
static lv_obj_t *btn_home;
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
static lv_obj_t *lbl_weekly_val;
static lv_obj_t *lbl_weekly_tag;
static lv_obj_t *bar_weekly;
static lv_obj_t *lbl_weekly_sub;
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
void fetchOpenRouterData();
void pollDisplayCommand();
void reportDisplayState();
void applyDisplayRotation(uint16_t rotationDegrees);
void showTelemetryError(const String &detail);
void showLauncherScreen();
void showUsageMonitorScreen();
void showOpenRouterScreen();

void printSimulatorKeybinds() {
    Serial.println();
    Serial.println("[KEYS] Wokwi touch shortcuts");
    Serial.println("[KEYS] U  Open Usage Monitor");
    Serial.println("[KEYS] O  Open OpenRouter");
    Serial.println("[KEYS] H  Return Home");
    Serial.println("[KEYS] N  Next account");
    Serial.println("[KEYS] ?  Show this help");
    Serial.println();
}

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
    bool pressed = false;
    uint16_t touch_x = 0, touch_y = 0;

    if (tft.getTouch(&touch_x, &touch_y, 200)) {
        pressed = true;
        if (displayRotationDegrees == 180) {
            touch_x = 479 - constrain(touch_x, 0, 479);
            touch_y = 319 - constrain(touch_y, 0, 319);
        }
        Serial.printf("[TOUCH] calibrated screen=(%d, %d)\n", touch_x, touch_y);
    }

    if (!touchInputReady) {
        if (pressed) {
            touchReleasedSince = 0;
        } else if (touchReleasedSince == 0) {
            touchReleasedSince = millis();
        } else if (millis() - touchReleasedSince >= 100) {
            touchInputReady = true;
        }
        data->state = LV_INDEV_STATE_REL;
        return;
    }

    if (pressed) {
        data->state = LV_INDEV_STATE_PR;
        data->point.x = constrain(touch_x, 0, 479);
        data->point.y = constrain(touch_y, 0, 319);
        return;
    }

    data->state = LV_INDEV_STATE_REL;
}

void applyDisplayRotation(uint16_t rotationDegrees) {
    const bool flipped = rotationDegrees == 180;
    const uint16_t normalized = flipped ? 180 : 0;
    if (displayRotationDegrees == normalized) return;

    displayRotationDegrees = normalized;
    displayPreferences.putUShort("rotation", displayRotationDegrees);
    displayStateReportPending = true;
    tft.setRotation(flipped ? 3 : 1); // Both are 480x320 landscape orientations.
    touchInputReady = false;
    touchReleasedSince = 0;
    tft.fillScreen(TFT_BLACK);
    if (lv_scr_act() != nullptr) {
        lv_obj_invalidate(lv_scr_act());
        lv_refr_now(nullptr);
    }
    Serial.printf("[DISPLAY] Orientation set to %u degrees\n", displayRotationDegrees);
}

void launcherTileEvent(lv_event_t *event) {
    if (lv_event_get_code(event) != LV_EVENT_CLICKED) {
        return;
    }
    const AppDescriptor *app = static_cast<const AppDescriptor *>(lv_event_get_user_data(event));
    if (app != nullptr && app->id == AppId::UsageMonitor) {
        Serial.println("[NAV] Launcher -> Usage Monitor");
        openRouterRequested = false;
        openUsageRequested = true;
    } else if (app != nullptr && app->id == AppId::OpenRouter) {
        Serial.println("[NAV] Launcher -> OpenRouter");
        openUsageRequested = false;
        openRouterRequested = true;
    }
}

void homeButtonEvent(lv_event_t *event) {
    if (lv_event_get_code(event) == LV_EVENT_CLICKED) {
        Serial.println("[NAV] App -> Home");
        openUsageRequested = false;
        openRouterRequested = false;
        homeRequested = true;
    }
}

void nextAccountButtonEvent(lv_event_t *event) {
    if (lv_event_get_code(event) == LV_EVENT_CLICKED) {
        nextAccountRequested = true;
    }
}

void setLauncherWifiState(const char *text, uint32_t color) {
    if (launcher_wifi_label == nullptr) {
        return;
    }
    lv_label_set_text(launcher_wifi_label, text);
    lv_obj_set_style_bg_color(launcher_wifi_dot, lv_color_hex(color), LV_PART_MAIN);
    lv_obj_set_style_border_color(launcher_wifi_pill, lv_color_hex(color), LV_PART_MAIN);
}

void drawLauncherIcon(lv_obj_t *canvas, AppId id) {
    lv_canvas_set_buffer(canvas, launcherIconBuffer, 56, 56, LV_IMG_CF_TRUE_COLOR_CHROMA_KEYED);
    lv_canvas_fill_bg(canvas, LV_COLOR_CHROMA_KEY, LV_OPA_COVER);

    lv_draw_arc_dsc_t arc;
    lv_draw_arc_dsc_init(&arc);
    arc.color = lv_color_hex(0xC4B5FD);
    arc.width = 5;
    arc.rounded = true;
    lv_canvas_draw_arc(canvas, 28, 27, 20, 40, 320, &arc);

    lv_draw_arc_dsc_t accentArc;
    lv_draw_arc_dsc_init(&accentArc);
    accentArc.color = lv_color_hex(0xA7F3D0);
    accentArc.width = 5;
    accentArc.rounded = true;
    lv_canvas_draw_arc(canvas, 28, 27, 20, 40, 165, &accentArc);

    const uint32_t barColors[] = {0xFBCFE8, 0xBAE6FD, 0xFDE68A};
    const lv_coord_t barHeights[] = {8, 14, 20};
    for (int i = 0; i < 3; ++i) {
        lv_draw_rect_dsc_t bar;
        lv_draw_rect_dsc_init(&bar);
        bar.bg_color = lv_color_hex(barColors[i]);
        bar.bg_opa = LV_OPA_COVER;
        bar.radius = 2;
        lv_canvas_draw_rect(canvas, 17 + i * 9, 45 - barHeights[i], 6, barHeights[i], &bar);
    }
}

lv_obj_t *createLauncherTile(lv_obj_t *parent, const AppDescriptor *app) {
    lv_obj_t *tile = lv_btn_create(parent);
    lv_obj_set_size(tile, 218, 220);
    lv_obj_clear_flag(tile, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_color(tile, lv_color_hex(0x282432), LV_PART_MAIN);
    lv_obj_set_style_bg_grad_color(tile, lv_color_hex(0x202A31), LV_PART_MAIN);
    lv_obj_set_style_bg_grad_dir(tile, LV_GRAD_DIR_VER, LV_PART_MAIN);
    lv_obj_set_style_border_color(tile, lv_color_hex(app->accent), LV_PART_MAIN);
    lv_obj_set_style_border_width(tile, 2, LV_PART_MAIN);
    lv_obj_set_style_radius(tile, 20, LV_PART_MAIN);
    lv_obj_set_style_shadow_color(tile, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
    lv_obj_set_style_shadow_width(tile, 18, LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(tile, LV_OPA_20, LV_PART_MAIN);
    lv_obj_set_style_pad_all(tile, 0, LV_PART_MAIN);
    lv_obj_set_style_transform_zoom(tile, 242, LV_STATE_PRESSED);
    lv_obj_set_style_bg_color(tile, lv_color_hex(0x332D42), LV_STATE_PRESSED);
    lv_obj_add_event_cb(tile, launcherTileEvent, LV_EVENT_CLICKED, const_cast<AppDescriptor *>(app));

    if (app->id == AppId::UsageMonitor) {
        lv_obj_t *canvas = lv_canvas_create(tile);
        lv_obj_clear_flag(canvas, LV_OBJ_FLAG_CLICKABLE);
        drawLauncherIcon(canvas, app->id);
        lv_obj_align(canvas, LV_ALIGN_TOP_MID, 0, 16);
    } else {
        lv_obj_t *icon = lv_obj_create(tile);
        lv_obj_clear_flag(icon, LV_OBJ_FLAG_CLICKABLE);
        lv_obj_set_size(icon, 56, 56);
        lv_obj_align(icon, LV_ALIGN_TOP_MID, 0, 16);
        lv_obj_clear_flag(icon, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_set_style_bg_opa(icon, LV_OPA_TRANSP, LV_PART_MAIN);
        lv_obj_set_style_border_width(icon, 0, LV_PART_MAIN);
        lv_obj_set_style_pad_all(icon, 4, LV_PART_MAIN);
        lv_obj_t *route = lv_line_create(icon);
        lv_line_set_points(route, openRouterRoutePoints, 4);
        lv_obj_set_style_line_color(route, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
        lv_obj_set_style_line_width(route, 5, LV_PART_MAIN);
        lv_obj_set_style_line_rounded(route, true, LV_PART_MAIN);
        for (const lv_point_t &point : openRouterRoutePoints) {
            lv_obj_t *node = lv_obj_create(icon);
            lv_obj_clear_flag(node, LV_OBJ_FLAG_CLICKABLE);
            lv_obj_set_size(node, 9, 9);
            lv_obj_set_pos(node, point.x - 4, point.y - 4);
            lv_obj_set_style_radius(node, LV_RADIUS_CIRCLE, LV_PART_MAIN);
            lv_obj_set_style_bg_color(node, lv_color_hex(0xC4B5FD), LV_PART_MAIN);
            lv_obj_set_style_border_width(node, 0, LV_PART_MAIN);
        }
    }

    lv_obj_t *title = lv_label_create(tile);
    lv_obj_clear_flag(title, LV_OBJ_FLAG_CLICKABLE);
    lv_label_set_text(title, app->title);
    lv_obj_set_style_text_color(title, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
    lv_obj_set_style_text_font(title, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 86);

    lv_obj_t *subtitle = lv_label_create(tile);
    lv_obj_clear_flag(subtitle, LV_OBJ_FLAG_CLICKABLE);
    lv_label_set_text(subtitle, app->subtitle);
    lv_obj_set_style_text_color(subtitle, lv_color_hex(0xC7D2FE), LV_PART_MAIN);
    lv_obj_set_style_text_font(subtitle, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_align(subtitle, LV_ALIGN_TOP_MID, 0, 118);

    lv_obj_t *openLabel = lv_label_create(tile);
    lv_obj_clear_flag(openLabel, LV_OBJ_FLAG_CLICKABLE);
    lv_label_set_text(openLabel, "Open  " LV_SYMBOL_RIGHT);
    lv_obj_set_style_text_color(openLabel, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
    lv_obj_set_style_text_font(openLabel, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_align(openLabel, LV_ALIGN_BOTTOM_MID, 0, -14);

    lv_obj_fade_in(tile, 220, 60);
    return tile;
}

void buildLauncherUI() {
    scr_launcher = lv_obj_create(NULL);
    lv_obj_clear_flag(scr_launcher, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_color(scr_launcher, lv_color_hex(0x111217), LV_PART_MAIN);
    lv_obj_set_style_bg_grad_color(scr_launcher, lv_color_hex(0x191622), LV_PART_MAIN);
    lv_obj_set_style_bg_grad_dir(scr_launcher, LV_GRAD_DIR_VER, LV_PART_MAIN);
    lv_obj_set_style_pad_all(scr_launcher, 0, LV_PART_MAIN);

    lv_obj_t *lavenderGlow = lv_obj_create(scr_launcher);
    lv_obj_set_size(lavenderGlow, 120, 120);
    lv_obj_set_pos(lavenderGlow, 380, -40);
    lv_obj_set_style_radius(lavenderGlow, LV_RADIUS_CIRCLE, LV_PART_MAIN);
    lv_obj_set_style_bg_color(lavenderGlow, lv_color_hex(0xC4B5FD), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(lavenderGlow, LV_OPA_10, LV_PART_MAIN);
    lv_obj_set_style_border_width(lavenderGlow, 0, LV_PART_MAIN);

    lv_obj_t *mintGlow = lv_obj_create(scr_launcher);
    lv_obj_set_size(mintGlow, 90, 90);
    lv_obj_set_pos(mintGlow, -30, 240);
    lv_obj_set_style_radius(mintGlow, LV_RADIUS_CIRCLE, LV_PART_MAIN);
    lv_obj_set_style_bg_color(mintGlow, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(mintGlow, LV_OPA_10, LV_PART_MAIN);
    lv_obj_set_style_border_width(mintGlow, 0, LV_PART_MAIN);

    lv_obj_t *title = lv_label_create(scr_launcher);
    lv_label_set_text(title, "CYD Apps");
    lv_obj_set_style_text_color(title, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
    lv_obj_set_style_text_font(title, &lv_font_montserrat_28, LV_PART_MAIN);
    lv_obj_set_pos(title, 24, 12);

    lv_obj_t *subtitle = lv_label_create(scr_launcher);
    lv_label_set_text(subtitle, "Choose an app");
    lv_obj_set_style_text_color(subtitle, lv_color_hex(0xC7D2FE), LV_PART_MAIN);
    lv_obj_set_style_text_font(subtitle, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_pos(subtitle, 26, 46);

    launcher_wifi_pill = lv_obj_create(scr_launcher);
    lv_obj_set_size(launcher_wifi_pill, 114, 30);
    lv_obj_set_pos(launcher_wifi_pill, 346, 16);
    lv_obj_clear_flag(launcher_wifi_pill, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_color(launcher_wifi_pill, lv_color_hex(0x202028), LV_PART_MAIN);
    lv_obj_set_style_border_color(launcher_wifi_pill, lv_color_hex(0xFDE68A), LV_PART_MAIN);
    lv_obj_set_style_border_width(launcher_wifi_pill, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(launcher_wifi_pill, 15, LV_PART_MAIN);
    lv_obj_set_style_pad_all(launcher_wifi_pill, 0, LV_PART_MAIN);

    launcher_wifi_dot = lv_obj_create(launcher_wifi_pill);
    lv_obj_set_size(launcher_wifi_dot, 8, 8);
    lv_obj_set_pos(launcher_wifi_dot, 10, 10);
    lv_obj_set_style_radius(launcher_wifi_dot, LV_RADIUS_CIRCLE, LV_PART_MAIN);
    lv_obj_set_style_bg_color(launcher_wifi_dot, lv_color_hex(0xFDE68A), LV_PART_MAIN);
    lv_obj_set_style_border_width(launcher_wifi_dot, 0, LV_PART_MAIN);

    launcher_wifi_label = lv_label_create(launcher_wifi_pill);
    lv_label_set_text(launcher_wifi_label, "Connecting");
    lv_obj_set_style_text_color(launcher_wifi_label, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
    lv_obj_set_style_text_font(launcher_wifi_label, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(launcher_wifi_label, 26, 7);

    lv_obj_t *grid = lv_obj_create(scr_launcher);
    lv_obj_set_size(grid, 460, 235);
    lv_obj_set_pos(grid, 10, 75);
    lv_obj_clear_flag(grid, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_opa(grid, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(grid, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(grid, 4, LV_PART_MAIN);
    lv_obj_set_style_pad_row(grid, 12, LV_PART_MAIN);
    lv_obj_set_style_pad_column(grid, 16, LV_PART_MAIN);
    lv_obj_set_flex_flow(grid, LV_FLEX_FLOW_ROW_WRAP);
    lv_obj_set_flex_align(grid, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

    for (const AppDescriptor &app : launcherApps) {
        createLauncherTile(grid, &app);
    }
}

void showLauncherScreen() {
    activeScreen = AppScreen::MainMenu;
    usageFetchPending = false;
    nextAccountRequested = false;
    lv_scr_load_anim(scr_launcher, LV_SCR_LOAD_ANIM_MOVE_RIGHT, 180, 0, false);
    displayStateReportPending = true;
}

void showUsageMonitorScreen() {
    activeScreen = AppScreen::UsageMonitor;
    lv_scr_load_anim(scr_dashboard, LV_SCR_LOAD_ANIM_MOVE_LEFT, 180, 0, false);
    displayStateReportPending = true;
    if (WiFi.status() == WL_CONNECTED) {
        usageFetchPending = true;
    } else {
        showTelemetryError("Wi-Fi is connecting. Usage will refresh automatically.");
    }
}

void showOpenRouterScreen() {
    activeScreen = AppScreen::OpenRouter;
    lv_scr_load_anim(scr_openrouter, LV_SCR_LOAD_ANIM_MOVE_LEFT, 180, 0, false);
    displayStateReportPending = true;
    if (WiFi.status() == WL_CONNECTED) {
        usageFetchPending = true;
    } else {
        lv_label_set_text(or_state_label, "Wi-Fi connecting · refresh is automatic");
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
    lv_obj_set_pos(header_img, 10, 6);

    lbl_ag_mascot = lv_label_create(scr_dashboard);
    lv_label_set_text(lbl_ag_mascot, "🚀");
    lv_obj_set_style_text_font(lbl_ag_mascot, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_set_pos(lbl_ag_mascot, 10, 6);
    lv_obj_add_flag(lbl_ag_mascot, LV_OBJ_FLAG_HIDDEN);

    lbl_account_name = lv_label_create(scr_dashboard);
    lv_label_set_text(lbl_account_name, "Loading Account...");
    lv_obj_set_style_text_color(lbl_account_name, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_account_name, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_set_size(lbl_account_name, 320, 24);
    lv_label_set_long_mode(lbl_account_name, LV_LABEL_LONG_DOT);
    lv_obj_set_pos(lbl_account_name, 48, 7);

    btn_home = lv_btn_create(scr_dashboard);
    lv_obj_set_size(btn_home, 48, 38);
    lv_obj_set_pos(btn_home, 376, 1);
    lv_obj_set_style_radius(btn_home, 6, LV_PART_MAIN);
    lv_obj_set_style_bg_color(btn_home, lv_color_hex(0x2B2635), LV_PART_MAIN);
    lv_obj_set_style_border_color(btn_home, lv_color_hex(0xC4B5FD), LV_PART_MAIN);
    lv_obj_set_style_border_width(btn_home, 1, LV_PART_MAIN);
    lv_obj_set_style_pad_all(btn_home, 0, LV_PART_MAIN);
    lv_obj_set_style_transform_zoom(btn_home, 238, LV_STATE_PRESSED);
    lv_obj_add_event_cb(btn_home, homeButtonEvent, LV_EVENT_CLICKED, NULL);
    lv_obj_t *homeIcon = lv_label_create(btn_home);
    lv_label_set_text(homeIcon, LV_SYMBOL_HOME);
    lv_obj_set_style_text_color(homeIcon, lv_color_hex(0xC4B5FD), LV_PART_MAIN);
    lv_obj_center(homeIcon);

    btn_next_account = lv_btn_create(scr_dashboard);
    lv_obj_set_size(btn_next_account, 48, 38);
    lv_obj_set_pos(btn_next_account, 428, 1);
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
    lv_obj_set_size(card_primary, 460, 118);
    lv_obj_set_pos(card_primary, 10, 40);
    lv_obj_set_style_bg_color(card_primary, lv_color_hex(0x18181B), LV_PART_MAIN);
    lv_obj_set_style_border_color(card_primary, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_border_width(card_primary, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(card_primary, 12, LV_PART_MAIN);
    lv_obj_set_style_pad_all(card_primary, 8, LV_PART_MAIN);

    lbl_primary_val = lv_label_create(card_primary);
    lv_label_set_text(lbl_primary_val, "0%");
    lv_obj_set_style_text_color(lbl_primary_val, lv_color_hex(0x10B981), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_primary_val, &lv_font_montserrat_32, LV_PART_MAIN);
    lv_obj_set_pos(lbl_primary_val, 10, 4);

    lv_obj_t *badge1 = lv_obj_create(card_primary);
    lv_obj_set_size(badge1, 125, 26);
    lv_obj_align(badge1, LV_ALIGN_TOP_RIGHT, -6, 2);
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
    lv_obj_set_size(bar_primary, 440, 16);
    lv_obj_set_pos(bar_primary, 8, 54);
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
    lv_obj_set_pos(lbl_primary_sub, 10, 80);

    // --- ChatGPT Card 2: Weekly quota plus plan / credits footer ---
    card_details = lv_obj_create(scr_dashboard);
    lv_obj_set_size(card_details, 460, 110);
    lv_obj_set_pos(card_details, 10, 168);
    lv_obj_set_style_bg_color(card_details, lv_color_hex(0x18181B), LV_PART_MAIN);
    lv_obj_set_style_border_color(card_details, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_border_width(card_details, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(card_details, 10, LV_PART_MAIN);
    lv_obj_set_style_pad_all(card_details, 8, LV_PART_MAIN);

    lbl_weekly_val = lv_label_create(card_details);
    lv_label_set_text(lbl_weekly_val, "0% left");
    lv_obj_set_style_text_color(lbl_weekly_val, lv_color_hex(0x10B981), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_weekly_val, &lv_font_montserrat_24, LV_PART_MAIN);
    lv_obj_set_pos(lbl_weekly_val, 10, 0);

    lbl_weekly_tag = lv_label_create(card_details);
    lv_label_set_text(lbl_weekly_tag, "Weekly Limit");
    lv_obj_set_style_text_color(lbl_weekly_tag, lv_color_hex(0xE4E4E7), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_weekly_tag, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_align(lbl_weekly_tag, LV_ALIGN_TOP_RIGHT, -10, 5);

    bar_weekly = lv_bar_create(card_details);
    lv_obj_set_size(bar_weekly, 440, 12);
    lv_obj_set_pos(bar_weekly, 8, 36);
    lv_bar_set_range(bar_weekly, 0, 100);
    lv_obj_set_style_bg_color(bar_weekly, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_weekly, lv_color_hex(0x10B981), LV_PART_INDICATOR);
    lv_obj_set_style_radius(bar_weekly, 5, LV_PART_MAIN);
    lv_obj_set_style_radius(bar_weekly, 5, LV_PART_INDICATOR);

    lbl_weekly_sub = lv_label_create(card_details);
    lv_label_set_text(lbl_weekly_sub, "Waiting for weekly quota");
    lv_obj_set_style_text_color(lbl_weekly_sub, lv_color_hex(0x94A3B8), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_weekly_sub, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_weekly_sub, 10, 52);

    lbl_extra_credits = lv_label_create(card_details);
    lv_label_set_recolor(lbl_extra_credits, true);
    lv_label_set_text(lbl_extra_credits, "Credits: #38bdf8 None#");
    lv_obj_set_style_text_color(lbl_extra_credits, lv_color_hex(0xE4E4E7), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_extra_credits, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_extra_credits, 10, 78);

    lbl_server_status = lv_label_create(card_details);
    lv_label_set_text(lbl_server_status, "ChatGPT Plus");
    lv_obj_set_style_text_color(lbl_server_status, lv_color_hex(0x10B981), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_server_status, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_align(lbl_server_status, LV_ALIGN_TOP_RIGHT, -10, 78);

    // --- Collector Error Screen ---
    card_error = lv_obj_create(scr_dashboard);
    lv_obj_set_size(card_error, 460, 236);
    lv_obj_set_pos(card_error, 10, 42);
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
    lv_obj_set_style_text_font(lbl_error_detail, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_set_size(lbl_error_detail, 420, 140);
    lv_label_set_long_mode(lbl_error_detail, LV_LABEL_LONG_WRAP);
    lv_obj_set_pos(lbl_error_detail, 0, 43);
    lv_obj_add_flag(card_error, LV_OBJ_FLAG_HIDDEN);

    // ====================================================
    // --- ANTIGRAVITY 2x2 GRID LAYOUT ELEMENTS ---
    // ====================================================

    lbl_col_gemini = lv_label_create(scr_dashboard);
    lv_label_set_text(lbl_col_gemini, "Gemini Models");
    lv_obj_set_style_text_color(lbl_col_gemini, lv_color_hex(0x2563EB), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_col_gemini, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_pos(lbl_col_gemini, 14, 38);
    lv_obj_add_flag(lbl_col_gemini, LV_OBJ_FLAG_HIDDEN);

    lbl_col_claude = lv_label_create(scr_dashboard);
    lv_label_set_text(lbl_col_claude, "Claude Models");
    lv_obj_set_style_text_color(lbl_col_claude, lv_color_hex(0xF97316), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_col_claude, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_pos(lbl_col_claude, 250, 38);
    lv_obj_add_flag(lbl_col_claude, LV_OBJ_FLAG_HIDDEN);

    // Box 1: Gemini 5H
    box_gemini_5h = lv_obj_create(scr_dashboard);
    lv_obj_set_size(box_gemini_5h, 224, 105);
    lv_obj_set_pos(box_gemini_5h, 10, 58);
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
    lv_obj_set_pos(lbl_g5_t, 6, 6);

    lbl_g5_val = lv_label_create(box_gemini_5h);
    lv_label_set_text(lbl_g5_val, "78%");
    lv_obj_set_style_text_color(lbl_g5_val, lv_color_hex(0x3B82F6), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_g5_val, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_align(lbl_g5_val, LV_ALIGN_TOP_RIGHT, -6, 4);

    bar_g5 = lv_bar_create(box_gemini_5h);
    lv_obj_set_size(bar_g5, 208, 12);
    lv_obj_set_pos(bar_g5, 4, 48);
    lv_bar_set_range(bar_g5, 0, 100);
    lv_obj_set_style_bg_color(bar_g5, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_g5, lv_color_hex(0x2563EB), LV_PART_INDICATOR);
    lv_obj_set_style_radius(bar_g5, 5, LV_PART_MAIN);
    lv_obj_set_style_radius(bar_g5, 5, LV_PART_INDICATOR);

    lbl_g5_sub = lv_label_create(box_gemini_5h);
    lv_label_set_text(lbl_g5_sub, "Refresh in: 4h 31m");
    lv_obj_set_style_text_color(lbl_g5_sub, lv_color_hex(0x94A3B8), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_g5_sub, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_g5_sub, 6, 72);

    // Box 2: Gemini Weekly
    box_gemini_wk = lv_obj_create(scr_dashboard);
    lv_obj_set_size(box_gemini_wk, 224, 105);
    lv_obj_set_pos(box_gemini_wk, 10, 172);
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
    lv_obj_set_pos(lbl_gw_t, 6, 6);

    lbl_gw_val = lv_label_create(box_gemini_wk);
    lv_label_set_text(lbl_gw_val, "48%");
    lv_obj_set_style_text_color(lbl_gw_val, lv_color_hex(0x3B82F6), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_gw_val, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_align(lbl_gw_val, LV_ALIGN_TOP_RIGHT, -6, 4);

    bar_gw = lv_bar_create(box_gemini_wk);
    lv_obj_set_size(bar_gw, 208, 12);
    lv_obj_set_pos(bar_gw, 4, 48);
    lv_bar_set_range(bar_gw, 0, 100);
    lv_obj_set_style_bg_color(bar_gw, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_gw, lv_color_hex(0x2563EB), LV_PART_INDICATOR);
    lv_obj_set_style_radius(bar_gw, 5, LV_PART_MAIN);
    lv_obj_set_style_radius(bar_gw, 5, LV_PART_INDICATOR);

    lbl_gw_sub = lv_label_create(box_gemini_wk);
    lv_label_set_text(lbl_gw_sub, "Refresh in: 1d 21h");
    lv_obj_set_style_text_color(lbl_gw_sub, lv_color_hex(0x94A3B8), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_gw_sub, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_gw_sub, 6, 72);

    // Box 3: Claude 5H
    box_claude_5h = lv_obj_create(scr_dashboard);
    lv_obj_set_size(box_claude_5h, 224, 105);
    lv_obj_set_pos(box_claude_5h, 246, 58);
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
    lv_obj_set_pos(lbl_c5_t, 6, 6);

    lbl_c5_val = lv_label_create(box_claude_5h);
    lv_label_set_text(lbl_c5_val, "100%");
    lv_obj_set_style_text_color(lbl_c5_val, lv_color_hex(0xFB923C), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_c5_val, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_align(lbl_c5_val, LV_ALIGN_TOP_RIGHT, -6, 4);

    bar_c5 = lv_bar_create(box_claude_5h);
    lv_obj_set_size(bar_c5, 208, 12);
    lv_obj_set_pos(bar_c5, 4, 48);
    lv_bar_set_range(bar_c5, 0, 100);
    lv_obj_set_style_bg_color(bar_c5, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_c5, lv_color_hex(0xF97316), LV_PART_INDICATOR);
    lv_obj_set_style_radius(bar_c5, 5, LV_PART_MAIN);
    lv_obj_set_style_radius(bar_c5, 5, LV_PART_INDICATOR);

    lbl_c5_sub = lv_label_create(box_claude_5h);
    lv_label_set_text(lbl_c5_sub, "Quota available");
    lv_obj_set_style_text_font(lbl_c5_sub, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_c5_sub, 6, 72);

    // Box 4: Claude Weekly
    box_claude_wk = lv_obj_create(scr_dashboard);
    lv_obj_set_size(box_claude_wk, 224, 105);
    lv_obj_set_pos(box_claude_wk, 246, 172);
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
    lv_obj_set_pos(lbl_cw_t, 6, 6);

    lbl_cw_val = lv_label_create(box_claude_wk);
    lv_label_set_text(lbl_cw_val, "82%");
    lv_obj_set_style_text_color(lbl_cw_val, lv_color_hex(0xFB923C), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_cw_val, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_align(lbl_cw_val, LV_ALIGN_TOP_RIGHT, -6, 4);

    bar_cw = lv_bar_create(box_claude_wk);
    lv_obj_set_size(bar_cw, 208, 12);
    lv_obj_set_pos(bar_cw, 4, 48);
    lv_bar_set_range(bar_cw, 0, 100);
    lv_obj_set_style_bg_color(bar_cw, lv_color_hex(0x27272A), LV_PART_MAIN);
    lv_obj_set_style_bg_color(bar_cw, lv_color_hex(0xF97316), LV_PART_INDICATOR);
    lv_obj_set_style_radius(bar_cw, 5, LV_PART_MAIN);
    lv_obj_set_style_radius(bar_cw, 5, LV_PART_INDICATOR);

    lbl_cw_sub = lv_label_create(box_claude_wk);
    lv_label_set_text(lbl_cw_sub, "Refresh in: 2d 15h");
    lv_obj_set_style_text_color(lbl_cw_sub, lv_color_hex(0x94A3B8), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_cw_sub, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(lbl_cw_sub, 6, 72);

    // --- Footer Ticker ---
    lbl_ticker = lv_label_create(scr_dashboard);
    lv_label_set_text(lbl_ticker, "* Initializing 24/7 AI Monitor...");
    lv_obj_set_style_text_color(lbl_ticker, lv_color_hex(0xF97316), LV_PART_MAIN);
    lv_obj_set_style_text_font(lbl_ticker, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_size(lbl_ticker, 460, 20);
    lv_label_set_long_mode(lbl_ticker, LV_LABEL_LONG_DOT);
    lv_obj_align(lbl_ticker, LV_ALIGN_BOTTOM_MID, 0, -4);
}

lv_obj_t *createOpenRouterSpendCard(lv_obj_t *parent, const char *title, lv_coord_t x, lv_obj_t **value) {
    lv_obj_t *card = lv_obj_create(parent);
    lv_obj_set_size(card, 94, 88);
    lv_obj_set_pos(card, x, 44);
    lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_color(card, lv_color_hex(0x151D1C), LV_PART_MAIN);
    lv_obj_set_style_border_color(card, lv_color_hex(0x345048), LV_PART_MAIN);
    lv_obj_set_style_border_width(card, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(card, 9, LV_PART_MAIN);
    lv_obj_set_style_pad_all(card, 8, LV_PART_MAIN);
    lv_obj_t *caption = lv_label_create(card);
    lv_label_set_text(caption, title);
    lv_obj_set_style_text_color(caption, lv_color_hex(0x94A3B8), LV_PART_MAIN);
    lv_obj_set_style_text_font(caption, &lv_font_montserrat_12, LV_PART_MAIN);
    *value = lv_label_create(card);
    lv_label_set_text(*value, "$0.00");
    lv_obj_set_style_text_color(*value, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
    lv_obj_set_style_text_font(*value, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_align(*value, LV_ALIGN_BOTTOM_LEFT, 0, -2);
    return card;
}

void buildOpenRouterUI() {
    scr_openrouter = lv_obj_create(NULL);
    lv_obj_clear_flag(scr_openrouter, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_color(scr_openrouter, lv_color_hex(0x0B1110), LV_PART_MAIN);
    lv_obj_set_style_bg_grad_color(scr_openrouter, lv_color_hex(0x171326), LV_PART_MAIN);
    lv_obj_set_style_bg_grad_dir(scr_openrouter, LV_GRAD_DIR_VER, LV_PART_MAIN);
    lv_obj_set_style_pad_all(scr_openrouter, 0, LV_PART_MAIN);

    or_account_label = lv_label_create(scr_openrouter);
    lv_label_set_text(or_account_label, "OpenRouter");
    lv_obj_set_size(or_account_label, 320, 24);
    lv_label_set_long_mode(or_account_label, LV_LABEL_LONG_DOT);
    lv_obj_set_style_text_color(or_account_label, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
    lv_obj_set_style_text_font(or_account_label, &lv_font_montserrat_16, LV_PART_MAIN);
    lv_obj_set_pos(or_account_label, 12, 7);

    lv_obj_t *home = lv_btn_create(scr_openrouter);
    lv_obj_set_size(home, 48, 38);
    lv_obj_set_pos(home, 422, 1);
    lv_obj_set_style_radius(home, 6, LV_PART_MAIN);
    lv_obj_set_style_bg_color(home, lv_color_hex(0x20302C), LV_PART_MAIN);
    lv_obj_set_style_border_color(home, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
    lv_obj_set_style_border_width(home, 1, LV_PART_MAIN);
    lv_obj_set_style_pad_all(home, 0, LV_PART_MAIN);
    lv_obj_add_event_cb(home, homeButtonEvent, LV_EVENT_CLICKED, NULL);
    lv_obj_t *homeIcon = lv_label_create(home);
    lv_label_set_text(homeIcon, LV_SYMBOL_HOME);
    lv_obj_set_style_text_color(homeIcon, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
    lv_obj_center(homeIcon);

    or_balance_arc = lv_arc_create(scr_openrouter);
    lv_obj_set_size(or_balance_arc, 120, 120);
    lv_obj_set_pos(or_balance_arc, 10, 36);
    lv_arc_set_range(or_balance_arc, 0, 100);
    lv_arc_set_bg_angles(or_balance_arc, 135, 45);
    lv_arc_set_value(or_balance_arc, 0);
    lv_obj_remove_style(or_balance_arc, NULL, LV_PART_KNOB);
    lv_obj_clear_flag(or_balance_arc, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_style_arc_width(or_balance_arc, 10, LV_PART_MAIN);
    lv_obj_set_style_arc_color(or_balance_arc, lv_color_hex(0x263330), LV_PART_MAIN);
    lv_obj_set_style_arc_width(or_balance_arc, 10, LV_PART_INDICATOR);
    lv_obj_set_style_arc_color(or_balance_arc, lv_color_hex(0xA7F3D0), LV_PART_INDICATOR);
    or_balance_value = lv_label_create(or_balance_arc);
    lv_label_set_text(or_balance_value, "$0.00");
    lv_obj_set_style_text_color(or_balance_value, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
    lv_obj_set_style_text_font(or_balance_value, &lv_font_montserrat_20, LV_PART_MAIN);
    lv_obj_align(or_balance_value, LV_ALIGN_CENTER, 0, -6);
    lv_obj_t *remaining = lv_label_create(or_balance_arc);
    lv_label_set_text(remaining, "remaining");
    lv_obj_set_style_text_color(remaining, lv_color_hex(0x94A3B8), LV_PART_MAIN);
    lv_obj_set_style_text_font(remaining, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_align(remaining, LV_ALIGN_CENTER, 0, 18);

    createOpenRouterSpendCard(scr_openrouter, "Today", 146, &or_today_value);
    createOpenRouterSpendCard(scr_openrouter, "Week", 252, &or_week_value);
    createOpenRouterSpendCard(scr_openrouter, "Month", 358, &or_month_value);

    lv_obj_t *chartCard = lv_obj_create(scr_openrouter);
    lv_obj_set_size(chartCard, 260, 115);
    lv_obj_set_pos(chartCard, 10, 168);
    lv_obj_clear_flag(chartCard, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_color(chartCard, lv_color_hex(0x121817), LV_PART_MAIN);
    lv_obj_set_style_border_color(chartCard, lv_color_hex(0x2E403B), LV_PART_MAIN);
    lv_obj_set_style_border_width(chartCard, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(chartCard, 9, LV_PART_MAIN);
    lv_obj_set_style_pad_all(chartCard, 6, LV_PART_MAIN);
    lv_obj_t *chartTitle = lv_label_create(chartCard);
    lv_label_set_text(chartTitle, "Last 7 completed days");
    lv_obj_set_style_text_color(chartTitle, lv_color_hex(0x94A3B8), LV_PART_MAIN);
    lv_obj_set_style_text_font(chartTitle, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_set_pos(chartTitle, 4, 0);
    or_chart = lv_chart_create(chartCard);
    lv_obj_set_size(or_chart, 244, 76);
    lv_obj_set_pos(or_chart, 2, 22);
    lv_chart_set_type(or_chart, LV_CHART_TYPE_BAR);
    lv_chart_set_point_count(or_chart, 7);
    lv_chart_set_range(or_chart, LV_CHART_AXIS_PRIMARY_Y, 0, 100);
    lv_obj_set_style_bg_opa(or_chart, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(or_chart, 0, LV_PART_MAIN);
    lv_obj_set_style_line_opa(or_chart, LV_OPA_20, LV_PART_MAIN);
    lv_obj_set_style_bg_color(or_chart, lv_color_hex(0xA7F3D0), LV_PART_ITEMS);
    lv_obj_set_style_radius(or_chart, 3, LV_PART_ITEMS);
    or_chart_series = lv_chart_add_series(or_chart, lv_color_hex(0xA7F3D0), LV_CHART_AXIS_PRIMARY_Y);
    for (uint16_t i = 0; i < 7; ++i) lv_chart_set_value_by_id(or_chart, or_chart_series, i, 0);

    lv_obj_t *modelCard = lv_obj_create(scr_openrouter);
    lv_obj_set_size(modelCard, 192, 115);
    lv_obj_set_pos(modelCard, 278, 168);
    lv_obj_clear_flag(modelCard, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_bg_color(modelCard, lv_color_hex(0x181526), LV_PART_MAIN);
    lv_obj_set_style_border_color(modelCard, lv_color_hex(0x594D73), LV_PART_MAIN);
    lv_obj_set_style_border_width(modelCard, 1, LV_PART_MAIN);
    lv_obj_set_style_radius(modelCard, 9, LV_PART_MAIN);
    lv_obj_set_style_pad_all(modelCard, 8, LV_PART_MAIN);
    lv_obj_t *modelTitle = lv_label_create(modelCard);
    lv_label_set_text(modelTitle, "TOP MODEL - 7D");
    lv_obj_set_style_text_color(modelTitle, lv_color_hex(0xC4B5FD), LV_PART_MAIN);
    lv_obj_set_style_text_font(modelTitle, &lv_font_montserrat_12, LV_PART_MAIN);
    or_top_model = lv_label_create(modelCard);
    lv_label_set_text(or_top_model, "No completed usage");
    lv_obj_set_size(or_top_model, 172, 70);
    lv_label_set_long_mode(or_top_model, LV_LABEL_LONG_WRAP);
    lv_obj_set_style_text_color(or_top_model, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
    lv_obj_set_style_text_font(or_top_model, &lv_font_montserrat_14, LV_PART_MAIN);
    lv_obj_set_pos(or_top_model, 0, 24);

    or_state_label = lv_label_create(scr_openrouter);
    lv_label_set_text(or_state_label, "Waiting for cached telemetry");
    lv_obj_set_size(or_state_label, 460, 16);
    lv_label_set_long_mode(or_state_label, LV_LABEL_LONG_DOT);
    lv_obj_set_style_text_color(or_state_label, lv_color_hex(0x94A3B8), LV_PART_MAIN);
    lv_obj_set_style_text_font(or_state_label, &lv_font_montserrat_12, LV_PART_MAIN);
    lv_obj_align(or_state_label, LV_ALIGN_BOTTOM_MID, 0, -4);
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
                int weekly_left = doc["codex_weekly_pct"] | left_pct;
                String weekly_sub = doc["codex_weekly_sub"] | "Weekly reset unavailable";

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

                String weekly_value = String(weekly_left) + "% left";
                lv_label_set_text(lbl_weekly_val, weekly_value.c_str());
                lv_label_set_text(lbl_weekly_tag, "Weekly Limit");
                lv_bar_set_value(bar_weekly, weekly_left, LV_ANIM_ON);
                lv_label_set_text(lbl_weekly_sub, weekly_sub.c_str());
                const int weekly_used = 100 - weekly_left;
                const uint32_t weekly_color = weekly_used > 80 ? 0xF43F5E : weekly_used > 50 ? 0xF59E0B : 0x10B981;
                lv_obj_set_style_text_color(lbl_weekly_val, lv_color_hex(weekly_color), LV_PART_MAIN);
                lv_obj_set_style_bg_color(bar_weekly, lv_color_hex(weekly_color), LV_PART_INDICATOR);

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

void pollDisplayCommand() {
    if (WiFi.status() != WL_CONNECTED || millis() - lastDisplayCommandPoll < FETCH_INTERVAL) return;
    lastDisplayCommandPoll = millis();
    String url = String(TELEMETRY_SERVER_URL);
    url.replace("/api/v1/cyd-status", "/api/v1/display-command");
    HTTPClient http;
    if (!beginTelemetryRequest(http, telemetryPlainClient, url)) return;
    http.setReuse(true);
    http.setConnectTimeout(TELEMETRY_CONNECT_TIMEOUT_MS);
    http.setTimeout(TELEMETRY_READ_TIMEOUT_MS);
    addTelemetryAuth(http);
    const int code = http.GET();
    if (code != HTTP_CODE_OK || http.getSize() > static_cast<int>(MAX_TELEMETRY_BYTES)) {
        http.end();
        return;
    }
    JsonDocument doc;
    const DeserializationError error = deserializeJson(doc, http.getString());
    http.end();
    if (error) return;
    displayCommandSeen = true;
    String commandId = doc["id"] | "";
    String app = doc["app"] | "";
    const uint16_t rotation = doc["rotation"] | 0;
    applyDisplayRotation(rotation);
    if (commandId.length() == 0 || commandId == lastDisplayCommandId) return;
    lastDisplayCommandId = commandId;
    if (app == "openrouter") {
        homeRequested = false;
        Serial.println("[REMOTE] Dashboard -> OpenRouter");
        openUsageRequested = false;
        if (activeScreen != AppScreen::OpenRouter) openRouterRequested = true;
        else fetchOpenRouterData();
    } else if (app == "usage") {
        homeRequested = false;
        Serial.println("[REMOTE] Dashboard -> Usage Monitor");
        openRouterRequested = false;
        usageFetchPending = true;
        if (activeScreen != AppScreen::UsageMonitor) openUsageRequested = true;
    } else if (app == "launcher") {
        Serial.println("[REMOTE] Dashboard -> Launcher");
        openUsageRequested = false;
        openRouterRequested = false;
        if (activeScreen != AppScreen::MainMenu) homeRequested = true;
    }
}

void reportDisplayState() {
    if (!displayCommandSeen || !displayStateReportPending || WiFi.status() != WL_CONNECTED) return;
    if (millis() - lastDisplayStateReportAttempt < FETCH_INTERVAL) return;
    lastDisplayStateReportAttempt = millis();

    const char *app = "launcher";
    if (activeScreen == AppScreen::UsageMonitor) app = "usage";
    else if (activeScreen == AppScreen::OpenRouter) app = "openrouter";

    String url = String(TELEMETRY_SERVER_URL);
    url.replace("/api/v1/cyd-status", "/api/v1/display-state");
    HTTPClient http;
    if (!beginTelemetryRequest(http, telemetryPlainClient, url)) return;
    http.setReuse(true);
    http.setConnectTimeout(TELEMETRY_CONNECT_TIMEOUT_MS);
    http.setTimeout(TELEMETRY_READ_TIMEOUT_MS);
    addTelemetryAuth(http);
    http.addHeader("Content-Type", "application/json");

    JsonDocument doc;
    doc["app"] = app;
    doc["rotation"] = displayRotationDegrees;
    String payload;
    serializeJson(doc, payload);
    const int code = http.POST(payload);
    http.end();
    if (code == HTTP_CODE_OK) {
        displayStateReportPending = false;
        Serial.printf("[SYNC] Reported %s at %u degrees\n", app, displayRotationDegrees);
    }
}

void showOpenRouterError(const String &detail) {
    lv_label_set_text(or_balance_value, "--");
    lv_arc_set_value(or_balance_arc, 0);
    lv_label_set_text(or_today_value, "--");
    lv_label_set_text(or_week_value, "--");
    lv_label_set_text(or_month_value, "--");
    lv_label_set_text(or_top_model, detail.c_str());
    lv_label_set_text(or_state_label, "Telemetry unavailable");
    lv_obj_set_style_text_color(or_state_label, lv_color_hex(0xFBCFE8), LV_PART_MAIN);
    for (uint16_t i = 0; i < 7; ++i) lv_chart_set_value_by_id(or_chart, or_chart_series, i, 0);
    lv_chart_refresh(or_chart);
}

void fetchOpenRouterData() {
    if (WiFi.status() != WL_CONNECTED) {
        showOpenRouterError("Wi-Fi is disconnected");
        return;
    }
    String url = String(TELEMETRY_SERVER_URL);
    url.replace("/api/v1/cyd-status", "/api/v1/openrouter-status");
    HTTPClient http;
    if (!beginTelemetryRequest(http, telemetryPlainClient, url)) return;
    http.setReuse(true);
    http.setConnectTimeout(TELEMETRY_CONNECT_TIMEOUT_MS);
    http.setTimeout(TELEMETRY_READ_TIMEOUT_MS);
    addTelemetryAuth(http);
    const int code = http.GET();
    if (code != HTTP_CODE_OK) {
        if (code == HTTP_CODE_UNAUTHORIZED) showOpenRouterError("Device token rejected");
        else showOpenRouterError(code > 0 ? "Monitor returned HTTP " + String(code) : "Local monitor connection failed");
        http.end();
        return;
    }
    if (http.getSize() > static_cast<int>(MAX_TELEMETRY_BYTES)) {
        http.end();
        showOpenRouterError("Response exceeded safe size");
        return;
    }
    String payload = http.getString();
    http.end();
    if (payload.length() > MAX_TELEMETRY_BYTES) {
        showOpenRouterError("Response exceeded safe size");
        return;
    }
    JsonDocument doc;
    if (deserializeJson(doc, payload)) {
        showOpenRouterError("Monitor returned invalid JSON");
        return;
    }
    String status = doc["status"] | "error";
    String label = doc["account_label"] | "OpenRouter";
    lv_label_set_text(or_account_label, label.c_str());
    if (status != "ok") {
        String detail = status == "unconfigured" ? "Configure OpenRouter in dashboard" : String(doc["error"] | "Waiting for collector");
        showOpenRouterError(detail);
        return;
    }
    const float balance = doc["remaining_credits"] | 0.0f;
    const int percent = constrain(static_cast<int>(roundf(doc["remaining_pct"] | 0.0f)), 0, 100);
    const String balanceText = "$" + String(balance, 2);
    const String today = "$" + String(static_cast<float>(doc["usage_today"] | 0.0f), 2);
    const String week = "$" + String(static_cast<float>(doc["usage_week"] | 0.0f), 2);
    const String month = "$" + String(static_cast<float>(doc["usage_month"] | 0.0f), 2);
    lv_label_set_text(or_balance_value, balanceText.c_str());
    lv_arc_set_value(or_balance_arc, percent);
    lv_label_set_text(or_today_value, today.c_str());
    lv_label_set_text(or_week_value, week.c_str());
    lv_label_set_text(or_month_value, month.c_str());
    String model = doc["top_model"]["name"] | "No completed usage";
    lv_label_set_text(or_top_model, model.c_str());
    JsonArray daily = doc["daily_usage"].as<JsonArray>();
    float maximum = 0.0f;
    for (JsonObject point : daily) maximum = max(maximum, static_cast<float>(point["usage"] | 0.0f));
    for (uint16_t i = 0; i < 7; ++i) {
        float value = i < daily.size() ? static_cast<float>(daily[i]["usage"] | 0.0f) : 0.0f;
        int normalized = maximum > 0.0f ? static_cast<int>(roundf(value * 100.0f / maximum)) : 0;
        lv_chart_set_value_by_id(or_chart, or_chart_series, i, normalized);
    }
    lv_chart_refresh(or_chart);
    lv_label_set_text(or_state_label, "Cached OpenRouter API - refreshes every 90s");
    lv_obj_set_style_text_color(or_state_label, lv_color_hex(0x94A3B8), LV_PART_MAIN);
}

void serviceWifiState() {
    const wl_status_t status = WiFi.status();
    const bool statusChanged = status != previousWifiStatus;
    const bool becameConnected = status == WL_CONNECTED && previousWifiStatus != WL_CONNECTED;
    const unsigned long now = millis();

    if (becameConnected && (activeScreen == AppScreen::UsageMonitor || activeScreen == AppScreen::OpenRouter)) {
        usageFetchPending = true;
    }

    if (statusChanged || now - lastWifiUiUpdate >= 500) {
        lastWifiUiUpdate = now;
        if (status == WL_CONNECTED) {
            setLauncherWifiState("Online", 0xA7F3D0);
            digitalWrite(LED_BLUE, HIGH);
        } else if (now - wifiBeginTime < 15000) {
            setLauncherWifiState("Connecting", 0xFDE68A);
            digitalWrite(LED_BLUE, ((now / 500) % 2) ? HIGH : LOW);
        } else {
            setLauncherWifiState("Offline", 0xFBCFE8);
            digitalWrite(LED_BLUE, HIGH);
        }
    }
    previousWifiStatus = status;
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

    // The 4.0-inch E32R40T backlight is active-high on GPIO27.
    pinMode(TFT_BL, OUTPUT);
    digitalWrite(TFT_BL, TFT_BACKLIGHT_ON);

    // Display Setup
    displayPreferences.begin("cyd-display", false);
    displayRotationDegrees = displayPreferences.getUShort("rotation", 0) == 180 ? 180 : 0;
    tft.init();
    tft.setRotation(displayRotationDegrees == 180 ? 3 : 1); // Landscape 480x320
    Serial.printf("[DISPLAY] Restored orientation: %u degrees\n", displayRotationDegrees);
    uint8_t id1 = tft.readcommand8(0x04, 1);
    uint8_t id2 = tft.readcommand8(0x04, 2);
    uint8_t id3 = tft.readcommand8(0x04, 3);
    Serial.printf("[DISPLAY] Read ID bytes: 0x%02X 0x%02X 0x%02X\n", id1, id2, id3);
    tft.fillScreen(TFT_BLACK);

    // XPT2046 shares SCK/MOSI/MISO with the display and uses CS=33.
    Serial.println("[TOUCH] Using E32R40T XPT2046 resistive touch (shared SPI, CS=33)");
    uint16_t calData[5] = { 200, 3600, 240, 3700, 7 };
    tft.setTouch(calData);

    lv_init();
    lv_disp_draw_buf_init(&draw_buf, buf, NULL, 480 * 20);

    static lv_disp_drv_t disp_drv;
    lv_disp_drv_init(&disp_drv);
    disp_drv.hor_res = 480;
    disp_drv.ver_res = 320;
    disp_drv.flush_cb = my_disp_flush;
    disp_drv.draw_buf = &draw_buf;
    lv_disp_drv_register(&disp_drv);

    static lv_indev_drv_t indev_drv;
    lv_indev_drv_init(&indev_drv);
    indev_drv.type = LV_INDEV_TYPE_POINTER;
    indev_drv.read_cb = my_touchpad_read;
    lv_indev_drv_register(&indev_drv);

    // Build both persistent screens, then make the launcher the deterministic
    // boot destination. App screens are never deleted during transitions.
    buildLauncherUI();
    buildDashboardUI();
    buildOpenRouterUI();
    lv_scr_load(scr_launcher);
    lv_timer_handler();

    // Start Wi-Fi without blocking the launcher. Connection state, recovery,
    // and the first app fetch are serviced from loop().
    WiFi.persistent(false);
    WiFi.setAutoReconnect(true);
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    wifiBeginTime = millis();
    previousWifiStatus = WiFi.status();
    serviceWifiState();
    printSimulatorKeybinds();
}

void loop() {
    lv_timer_handler();
    delay(5);

    if (Serial.available()) {
        char c = Serial.read();
        if (c == 'u' || c == 'U') {
            if (activeScreen == AppScreen::MainMenu) {
                Serial.println("[KEY] U -> Usage Monitor");
                openUsageRequested = true;
            }
        } else if (c == 'o' || c == 'O') {
            if (activeScreen == AppScreen::MainMenu) {
                Serial.println("[KEY] O -> OpenRouter");
                openRouterRequested = true;
            }
        } else if (c == 'h' || c == 'H') {
            if (activeScreen != AppScreen::MainMenu) {
                Serial.println("[KEY] H -> Home");
                homeRequested = true;
            }
        } else if (c == 'n' || c == 'N' || c == ' ') {
            if (activeScreen == AppScreen::UsageMonitor) {
                Serial.println("[KEY] N -> Next account");
                nextAccountRequested = true;
            } else {
                Serial.println("[KEY] Open Usage Monitor before switching accounts.");
            }
        } else if (c == '?') {
            printSimulatorKeybinds();
        }
    }

    if (homeRequested) {
        homeRequested = false;
        if (activeScreen != AppScreen::MainMenu) {
            showLauncherScreen();
        }
    }

    if (openUsageRequested) {
        openUsageRequested = false;
        if (activeScreen != AppScreen::UsageMonitor) {
            showUsageMonitorScreen();
        }
    }

    if (openRouterRequested) {
        openRouterRequested = false;
        if (activeScreen != AppScreen::OpenRouter) {
            showOpenRouterScreen();
        }
    }

    serviceWifiState();
    pollDisplayCommand();

    if (!homeRequested && !openUsageRequested && !openRouterRequested) {
        reportDisplayState();
    }

    if (nextAccountRequested && activeScreen == AppScreen::UsageMonitor) {
        nextAccountRequested = false;
        triggerNextAccount();
    }

    if (usageFetchPending && activeScreen != AppScreen::MainMenu) {
        usageFetchPending = false;
        if (activeScreen == AppScreen::UsageMonitor) fetchQuotaData();
        else fetchOpenRouterData();
        lastFetchTime = millis();
    } else if (activeScreen != AppScreen::MainMenu && millis() - lastFetchTime >= FETCH_INTERVAL) {
        lastFetchTime = millis();
        if (activeScreen == AppScreen::UsageMonitor) fetchQuotaData();
        else fetchOpenRouterData();
    }
}
