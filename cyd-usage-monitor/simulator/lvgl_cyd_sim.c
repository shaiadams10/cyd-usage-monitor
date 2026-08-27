#include <emscripten/emscripten.h>
#include <lvgl.h>
#include <stdint.h>
#include <stdlib.h>
#include "../src/mascot_img.h"

#define SCREEN_W 320
#define SCREEN_H 240

static lv_color_t buffer[SCREEN_W * 24];
static lv_color_t launcher_icon_buffer[56 * 56];
static lv_disp_draw_buf_t draw_buffer;
static lv_obj_t *launcher_screen, *usage_screen, *openrouter_screen, *mascot, *ag_mascot, *header, *home_button, *next_button, *next_icon, *primary_card, *details_card, *error_card, *error_title, *error_detail, *primary_value, *primary_tag, *primary_sub, *primary_warn, *primary_bar, *weekly_value, *weekly_tag, *weekly_sub, *weekly_bar;
static lv_obj_t *grid, *gemini_heading, *claude_heading, *g5, *gw, *c5, *cw;
static lv_obj_t *or_account, *or_arc, *or_balance, *or_today, *or_week, *or_month, *or_chart, *or_model, *or_state;
static lv_chart_series_t *or_series;
static lv_point_t or_route_points[] = {{4, 36}, {15, 15}, {30, 31}, {44, 10}};
static int pointer_x, pointer_y, pointer_pressed;

EM_JS(void, canvas_blit, (int x, int y, int width, int height, const uint16_t *pixels), {
  const canvas = Module.canvas;
  const ctx = canvas.getContext('2d', { alpha: false });
  const image = ctx.createImageData(width, height);
  const source = HEAPU16.subarray(pixels >>> 1, (pixels >>> 1) + width * height);
  for (let i = 0; i < source.length; i++) {
    const value = source[i];
    const offset = i * 4;
    image.data[offset] = ((value >> 11) & 31) * 255 / 31;
    image.data[offset + 1] = ((value >> 5) & 63) * 255 / 63;
    image.data[offset + 2] = (value & 31) * 255 / 31;
    image.data[offset + 3] = 255;
  }
  ctx.putImageData(image, x, y);
});

EM_JS(void, request_next_account, (), {
  if (typeof window.cydPreviewNextAccount === 'function') {
    window.cydPreviewNextAccount();
  }
});

EM_JS(void, request_display_app, (int app), {
  if (typeof window.cydPreviewDisplayApp === 'function') {
    window.cydPreviewDisplayApp(app === 1 ? 'usage' : app === 2 ? 'openrouter' : 'launcher');
  }
});

// Export the exact same 24x24 RGB565 mascot bitmaps used by the firmware as
// data URLs for the account badges in the dashboard.  This avoids maintaining
// a second, CSS-drawn provider logo that could drift from the physical CYD.
EM_JS(void, publish_mascot, (int provider, const uint16_t *pixels), {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 24;
  const image = canvas.getContext('2d').createImageData(24, 24);
  const source = HEAPU16.subarray(pixels >>> 1, (pixels >>> 1) + 24 * 24);
  for (let i = 0; i < source.length; i++) {
    const value = source[i], offset = i * 4;
    image.data[offset] = ((value >> 11) & 31) * 255 / 31;
    image.data[offset + 1] = ((value >> 5) & 63) * 255 / 63;
    image.data[offset + 2] = (value & 31) * 255 / 31;
    image.data[offset + 3] = 255;
  }
  canvas.getContext('2d').putImageData(image, 0, 0);
  window.cydProviderMascots = window.cydProviderMascots || {};
  window.cydProviderMascots[provider ? 'antigravity' : 'codex'] = canvas.toDataURL('image/png');
});

EMSCRIPTEN_KEEPALIVE void cyd_publish_provider_mascots(void) {
  publish_mascot(0, (const uint16_t *)mascot_pixel_map);
  publish_mascot(1, (const uint16_t *)antigravity_mascot_pixel_map);
}

static void flush(lv_disp_drv_t *driver, const lv_area_t *area, lv_color_t *color) {
  const int width = area->x2 - area->x1 + 1;
  const int height = area->y2 - area->y1 + 1;
  canvas_blit(area->x1, area->y1, width, height, (const uint16_t *)color);
  lv_disp_flush_ready(driver);
}

static void style_card(lv_obj_t *card, uint32_t border, int radius) {
  lv_obj_clear_flag(card, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_scrollbar_mode(card, LV_SCROLLBAR_MODE_OFF);
  lv_obj_set_style_bg_color(card, lv_color_hex(0x18181B), LV_PART_MAIN);
  lv_obj_set_style_border_color(card, lv_color_hex(border), LV_PART_MAIN);
  lv_obj_set_style_border_width(card, 1, LV_PART_MAIN);
  lv_obj_set_style_radius(card, radius, LV_PART_MAIN);
  lv_obj_set_style_pad_all(card, 7, LV_PART_MAIN);
}

static lv_obj_t *make_grid_card(lv_obj_t *parent, const char *title, int x, int y, uint32_t color) {
  lv_obj_t *card = lv_obj_create(parent);
  // The WebAssembly preview uses a compact grid with explicit outer gutters.
  // This is intentionally simulator-only: the physical 320x240 layout remains
  // unchanged while browser rasterization keeps every card border visible.
  lv_obj_set_size(card, 154, 84);
  lv_obj_set_pos(card, x, y);
  style_card(card, color, 8);
  lv_obj_set_style_pad_all(card, 6, LV_PART_MAIN);
  lv_obj_t *label = lv_label_create(card);
  lv_label_set_text(label, title);
  lv_obj_set_style_text_color(label, lv_color_hex(color), LV_PART_MAIN);
  lv_obj_set_style_text_font(label, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_set_pos(label, 3, 2);
  return card;
}

static void set_grid_card(lv_obj_t *card, const char *value, const char *sub, uint32_t color) {
  lv_obj_t *value_label = lv_obj_get_child(card, 1);
  lv_obj_t *bar = lv_obj_get_child(card, 2);
  lv_obj_t *sub_label = lv_obj_get_child(card, 3);
  lv_label_set_text(value_label, value);
  lv_obj_set_style_text_color(value_label, lv_color_hex(color), LV_PART_MAIN);
  lv_bar_set_value(bar, atoi(value), LV_ANIM_OFF);
  lv_label_set_text(sub_label, sub);
}

static void finish_grid_card(lv_obj_t *card, uint32_t color) {
  lv_obj_t *value = lv_label_create(card);
  lv_label_set_text(value, "-");
  lv_obj_set_style_text_font(value, &lv_font_montserrat_20, LV_PART_MAIN);
  lv_obj_align(value, LV_ALIGN_TOP_RIGHT, -2, 0);
  lv_obj_t *bar = lv_bar_create(card);
  lv_obj_set_size(bar, 136, 10);
  lv_obj_set_pos(bar, 3, 31);
  lv_bar_set_range(bar, 0, 100);
  lv_obj_set_style_bg_color(bar, lv_color_hex(0x27272A), LV_PART_MAIN);
  lv_obj_set_style_bg_color(bar, lv_color_hex(color), LV_PART_INDICATOR);
  lv_obj_t *sub = lv_label_create(card);
  lv_label_set_text(sub, "Waiting for collector");
  lv_obj_set_style_text_color(sub, lv_color_hex(0x94A3B8), LV_PART_MAIN);
  lv_obj_set_style_text_font(sub, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_set_pos(sub, 3, 50);
}

static void pointer_read(lv_indev_drv_t *driver, lv_indev_data_t *data) {
  (void)driver;
  data->point.x = pointer_x;
  data->point.y = pointer_y;
  data->state = pointer_pressed ? LV_INDEV_STATE_PR : LV_INDEV_STATE_REL;
}

static void open_usage_event(lv_event_t *event) {
  if (lv_event_get_code(event) == LV_EVENT_CLICKED) {
    lv_scr_load_anim(usage_screen, LV_SCR_LOAD_ANIM_MOVE_LEFT, 180, 0, false);
    request_display_app(1);
  }
}

static void open_openrouter_event(lv_event_t *event) {
  if (lv_event_get_code(event) == LV_EVENT_CLICKED) {
    lv_scr_load_anim(openrouter_screen, LV_SCR_LOAD_ANIM_MOVE_LEFT, 180, 0, false);
    request_display_app(2);
  }
}

static void home_event(lv_event_t *event) {
  if (lv_event_get_code(event) == LV_EVENT_CLICKED) {
    lv_scr_load_anim(launcher_screen, LV_SCR_LOAD_ANIM_MOVE_RIGHT, 180, 0, false);
    request_display_app(0);
  }
}

static void next_account_event(lv_event_t *event) {
  if (lv_event_get_code(event) == LV_EVENT_CLICKED) {
    request_next_account();
  }
}

static void draw_launcher_icon(lv_obj_t *canvas) {
  lv_canvas_set_buffer(canvas, launcher_icon_buffer, 56, 56, LV_IMG_CF_TRUE_COLOR_CHROMA_KEYED);
  lv_canvas_fill_bg(canvas, LV_COLOR_CHROMA_KEY, LV_OPA_COVER);

  lv_draw_arc_dsc_t arc;
  lv_draw_arc_dsc_init(&arc);
  arc.color = lv_color_hex(0xC4B5FD);
  arc.width = 5;
  arc.rounded = true;
  lv_canvas_draw_arc(canvas, 28, 27, 20, 40, 320, &arc);

  lv_draw_arc_dsc_t accent;
  lv_draw_arc_dsc_init(&accent);
  accent.color = lv_color_hex(0xA7F3D0);
  accent.width = 5;
  accent.rounded = true;
  lv_canvas_draw_arc(canvas, 28, 27, 20, 40, 165, &accent);

  const uint32_t colors[] = {0xFBCFE8, 0xBAE6FD, 0xFDE68A};
  const lv_coord_t heights[] = {8, 14, 20};
  for (int i = 0; i < 3; ++i) {
    lv_draw_rect_dsc_t bar;
    lv_draw_rect_dsc_init(&bar);
    bar.bg_color = lv_color_hex(colors[i]);
    bar.bg_opa = LV_OPA_COVER;
    bar.radius = 2;
    lv_canvas_draw_rect(canvas, 17 + i * 9, 45 - heights[i], 6, heights[i], &bar);
  }
}

static void build_launcher(void) {
  launcher_screen = lv_obj_create(NULL);
  lv_obj_clear_flag(launcher_screen, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_style_bg_color(launcher_screen, lv_color_hex(0x111217), LV_PART_MAIN);
  lv_obj_set_style_bg_grad_color(launcher_screen, lv_color_hex(0x191622), LV_PART_MAIN);
  lv_obj_set_style_bg_grad_dir(launcher_screen, LV_GRAD_DIR_VER, LV_PART_MAIN);
  lv_obj_set_style_pad_all(launcher_screen, 0, LV_PART_MAIN);

  lv_obj_t *lavender = lv_obj_create(launcher_screen);
  lv_obj_set_size(lavender, 92, 92);
  lv_obj_set_pos(lavender, 266, -44);
  lv_obj_set_style_radius(lavender, LV_RADIUS_CIRCLE, LV_PART_MAIN);
  lv_obj_set_style_bg_color(lavender, lv_color_hex(0xC4B5FD), LV_PART_MAIN);
  lv_obj_set_style_bg_opa(lavender, LV_OPA_10, LV_PART_MAIN);
  lv_obj_set_style_border_width(lavender, 0, LV_PART_MAIN);

  lv_obj_t *mint = lv_obj_create(launcher_screen);
  lv_obj_set_size(mint, 76, 76);
  lv_obj_set_pos(mint, -36, 196);
  lv_obj_set_style_radius(mint, LV_RADIUS_CIRCLE, LV_PART_MAIN);
  lv_obj_set_style_bg_color(mint, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
  lv_obj_set_style_bg_opa(mint, LV_OPA_10, LV_PART_MAIN);
  lv_obj_set_style_border_width(mint, 0, LV_PART_MAIN);

  lv_obj_t *title = lv_label_create(launcher_screen);
  lv_label_set_text(title, "CYD Apps");
  lv_obj_set_style_text_color(title, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
  lv_obj_set_style_text_font(title, &lv_font_montserrat_24, LV_PART_MAIN);
  lv_obj_set_pos(title, 16, 10);

  lv_obj_t *subtitle = lv_label_create(launcher_screen);
  lv_label_set_text(subtitle, "Choose an app");
  lv_obj_set_style_text_color(subtitle, lv_color_hex(0xC7D2FE), LV_PART_MAIN);
  lv_obj_set_style_text_font(subtitle, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_set_pos(subtitle, 18, 40);

  lv_obj_t *status = lv_obj_create(launcher_screen);
  lv_obj_set_size(status, 91, 27);
  lv_obj_set_pos(status, 216, 13);
  lv_obj_clear_flag(status, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_style_bg_color(status, lv_color_hex(0x202028), LV_PART_MAIN);
  lv_obj_set_style_border_color(status, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
  lv_obj_set_style_border_width(status, 1, LV_PART_MAIN);
  lv_obj_set_style_radius(status, 14, LV_PART_MAIN);
  lv_obj_set_style_pad_all(status, 0, LV_PART_MAIN);
  lv_obj_t *dot = lv_obj_create(status);
  lv_obj_set_size(dot, 8, 8);
  lv_obj_set_pos(dot, 10, 8);
  lv_obj_set_style_radius(dot, LV_RADIUS_CIRCLE, LV_PART_MAIN);
  lv_obj_set_style_bg_color(dot, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
  lv_obj_set_style_border_width(dot, 0, LV_PART_MAIN);
  lv_obj_t *status_label = lv_label_create(status);
  lv_label_set_text(status_label, "Preview");
  lv_obj_set_style_text_color(status_label, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
  lv_obj_set_style_text_font(status_label, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_set_pos(status_label, 24, 6);

  lv_obj_t *apps = lv_obj_create(launcher_screen);
  lv_obj_set_size(apps, 304, 170);
  lv_obj_set_pos(apps, 8, 62);
  lv_obj_clear_flag(apps, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_style_bg_opa(apps, LV_OPA_TRANSP, LV_PART_MAIN);
  lv_obj_set_style_border_width(apps, 0, LV_PART_MAIN);
  lv_obj_set_style_pad_all(apps, 6, LV_PART_MAIN);
  lv_obj_set_style_pad_column(apps, 8, LV_PART_MAIN);
  lv_obj_set_flex_flow(apps, LV_FLEX_FLOW_ROW_WRAP);
  lv_obj_set_flex_align(apps, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);

  lv_obj_t *tile = lv_btn_create(apps);
  lv_obj_set_size(tile, 142, 146);
  lv_obj_set_style_bg_color(tile, lv_color_hex(0x282432), LV_PART_MAIN);
  lv_obj_set_style_bg_grad_color(tile, lv_color_hex(0x202A31), LV_PART_MAIN);
  lv_obj_set_style_bg_grad_dir(tile, LV_GRAD_DIR_VER, LV_PART_MAIN);
  lv_obj_set_style_border_color(tile, lv_color_hex(0xC4B5FD), LV_PART_MAIN);
  lv_obj_set_style_border_width(tile, 2, LV_PART_MAIN);
  lv_obj_set_style_radius(tile, 20, LV_PART_MAIN);
  lv_obj_set_style_shadow_color(tile, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
  lv_obj_set_style_shadow_width(tile, 18, LV_PART_MAIN);
  lv_obj_set_style_shadow_opa(tile, LV_OPA_20, LV_PART_MAIN);
  lv_obj_set_style_pad_all(tile, 0, LV_PART_MAIN);
  lv_obj_set_style_transform_zoom(tile, 242, LV_STATE_PRESSED);
  lv_obj_set_style_bg_color(tile, lv_color_hex(0x332D42), LV_STATE_PRESSED);
  lv_obj_add_event_cb(tile, open_usage_event, LV_EVENT_CLICKED, NULL);
  lv_obj_t *icon = lv_canvas_create(tile);
  lv_obj_clear_flag(icon, LV_OBJ_FLAG_CLICKABLE);
  draw_launcher_icon(icon);
  lv_obj_align(icon, LV_ALIGN_TOP_MID, 0, 10);
  lv_obj_t *app_title = lv_label_create(tile);
  lv_label_set_text(app_title, "Usage Monitor");
  lv_obj_set_style_text_color(app_title, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
  lv_obj_set_style_text_font(app_title, &lv_font_montserrat_16, LV_PART_MAIN);
  lv_obj_align(app_title, LV_ALIGN_TOP_MID, 0, 74);
  lv_obj_t *app_subtitle = lv_label_create(tile);
  lv_label_set_text(app_subtitle, "AI quota dashboard");
  lv_obj_set_style_text_color(app_subtitle, lv_color_hex(0xC7D2FE), LV_PART_MAIN);
  lv_obj_set_style_text_font(app_subtitle, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_align(app_subtitle, LV_ALIGN_TOP_MID, 0, 99);
  lv_obj_t *open_label = lv_label_create(tile);
  lv_label_set_text(open_label, "Open  " LV_SYMBOL_RIGHT);
  lv_obj_set_style_text_color(open_label, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
  lv_obj_set_style_text_font(open_label, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_align(open_label, LV_ALIGN_BOTTOM_MID, 0, -8);
  lv_obj_fade_in(tile, 220, 60);

  lv_obj_t *router_tile = lv_btn_create(apps);
  lv_obj_set_size(router_tile, 142, 146);
  lv_obj_set_style_bg_color(router_tile, lv_color_hex(0x202A2A), LV_PART_MAIN);
  lv_obj_set_style_bg_grad_color(router_tile, lv_color_hex(0x282432), LV_PART_MAIN);
  lv_obj_set_style_bg_grad_dir(router_tile, LV_GRAD_DIR_VER, LV_PART_MAIN);
  lv_obj_set_style_border_color(router_tile, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
  lv_obj_set_style_border_width(router_tile, 2, LV_PART_MAIN);
  lv_obj_set_style_radius(router_tile, 20, LV_PART_MAIN);
  lv_obj_set_style_pad_all(router_tile, 0, LV_PART_MAIN);
  lv_obj_set_style_transform_zoom(router_tile, 242, LV_STATE_PRESSED);
  lv_obj_add_event_cb(router_tile, open_openrouter_event, LV_EVENT_CLICKED, NULL);
  lv_obj_t *route_icon = lv_obj_create(router_tile);
  lv_obj_clear_flag(route_icon, LV_OBJ_FLAG_CLICKABLE);
  lv_obj_set_size(route_icon, 56, 56);
  lv_obj_align(route_icon, LV_ALIGN_TOP_MID, 0, 10);
  lv_obj_set_style_bg_opa(route_icon, LV_OPA_TRANSP, LV_PART_MAIN);
  lv_obj_set_style_border_width(route_icon, 0, LV_PART_MAIN);
  lv_obj_set_style_pad_all(route_icon, 4, LV_PART_MAIN);
  lv_obj_t *route = lv_line_create(route_icon);
  lv_line_set_points(route, or_route_points, 4);
  lv_obj_set_style_line_color(route, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
  lv_obj_set_style_line_width(route, 5, LV_PART_MAIN);
  lv_obj_set_style_line_rounded(route, true, LV_PART_MAIN);
  for (int i = 0; i < 4; ++i) {
    lv_obj_t *node = lv_obj_create(route_icon);
    lv_obj_clear_flag(node, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_set_size(node, 9, 9);
    lv_obj_set_pos(node, or_route_points[i].x - 4, or_route_points[i].y - 4);
    lv_obj_set_style_radius(node, LV_RADIUS_CIRCLE, LV_PART_MAIN);
    lv_obj_set_style_bg_color(node, lv_color_hex(0xC4B5FD), LV_PART_MAIN);
    lv_obj_set_style_border_width(node, 0, LV_PART_MAIN);
  }
  lv_obj_t *router_title = lv_label_create(router_tile);
  lv_label_set_text(router_title, "OpenRouter");
  lv_obj_set_style_text_color(router_title, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
  lv_obj_set_style_text_font(router_title, &lv_font_montserrat_16, LV_PART_MAIN);
  lv_obj_align(router_title, LV_ALIGN_TOP_MID, 0, 74);
  lv_obj_t *router_subtitle = lv_label_create(router_tile);
  lv_label_set_text(router_subtitle, "Credits & spend");
  lv_obj_set_style_text_color(router_subtitle, lv_color_hex(0xC7D2FE), LV_PART_MAIN);
  lv_obj_set_style_text_font(router_subtitle, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_align(router_subtitle, LV_ALIGN_TOP_MID, 0, 99);
  lv_obj_t *router_open = lv_label_create(router_tile);
  lv_label_set_text(router_open, "Open  " LV_SYMBOL_RIGHT);
  lv_obj_set_style_text_color(router_open, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
  lv_obj_set_style_text_font(router_open, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_align(router_open, LV_ALIGN_BOTTOM_MID, 0, -8);
  lv_obj_fade_in(router_tile, 220, 100);
}

EMSCRIPTEN_KEEPALIVE void cyd_pointer(int x, int y, int pressed) {
  pointer_x = x < 0 ? 0 : x >= SCREEN_W ? SCREEN_W - 1 : x;
  pointer_y = y < 0 ? 0 : y >= SCREEN_H ? SCREEN_H - 1 : y;
  pointer_pressed = pressed != 0;
}

static lv_obj_t *make_or_spend(lv_obj_t *parent, const char *title, int x, lv_obj_t **value) {
  lv_obj_t *card = lv_obj_create(parent);
  lv_obj_set_size(card, 64, 72);
  lv_obj_set_pos(card, x, 37);
  style_card(card, 0x345048, 9);
  lv_obj_set_style_bg_color(card, lv_color_hex(0x151D1C), LV_PART_MAIN);
  lv_obj_t *caption = lv_label_create(card);
  lv_label_set_text(caption, title);
  lv_obj_set_style_text_color(caption, lv_color_hex(0x94A3B8), LV_PART_MAIN);
  lv_obj_set_style_text_font(caption, &lv_font_montserrat_12, LV_PART_MAIN);
  *value = lv_label_create(card);
  lv_label_set_text(*value, "$0.00");
  lv_obj_set_style_text_color(*value, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
  lv_obj_set_style_text_font(*value, &lv_font_montserrat_14, LV_PART_MAIN);
  lv_obj_align(*value, LV_ALIGN_BOTTOM_LEFT, 0, -3);
  return card;
}

static void build_openrouter(void) {
  openrouter_screen = lv_obj_create(NULL);
  lv_obj_clear_flag(openrouter_screen, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_style_bg_color(openrouter_screen, lv_color_hex(0x0B1110), LV_PART_MAIN);
  lv_obj_set_style_bg_grad_color(openrouter_screen, lv_color_hex(0x171326), LV_PART_MAIN);
  lv_obj_set_style_bg_grad_dir(openrouter_screen, LV_GRAD_DIR_VER, LV_PART_MAIN);
  lv_obj_set_style_pad_all(openrouter_screen, 0, LV_PART_MAIN);
  or_account = lv_label_create(openrouter_screen);
  lv_label_set_text(or_account, "OpenRouter");
  lv_obj_set_size(or_account, 236, 24);
  lv_label_set_long_mode(or_account, LV_LABEL_LONG_DOT);
  lv_obj_set_style_text_color(or_account, lv_color_hex(0xF8FAFC), LV_PART_MAIN);
  lv_obj_set_style_text_font(or_account, &lv_font_montserrat_16, LV_PART_MAIN);
  lv_obj_set_pos(or_account, 12, 7);
  lv_obj_t *home = lv_btn_create(openrouter_screen);
  lv_obj_set_size(home, 28, 26); lv_obj_set_pos(home, 286, 2);
  lv_obj_set_style_radius(home, 6, LV_PART_MAIN);
  lv_obj_set_style_bg_color(home, lv_color_hex(0x20302C), LV_PART_MAIN);
  lv_obj_set_style_border_color(home, lv_color_hex(0xA7F3D0), LV_PART_MAIN);
  lv_obj_set_style_border_width(home, 1, LV_PART_MAIN); lv_obj_set_style_pad_all(home, 0, LV_PART_MAIN);
  lv_obj_add_event_cb(home, home_event, LV_EVENT_CLICKED, NULL);
  lv_obj_t *home_icon = lv_label_create(home); lv_label_set_text(home_icon, LV_SYMBOL_HOME);
  lv_obj_set_style_text_color(home_icon, lv_color_hex(0xA7F3D0), LV_PART_MAIN); lv_obj_center(home_icon);
  or_arc = lv_arc_create(openrouter_screen);
  lv_obj_set_size(or_arc, 104, 104); lv_obj_set_pos(or_arc, 4, 34);
  lv_arc_set_range(or_arc, 0, 100); lv_arc_set_bg_angles(or_arc, 135, 45); lv_arc_set_value(or_arc, 0);
  lv_obj_remove_style(or_arc, NULL, LV_PART_KNOB); lv_obj_clear_flag(or_arc, LV_OBJ_FLAG_CLICKABLE);
  lv_obj_set_style_arc_width(or_arc, 9, LV_PART_MAIN); lv_obj_set_style_arc_color(or_arc, lv_color_hex(0x263330), LV_PART_MAIN);
  lv_obj_set_style_arc_width(or_arc, 9, LV_PART_INDICATOR); lv_obj_set_style_arc_color(or_arc, lv_color_hex(0xA7F3D0), LV_PART_INDICATOR);
  or_balance = lv_label_create(or_arc); lv_label_set_text(or_balance, "$0.00");
  lv_obj_set_style_text_color(or_balance, lv_color_hex(0xF8FAFC), LV_PART_MAIN); lv_obj_set_style_text_font(or_balance, &lv_font_montserrat_20, LV_PART_MAIN); lv_obj_align(or_balance, LV_ALIGN_CENTER, 0, -5);
  lv_obj_t *remaining = lv_label_create(or_arc); lv_label_set_text(remaining, "remaining");
  lv_obj_set_style_text_color(remaining, lv_color_hex(0x94A3B8), LV_PART_MAIN); lv_obj_set_style_text_font(remaining, &lv_font_montserrat_12, LV_PART_MAIN); lv_obj_align(remaining, LV_ALIGN_CENTER, 0, 17);
  make_or_spend(openrouter_screen, "Today", 114, &or_today);
  make_or_spend(openrouter_screen, "Week", 181, &or_week);
  make_or_spend(openrouter_screen, "Month", 248, &or_month);
  lv_obj_t *chart_card = lv_obj_create(openrouter_screen); lv_obj_set_size(chart_card, 190, 78); lv_obj_set_pos(chart_card, 4, 145); style_card(chart_card, 0x2E403B, 9);
  lv_obj_set_style_bg_color(chart_card, lv_color_hex(0x121817), LV_PART_MAIN);
  lv_obj_t *chart_title = lv_label_create(chart_card); lv_label_set_text(chart_title, "Last 7 completed days");
  lv_obj_set_style_text_color(chart_title, lv_color_hex(0x94A3B8), LV_PART_MAIN); lv_obj_set_style_text_font(chart_title, &lv_font_montserrat_12, LV_PART_MAIN); lv_obj_set_pos(chart_title, 2, -1);
  or_chart = lv_chart_create(chart_card); lv_obj_set_size(or_chart, 176, 48); lv_obj_set_pos(or_chart, 1, 19);
  lv_chart_set_type(or_chart, LV_CHART_TYPE_BAR); lv_chart_set_point_count(or_chart, 7); lv_chart_set_range(or_chart, LV_CHART_AXIS_PRIMARY_Y, 0, 100);
  lv_obj_set_style_bg_opa(or_chart, LV_OPA_TRANSP, LV_PART_MAIN); lv_obj_set_style_border_width(or_chart, 0, LV_PART_MAIN); lv_obj_set_style_line_opa(or_chart, LV_OPA_20, LV_PART_MAIN);
  lv_obj_set_style_bg_color(or_chart, lv_color_hex(0xA7F3D0), LV_PART_ITEMS); lv_obj_set_style_radius(or_chart, 3, LV_PART_ITEMS);
  or_series = lv_chart_add_series(or_chart, lv_color_hex(0xA7F3D0), LV_CHART_AXIS_PRIMARY_Y);
  lv_obj_t *model_card = lv_obj_create(openrouter_screen); lv_obj_set_size(model_card, 117, 78); lv_obj_set_pos(model_card, 199, 145); style_card(model_card, 0x594D73, 9);
  lv_obj_set_style_bg_color(model_card, lv_color_hex(0x181526), LV_PART_MAIN);
  lv_obj_t *model_title = lv_label_create(model_card); lv_label_set_text(model_title, "TOP MODEL - 7D");
  lv_obj_set_style_text_color(model_title, lv_color_hex(0xC4B5FD), LV_PART_MAIN); lv_obj_set_style_text_font(model_title, &lv_font_montserrat_12, LV_PART_MAIN);
  or_model = lv_label_create(model_card); lv_label_set_text(or_model, "No completed usage"); lv_obj_set_size(or_model, 99, 43); lv_label_set_long_mode(or_model, LV_LABEL_LONG_WRAP);
  lv_obj_set_style_text_color(or_model, lv_color_hex(0xF8FAFC), LV_PART_MAIN); lv_obj_set_style_text_font(or_model, &lv_font_montserrat_12, LV_PART_MAIN); lv_obj_set_pos(or_model, 0, 22);
  or_state = lv_label_create(openrouter_screen); lv_label_set_text(or_state, "Waiting for cached telemetry"); lv_obj_set_size(or_state, 300, 14); lv_label_set_long_mode(or_state, LV_LABEL_LONG_DOT);
  lv_obj_set_style_text_color(or_state, lv_color_hex(0x94A3B8), LV_PART_MAIN); lv_obj_set_style_text_font(or_state, &lv_font_montserrat_12, LV_PART_MAIN); lv_obj_set_pos(or_state, 10, 224);
}

EMSCRIPTEN_KEEPALIVE void cyd_init(void) {
  lv_init();
  lv_disp_draw_buf_init(&draw_buffer, buffer, NULL, SCREEN_W * 24);
  static lv_disp_drv_t driver;
  lv_disp_drv_init(&driver);
  driver.hor_res = SCREEN_W;
  driver.ver_res = SCREEN_H;
  driver.flush_cb = flush;
  driver.draw_buf = &draw_buffer;
  lv_disp_drv_register(&driver);

  static lv_indev_drv_t pointer_driver;
  lv_indev_drv_init(&pointer_driver);
  pointer_driver.type = LV_INDEV_TYPE_POINTER;
  pointer_driver.read_cb = pointer_read;
  lv_indev_drv_register(&pointer_driver);

  build_launcher();
  build_openrouter();

  usage_screen = lv_obj_create(NULL);
  // The browser canvas is an exact 320x240 viewport.  The simulator screen
  // must never become a scrollable parent, or LVGL can clip the right column
  // of the Antigravity 2x2 grid even though the physical screen has no scroll.
  lv_obj_clear_flag(usage_screen, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_scrollbar_mode(usage_screen, LV_SCROLLBAR_MODE_OFF);
  lv_obj_set_style_bg_color(usage_screen, lv_color_hex(0x09090B), LV_PART_MAIN);
  lv_obj_set_style_pad_all(usage_screen, 0, LV_PART_MAIN);

  mascot = lv_img_create(usage_screen);
  lv_img_set_src(mascot, &mascot_img);
  lv_obj_set_pos(mascot, 6, 3);
  // Reuse the exact Antigravity bitmap used by the physical CYD.  The web
  // preview is therefore a renderer of the device asset, not an HTML "AG"
  // substitute.
  ag_mascot = lv_img_create(usage_screen);
  lv_img_set_src(ag_mascot, &antigravity_mascot_img);
  lv_obj_set_pos(ag_mascot, 6, 3);
  lv_obj_add_flag(ag_mascot, LV_OBJ_FLAG_HIDDEN);
  header = lv_label_create(usage_screen);
  lv_label_set_text(header, "Waiting for collector");
  lv_obj_set_style_text_color(header, lv_color_hex(0xFFFFFF), LV_PART_MAIN);
  lv_obj_set_style_text_font(header, &lv_font_montserrat_16, LV_PART_MAIN);
  lv_obj_set_size(header, 214, 20);
  lv_label_set_long_mode(header, LV_LABEL_LONG_DOT);
  lv_obj_set_pos(header, 36, 4);

  home_button = lv_btn_create(usage_screen);
  lv_obj_set_size(home_button, 28, 26);
  lv_obj_set_pos(home_button, 258, 1);
  lv_obj_set_style_radius(home_button, 6, LV_PART_MAIN);
  lv_obj_set_style_bg_color(home_button, lv_color_hex(0x2B2635), LV_PART_MAIN);
  lv_obj_set_style_border_color(home_button, lv_color_hex(0xC4B5FD), LV_PART_MAIN);
  lv_obj_set_style_border_width(home_button, 1, LV_PART_MAIN);
  lv_obj_set_style_pad_all(home_button, 0, LV_PART_MAIN);
  lv_obj_set_style_transform_zoom(home_button, 238, LV_STATE_PRESSED);
  lv_obj_add_event_cb(home_button, home_event, LV_EVENT_CLICKED, NULL);
  lv_obj_t *home_icon = lv_label_create(home_button);
  lv_label_set_text(home_icon, LV_SYMBOL_HOME);
  lv_obj_set_style_text_color(home_icon, lv_color_hex(0xC4B5FD), LV_PART_MAIN);
  lv_obj_center(home_icon);

  next_button = lv_btn_create(usage_screen);
  lv_obj_set_size(next_button, 28, 26);
  lv_obj_set_pos(next_button, 290, 1);
  lv_obj_set_style_radius(next_button, 6, LV_PART_MAIN);
  lv_obj_set_style_bg_color(next_button, lv_color_hex(0x17212A), LV_PART_MAIN);
  lv_obj_set_style_border_color(next_button, lv_color_hex(0x334155), LV_PART_MAIN);
  lv_obj_set_style_border_width(next_button, 1, LV_PART_MAIN);
  lv_obj_set_style_pad_all(next_button, 0, LV_PART_MAIN);
  lv_obj_set_style_transform_zoom(next_button, 238, LV_STATE_PRESSED);
  lv_obj_add_event_cb(next_button, next_account_event, LV_EVENT_CLICKED, NULL);
  next_icon = lv_label_create(next_button);
  lv_label_set_text(next_icon, LV_SYMBOL_NEXT);
  lv_obj_set_style_text_color(next_icon, lv_color_hex(0x10B981), LV_PART_MAIN);
  lv_obj_center(next_icon);

  lv_obj_t *primary = lv_obj_create(usage_screen);
  primary_card = primary;
  lv_obj_set_size(primary, 312, 122);
  lv_obj_set_pos(primary, 4, 30);
  style_card(primary, 0x27272A, 12);
  primary_value = lv_label_create(primary);
  lv_label_set_text(primary_value, "-");
  lv_obj_set_style_text_font(primary_value, &lv_font_montserrat_32, LV_PART_MAIN);
  lv_obj_set_pos(primary_value, 6, 1);
  lv_obj_t *badge = lv_obj_create(primary);
  lv_obj_set_size(badge, 116, 24);
  lv_obj_align(badge, LV_ALIGN_TOP_RIGHT, 0, -2);
  lv_obj_set_style_bg_color(badge, lv_color_hex(0x27272A), LV_PART_MAIN);
  lv_obj_set_style_border_width(badge, 0, LV_PART_MAIN);
  lv_obj_set_style_radius(badge, 10, LV_PART_MAIN);
  primary_tag = lv_label_create(badge);
  lv_label_set_text(primary_tag, "Usage Limit");
  lv_obj_center(primary_tag);
  primary_bar = lv_bar_create(primary);
  lv_obj_set_size(primary_bar, 296, 14);
  lv_obj_set_pos(primary_bar, 4, 52);
  lv_bar_set_range(primary_bar, 0, 100);
  lv_obj_set_style_bg_color(primary_bar, lv_color_hex(0x27272A), LV_PART_MAIN);
  lv_obj_set_style_border_color(primary_bar, lv_color_hex(0x3F3F46), LV_PART_MAIN);
  lv_obj_set_style_border_width(primary_bar, 1, LV_PART_MAIN);
  lv_obj_set_style_bg_color(primary_bar, lv_color_hex(0x10B981), LV_PART_INDICATOR);
  lv_obj_set_style_radius(primary_bar, 6, LV_PART_MAIN);
  lv_obj_set_style_radius(primary_bar, 6, LV_PART_INDICATOR);
  primary_warn = lv_label_create(primary);
  lv_label_set_text(primary_warn, "100% QUOTA EXHAUSTED");
  lv_obj_set_style_text_color(primary_warn, lv_color_hex(0xF43F5E), LV_PART_MAIN);
  lv_obj_set_style_text_font(primary_warn, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_align_to(primary_warn, primary_bar, LV_ALIGN_CENTER, 0, 0);
  lv_obj_add_flag(primary_warn, LV_OBJ_FLAG_HIDDEN);
  primary_sub = lv_label_create(primary);
  lv_label_set_text(primary_sub, "Waiting for a CLI result");
  lv_obj_set_style_text_color(primary_sub, lv_color_hex(0x10B981), LV_PART_MAIN);
  lv_obj_set_style_text_font(primary_sub, &lv_font_montserrat_14, LV_PART_MAIN);
  lv_obj_set_pos(primary_sub, 6, 80);
  lv_obj_t *details = lv_obj_create(usage_screen);
  details_card = details;
  lv_obj_set_size(details, 312, 60);
  lv_obj_set_pos(details, 4, 160);
  style_card(details, 0x27272A, 10);
  weekly_value = lv_label_create(details);
  lv_label_set_text(weekly_value, "-");
  lv_obj_set_style_text_font(weekly_value, &lv_font_montserrat_20, LV_PART_MAIN);
  lv_obj_set_pos(weekly_value, 4, -2);
  weekly_tag = lv_label_create(details);
  lv_label_set_text(weekly_tag, "Weekly Limit");
  lv_obj_set_style_text_font(weekly_tag, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_align(weekly_tag, LV_ALIGN_TOP_RIGHT, -2, 1);
  weekly_bar = lv_bar_create(details);
  lv_obj_set_size(weekly_bar, 296, 10);
  lv_obj_set_pos(weekly_bar, 1, 23);
  lv_bar_set_range(weekly_bar, 0, 100);
  lv_obj_set_style_bg_color(weekly_bar, lv_color_hex(0x27272A), LV_PART_MAIN);
  lv_obj_set_style_bg_color(weekly_bar, lv_color_hex(0x10B981), LV_PART_INDICATOR);
  weekly_sub = lv_label_create(details);
  lv_label_set_text(weekly_sub, "Waiting for weekly quota");
  lv_obj_set_style_text_color(weekly_sub, lv_color_hex(0x94A3B8), LV_PART_MAIN);
  lv_obj_set_style_text_font(weekly_sub, &lv_font_montserrat_12, LV_PART_MAIN);
  lv_obj_set_pos(weekly_sub, 3, 36);

  error_card = lv_obj_create(usage_screen);
  lv_obj_set_size(error_card, 312, 154);
  lv_obj_set_pos(error_card, 4, 48);
  style_card(error_card, 0xF43F5E, 12);
  lv_obj_set_style_bg_color(error_card, lv_color_hex(0x211316), LV_PART_MAIN);
  error_title = lv_label_create(error_card);
  lv_label_set_text(error_title, "Usage unavailable");
  lv_obj_set_style_text_color(error_title, lv_color_hex(0xF43F5E), LV_PART_MAIN);
  lv_obj_set_style_text_font(error_title, &lv_font_montserrat_20, LV_PART_MAIN);
  lv_obj_set_pos(error_title, 7, 10);
  error_detail = lv_label_create(error_card);
  lv_label_set_text(error_detail, "Waiting for the CLI collector.");
  lv_obj_set_style_text_color(error_detail, lv_color_hex(0xF4D7DA), LV_PART_MAIN);
  lv_obj_set_style_text_font(error_detail, &lv_font_montserrat_14, LV_PART_MAIN);
  lv_obj_set_size(error_detail, 280, 90);
  lv_label_set_long_mode(error_detail, LV_LABEL_LONG_WRAP);
  lv_obj_set_pos(error_detail, 7, 48);
  lv_obj_add_flag(error_card, LV_OBJ_FLAG_HIDDEN);

  grid = lv_obj_create(usage_screen);
  lv_obj_clear_flag(grid, LV_OBJ_FLAG_SCROLLABLE);
  lv_obj_set_scrollbar_mode(grid, LV_SCROLLBAR_MODE_OFF);
  lv_obj_set_size(grid, SCREEN_W, SCREEN_H);
  lv_obj_set_pos(grid, 0, 0);
  lv_obj_set_style_bg_opa(grid, LV_OPA_TRANSP, LV_PART_MAIN);
  lv_obj_set_style_border_width(grid, 0, LV_PART_MAIN);
  lv_obj_set_style_pad_all(grid, 0, LV_PART_MAIN);
  lv_obj_clear_flag(grid, LV_OBJ_FLAG_CLICKABLE);
  gemini_heading = lv_label_create(grid);
  lv_label_set_text(gemini_heading, "Gemini Models");
  lv_obj_set_style_text_color(gemini_heading, lv_color_hex(0x2563EB), LV_PART_MAIN);
  lv_obj_set_style_text_font(gemini_heading, &lv_font_montserrat_14, LV_PART_MAIN);
  lv_obj_set_pos(gemini_heading, 2, 28);
  claude_heading = lv_label_create(grid);
  lv_label_set_text(claude_heading, "Claude Models");
  lv_obj_set_style_text_color(claude_heading, lv_color_hex(0xF97316), LV_PART_MAIN);
  lv_obj_set_style_text_font(claude_heading, &lv_font_montserrat_14, LV_PART_MAIN);
  lv_obj_set_pos(claude_heading, 164, 28);
  g5 = make_grid_card(grid, "5H Limit", 2, 48, 0x2563EB); finish_grid_card(g5, 0x2563EB);
  c5 = make_grid_card(grid, "5H Limit", 164, 48, 0xF97316); finish_grid_card(c5, 0xF97316);
  gw = make_grid_card(grid, "Weekly", 2, 138, 0x2563EB); finish_grid_card(gw, 0x2563EB);
  cw = make_grid_card(grid, "Weekly", 164, 138, 0xF97316); finish_grid_card(cw, 0xF97316);
  lv_obj_add_flag(grid, LV_OBJ_FLAG_HIDDEN);
  // Keep the full-screen Antigravity content layer behind the header controls
  // so its transparent parent cannot intercept Home or Next pointer events.
  lv_obj_move_background(grid);

  lv_scr_load(launcher_screen);
}

EMSCRIPTEN_KEEPALIVE void cyd_tick(uint32_t elapsed_ms) {
  if (elapsed_ms < 1) elapsed_ms = 1;
  if (elapsed_ms > 100) elapsed_ms = 100;
  lv_tick_inc(elapsed_ms);
  lv_timer_handler();
}

EMSCRIPTEN_KEEPALIVE void cyd_set_codex(const char *account, const char *value, const char *tag, const char *sub, int used,
                                        const char *week_value, const char *week_sub, int week_used) {
  lv_obj_add_flag(error_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(grid, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(primary_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(details_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(mascot, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(ag_mascot, LV_OBJ_FLAG_HIDDEN);
  lv_label_set_text(header, account);
  lv_label_set_text(primary_value, value);
  lv_label_set_text(primary_tag, tag);
  lv_label_set_text(primary_sub, sub);
  lv_bar_set_value(primary_bar, 100 - used, LV_ANIM_OFF);
  uint32_t status_color = used > 80 ? 0xF43F5E : used > 50 ? 0xF59E0B : 0x10B981;
  lv_obj_set_style_text_color(primary_value, lv_color_hex(status_color), LV_PART_MAIN);
  lv_obj_set_style_bg_color(primary_bar, lv_color_hex(status_color), LV_PART_INDICATOR);
  if (used >= 100) lv_obj_clear_flag(primary_warn, LV_OBJ_FLAG_HIDDEN);
  else lv_obj_add_flag(primary_warn, LV_OBJ_FLAG_HIDDEN);
  lv_label_set_text(weekly_value, week_value);
  lv_label_set_text(weekly_sub, week_sub);
  lv_bar_set_value(weekly_bar, 100 - week_used, LV_ANIM_OFF);
  uint32_t weekly_color = week_used > 80 ? 0xF43F5E : week_used > 50 ? 0xF59E0B : 0x10B981;
  lv_obj_set_style_text_color(weekly_value, lv_color_hex(weekly_color), LV_PART_MAIN);
  lv_obj_set_style_bg_color(weekly_bar, lv_color_hex(weekly_color), LV_PART_INDICATOR);
}

EMSCRIPTEN_KEEPALIVE void cyd_show_usage(void) {
  lv_scr_load_anim(usage_screen, LV_SCR_LOAD_ANIM_MOVE_LEFT, 180, 0, false);
}

EMSCRIPTEN_KEEPALIVE void cyd_show_launcher(void) {
  lv_scr_load_anim(launcher_screen, LV_SCR_LOAD_ANIM_MOVE_RIGHT, 180, 0, false);
}

EMSCRIPTEN_KEEPALIVE void cyd_show_openrouter(void) {
  lv_scr_load_anim(openrouter_screen, LV_SCR_LOAD_ANIM_MOVE_LEFT, 180, 0, false);
}

EMSCRIPTEN_KEEPALIVE void cyd_set_antigravity(const char *account, const char *gemini5, const char *gemini5sub, const char *geminiweek, const char *geminiweeksub, const char *claude5, const char *claude5sub, const char *claudeweek, const char *claudeweeksub) {
  lv_obj_add_flag(error_card, LV_OBJ_FLAG_HIDDEN);
  lv_label_set_text(header, account);
  lv_obj_add_flag(mascot, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(ag_mascot, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(primary_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(details_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(grid, LV_OBJ_FLAG_HIDDEN);
  set_grid_card(g5, gemini5, gemini5sub, 0x2563EB);
  set_grid_card(gw, geminiweek, geminiweeksub, 0x2563EB);
  set_grid_card(c5, claude5, claude5sub, 0xF97316);
  set_grid_card(cw, claudeweek, claudeweeksub, 0xF97316);
}

EMSCRIPTEN_KEEPALIVE void cyd_set_error(const char *account, const char *detail) {
  lv_obj_add_flag(grid, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(primary_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(details_card, LV_OBJ_FLAG_HIDDEN);
  lv_obj_clear_flag(mascot, LV_OBJ_FLAG_HIDDEN);
  lv_obj_add_flag(ag_mascot, LV_OBJ_FLAG_HIDDEN);
  lv_label_set_text(header, account);
  lv_label_set_text(error_detail, detail);
  lv_obj_clear_flag(error_card, LV_OBJ_FLAG_HIDDEN);
}

EMSCRIPTEN_KEEPALIVE void cyd_set_openrouter(const char *account, const char *balance, int percent,
                                             const char *today, const char *week, const char *month,
                                             const char *model, int d1, int d2, int d3, int d4,
                                             int d5, int d6, int d7) {
  const int values[] = {d1, d2, d3, d4, d5, d6, d7};
  lv_label_set_text(or_account, account);
  lv_label_set_text(or_balance, balance);
  lv_arc_set_value(or_arc, percent < 0 ? 0 : percent > 100 ? 100 : percent);
  lv_label_set_text(or_today, today);
  lv_label_set_text(or_week, week);
  lv_label_set_text(or_month, month);
  lv_label_set_text(or_model, model);
  for (uint16_t i = 0; i < 7; ++i) lv_chart_set_value_by_id(or_chart, or_series, i, values[i]);
  lv_chart_refresh(or_chart);
  lv_label_set_text(or_state, percent > 0 ? "Cached OpenRouter API - refreshes every 90s" : "OpenRouter telemetry status");
}
